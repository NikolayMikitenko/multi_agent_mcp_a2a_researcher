from config import Settings
from openai import OpenAI
from pathlib import Path
from pypdf import PdfReader, PageObject
from typing import Any
from langchain_text_splitters import RecursiveCharacterTextSplitter
from qdrant_client import QdrantClient
from qdrant_client.models import VectorParams, Distance, PointStruct
import json

settings = Settings()

def get_embed_client() -> OpenAI:
    return OpenAI(
        base_url=settings.azure_embed_endpoint,
        api_key=settings.azure_api_key.get_secret_value(),
    )

def read_pdf_page(id: int, path: Path, i: int, page: PageObject) -> dict[str, Any]:
    text = page.extract_text().strip() or ""
    if not text:
        return
    return {"source_id":id, "source": path.name, "page": i, "text": text}

def read_pdf(id: int, path: Path) -> list[dict[str, Any]]:
    reader = PdfReader(str(path))
    pages = [read_pdf_page(id, path, i, page) for i, page in enumerate(reader.pages, start=1)]
    docs = [page for page in pages if page is not None]
    return docs

def read_text_file(id: int, path: Path) -> list[dict[str, Any]]:
    try:
        with open(path, mode="r") as f:
            text = f.read()
    except Exception as e:
        print(f"[WARN] Error with read file content {path}: {e}")
        return []

    if not text:
        return []

    return [
        {
            "source_id":id,
            "source": path.name,
            "page": 1,
            "text": text,
        }
    ]

def load_document(id: int, file_path: Path) -> list[dict[str, Any]]:
    if not file_path.is_file():
        print(f"[WARN] {file_path.name} is not a file")
        return
    
    suffix = file_path.suffix.lower()

    try:
        if suffix == ".pdf":
            return read_pdf(id, file_path)
        elif suffix in {'.txt', '.md'}:
            return read_text_file(id, file_path)
    except Exception as e:
        print(f"[WARN] Failed to read {file_path.name}: {e}")

def load_documents(data_dir: Path) -> list[dict[str, Any]]:
    documents = [load_document(id, path) for id, path in enumerate(sorted(data_dir.rglob("*")), start=1)]
    documents_pages = []
    [documents_pages.extend(doc) for doc in documents if doc is not None]
    return documents_pages

def get_chunks(source_id: int, source: str, page: int, chunk_index: int, piece: str) -> dict[str, Any]:
    piece = piece.strip()
    if not piece:
        return

    return {
        "source_id": source_id,
        "source": source,
        "page": page,
        "chunk_index": chunk_index,
        "text": piece
        }

def chunk_document(splitter: RecursiveCharacterTextSplitter, document: list[dict[str, Any]]) -> list[dict[str, Any]]:
    pieces = splitter.split_text(document["text"])
    chunks = [get_chunks(document["source_id"], document["source"], document["page"], chunk_index, piece) for chunk_index, piece in enumerate(pieces, start=1)]
    chunks = [chunk for chunk in chunks if chunk is not None]
    return chunks   

def chunk_documents(documents: list[dict[str, Any]]) -> list[dict[str, Any]]:
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=settings.chunk_size,
        chunk_overlap=settings.chunk_overlap,
        separators=["\n\n", "\n", ". ", " ", ""],
    )
    chunked_document = [chunk_document(splitter, document) for document in documents]
    chunks = []
    [chunks.extend(cd) for cd in chunked_document if cd is not None]
    chunks = [{"id": i , **chunk} for i, chunk in enumerate(chunks, start=1)]
    return chunks

def embed_texts(embed_client: OpenAI, texts: list[str]) -> list[list[float]]:
    vectors: list[list[float]] = []

    for start in range(0, len(texts), settings.embed_batch_size):
        batch = texts[start : start + settings.embed_batch_size]
        response = embed_client.embeddings.create(
            model=settings.azure_embed_model,
            input=batch,
        )
        vectors.extend(item.embedding for item in response.data)

    return vectors

def rebuild_qdrant_index(client: QdrantClient, chunks: list[dict[str, Any]], vectors: list[list[float]]) -> None:
    if not vectors:
        raise ValueError("No vectors were created. Check your documents in ./data")

    vector_size = len(vectors[0])

    if client.collection_exists(settings.collection_name):
        client.delete_collection(settings.collection_name)

    client.create_collection(
        collection_name=settings.collection_name,
        vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE)
    )

    points: list[PointStruct] = []
    for chunk, vector in zip(chunks, vectors, strict=True):
        payload = {
            "source_id": chunk["source_id"],
            "source": chunk["source"],
            "page": chunk["page"],
            "chunk_index": chunk["chunk_index"],
            "text": chunk["text"],
        }
        points.append(
            PointStruct(
                id=chunk["id"],
                vector=vector,
                payload=payload,
            )
        )

    for start in range(0, len(points), 256):
        batch = points[start : start + 256]
        client.upsert(
            collection_name=settings.collection_name,
            points=batch,
            wait=True,
        )

def save_chunks(chunks: list[dict[str, Any]]) -> None:
    Path(settings.qdrant_path).mkdir(parents=True, exist_ok=True)
    chunks_path = Path(settings.qdrant_path) / settings.chunk_file_name
    with chunks_path.open("w", encoding="utf-8") as f:
        json.dump(chunks, f, ensure_ascii=False, indent=2)

def main() -> None:
    source_data_path = Path(settings.data_dir)
    if not source_data_path.exists():
        raise FileNotFoundError(f"Data directory not found: {source_data_path.resolve()}")
    
    print(f"[INFO] Loading documents from: {source_data_path.resolve()}")
    documents = load_documents(source_data_path)
    print(f"[INFO] Loaded {max([doc['source_id'] for doc in documents])} documents with units: {len(documents)}")

    chunks = chunk_documents(documents)
    print(f"[INFO] Created chunks: {len(chunks)}")

    if not chunks:
        raise ValueError("No chunks were created. Check your input files.")
    
    texts = [chunk["text"] for chunk in chunks]
    embed_client = get_embed_client()
    vectors = embed_texts(embed_client, texts)
    print(f"[INFO] Created embeddings: {len(vectors)}")

    qdrant = QdrantClient(path=str(settings.qdrant_path))
    rebuild_qdrant_index(qdrant, chunks, vectors)
    save_chunks(chunks)

    print(f"[OK] Qdrant index stored in: {Path(settings.qdrant_path).resolve()}")
    print(f"[OK] Collection: {settings.collection_name}")
    print(f"[OK] Chunk metadata saved to: {(Path(settings.qdrant_path) / settings.chunk_file_name).resolve()}")

if __name__ == "__main__":
    main()