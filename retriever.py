from qdrant_client import QdrantClient
from config import Settings
from openai import OpenAI
from pathlib import Path
from typing import Any
from rank_bm25 import BM25Okapi
import json
import cohere


"""
Hybrid retrieval module.

Combines semantic search (vector DB) + BM25 (lexical) + cross-encoder reranking.
"""
import re

def tokenize(text: str) -> list[str]:
    return re.findall(r"\w+", text.lower())

class HybridRetriever:
    def __init__(self) -> None:
        self.settings = Settings()
        self.embed_client = OpenAI(
            base_url=self.settings.azure_embed_endpoint,
            api_key=self.settings.azure_api_key.get_secret_value()
            )
        self.qdrant = QdrantClient(path=self.settings.qdrant_path)
        self.reranker = cohere.ClientV2(
            base_url=self.settings.azure_rerank_endpoint,
            api_key=self.settings.azure_api_key.get_secret_value()
        )

        self.chunks_path = Path(self.settings.qdrant_path) / self.settings.chunk_file_name

        with self.chunks_path.open("r", encoding="utf-8") as f:
            self.chunks = json.load(f)

        self.bm25 = BM25Okapi([tokenize(item["text"]) for item in self.chunks])
        self.chunk_ids = [int(item["id"]) for item in self.chunks]
        self.chunk_by_id = {int(item["id"]): item for item in self.chunks}

    def embed_query(self, query: str) -> list[float]:
        response = self.embed_client.embeddings.create(
            model=self.settings.azure_embed_model,
            input=[query],
        )
        return response.data[0].embedding

    def semantic_search(self, query: str, top_k: int) -> list[dict[str, Any]]:
        query_vector = self.embed_query(query)
        hits = self.qdrant.query_points(
            collection_name=self.settings.collection_name,
            query=query_vector,
            limit=top_k,
            with_payload=True,
        )

        results: list[dict[str, Any]] = []
        for rank, point in enumerate(hits.points, start=1):
            payload = point.payload or {}
            results.append(
                {
                    "id": int(point.id),
                    "source_id": payload.get("source_id"),
                    "source": payload.get("source"),
                    "page": payload.get("page"),
                    "chunk_index": payload.get("chunk_index"),
                    "text": payload.get("text"),
                    "semantic_score": float(point.score),
                    "semantic_rank": rank,
                }
            )
        return results

    def bm25_search(self, query: str, top_k: int) -> list[dict[str, Any]]:
        tokenized_query = tokenize(query)
        scores = self.bm25.get_scores(tokenized_query)

        ranked = sorted(
            zip(self.chunk_ids, scores, strict=True),
            key=lambda x: x[1],
            reverse=True,
        )[:top_k]

        results: list[dict[str, Any]] = []
        for rank, (chunk_id, score) in enumerate(ranked, start=1):
            item = self.chunk_by_id[int(chunk_id)]
            results.append(
                {
                    "id": int(chunk_id),
                    "text": item["text"],
                    "source": item["source"],
                    "page": item.get("page"),
                    "chunk_index": item.get("chunk_index"),
                    "bm25_score": float(score),
                    "bm25_rank": rank,
                }
            )
        return results
    
    def fuse_results(self, semantic_results: list[dict[str, Any]], bm25_results: list[dict[str, Any]]) -> list[dict[str, Any]]:
        fused: list[dict[str, Any]] = []

        for item in semantic_results:
            item["bm25_score"]=None
            item["bm25_rank"]=None
            fused.append(item)

        for item in bm25_results:
            index = next((i for i, f_item in enumerate(fused) if f_item.get("id") == item['id']), None)
            if index is not None:
                fused[index]["bm25_score"] = item["bm25_score"]
                fused[index]["bm25_rank"] = item["bm25_rank"]
            else:
                item["semantic_score"]=None
                item["semantic_rank"]=None
                fused.append(item)

        return fused

    def rerank(self, query: str, candidates: list[dict[str, Any]], top_n: int) -> list[dict[str, Any]]:
        if not candidates:
            return []

        documents = [item["text"] for item in candidates]

        rerank_scores = self.reranker.rerank(
            model=self.settings.azure_rerank_model,
            query=query,
            documents=documents,
            top_n=top_n,
        )

        items = [item.index for item in rerank_scores.results]
        scores = [item.relevance_score for item in rerank_scores.results]
        candidates = [candidates[i] for i in items]

        reranked: list[dict[str, Any]] = []
        for item, score in zip(candidates, scores, strict=True):
            enriched = dict(item)
            enriched["rerank_score"] = score
            reranked.append(enriched)

        reranked.sort(key=lambda x: x["rerank_score"], reverse=True)
        return reranked      

    def search(self, query: str) -> list[dict[str, Any]]:
        top_k = self.settings.retrieval_top_k
        top_n = self.settings.rerank_top_n
        semantic = self.semantic_search(query, top_k=top_k)
        bm25 = self.bm25_search(query, top_k=top_k)
        fused = self.fuse_results(semantic, bm25)
        return self.rerank(query, fused, top_n=top_n)

    def format_output(self, results: list[dict[str, Any]]) -> str:

        lines = [f"[{len(results)} documents found:]"]

        for item in results:
            source = item.get("source")
            page = item.get("page")
            page_part = item.get("chunk_index")
            rerank_score = item.get("rerank_score")
            lines.append(f"- [SOURCE: {source} PAGE: {page} PAGE PART: {page_part} SCORE: {rerank_score:.4f}]")
            
            snippet = item.get("text")
            lines.append(f"\t{snippet}")

        return "\n".join(lines)
    
    def info_output(self, results: list[dict[str, Any]]) -> str:

        lines = [f"Founed {len(results)}  chunks in local knowledge database"]

        for item in results:
            source = item.get("source")
            page = item.get("page")
            page_part = item.get("chunk_index")
            rerank_score = item.get("rerank_score")
            lines.append(f"- [SOURCE: {source} PAGE: {page} PAGE PART: {page_part} SCORE: {rerank_score:.4f}]")            

        return "\n".join(lines)