from __future__ import annotations

import hashlib
import json
import math
import re
from pathlib import Path
from typing import Any


DEFAULT_VECTOR_STORE_PATH = Path("data/rag/vector_store.json")
EMBEDDING_MODEL = "local_hashing_v1"
VECTOR_DIMENSIONS = 384


class LocalVectorStore:
    """Small persistent vector store for audit-standard RAG retrieval.

    The embedding is deterministic and local: it hashes Chinese character
    n-grams and ASCII tokens into a fixed-size vector, then uses cosine
    similarity. This keeps the MVP runnable without downloading models.
    """

    def __init__(
        self,
        store_path: Path | str = DEFAULT_VECTOR_STORE_PATH,
        dimensions: int = VECTOR_DIMENSIONS,
    ) -> None:
        self.store_path = Path(store_path)
        self.dimensions = dimensions

    def build_from_json(self, source_path: Path | str) -> list[dict[str, Any]]:
        source = Path(source_path)
        standards = json.loads(source.read_text(encoding="utf-8"))
        records = [self._record_from_standard(item) for item in standards]
        payload = {
            "embedding_model": EMBEDDING_MODEL,
            "dimensions": self.dimensions,
            "source_path": source.as_posix(),
            "records": records,
        }
        self.store_path.parent.mkdir(parents=True, exist_ok=True)
        self.store_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return records

    def search(self, query: str, limit: int = 3) -> list[dict[str, Any]]:
        payload = self._load()
        records = payload.get("records", [])
        if not records:
            return []

        query_vector = self.embed(query)
        scored: list[tuple[float, dict[str, Any]]] = []
        for record in records:
            score = cosine_similarity(query_vector, record.get("vector", []))
            if score > 0:
                item = {
                    "id": record["id"],
                    "title": record["title"],
                    "keywords": record.get("keywords", []),
                    "content": record["content"],
                    "similarity": round(score, 6),
                    "retrieval_mode": "vector",
                }
                scored.append((score, item))

        scored.sort(key=lambda pair: pair[0], reverse=True)
        return [item for _, item in scored[:limit]]

    def ensure_built(self, source_path: Path | str) -> None:
        if not self.store_path.exists():
            self.build_from_json(source_path)
            return

        try:
            payload = self._load()
        except Exception:
            self.build_from_json(source_path)
            return

        if (
            payload.get("embedding_model") != EMBEDDING_MODEL
            or payload.get("dimensions") != self.dimensions
            or not payload.get("records")
        ):
            self.build_from_json(source_path)

    def embed(self, text: str) -> list[float]:
        vector = [0.0] * self.dimensions
        for token in tokenize(text):
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            index = int.from_bytes(digest[:4], "big") % self.dimensions
            vector[index] += 1.0
        return normalize(vector)

    def _load(self) -> dict[str, Any]:
        return json.loads(self.store_path.read_text(encoding="utf-8"))

    def _record_from_standard(self, item: dict[str, Any]) -> dict[str, Any]:
        keywords = item.get("keywords", [])
        embedding_text = "\n".join(
            [
                str(item.get("title", "")),
                " ".join(str(keyword) for keyword in keywords),
                str(item.get("content", "")),
            ]
        )
        return {
            "id": item["id"],
            "title": item.get("title", item["id"]),
            "keywords": keywords,
            "content": item.get("content", ""),
            "embedding_model": EMBEDDING_MODEL,
            "vector": self.embed(embedding_text),
        }


def tokenize(text: str) -> list[str]:
    cleaned = re.sub(r"\s+", "", text.lower())
    tokens = re.findall(r"[a-z0-9_]+", text.lower())
    chinese_chars = [character for character in cleaned if "\u4e00" <= character <= "\u9fff"]
    for size in (1, 2, 3):
        tokens.extend(
            "".join(chinese_chars[index : index + size])
            for index in range(0, max(len(chinese_chars) - size + 1, 0))
        )
    return [token for token in tokens if token]


def normalize(vector: list[float]) -> list[float]:
    norm = math.sqrt(sum(value * value for value in vector))
    if norm == 0:
        return vector
    return [value / norm for value in vector]


def cosine_similarity(left: list[float], right: list[float]) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0
    return sum(left[index] * right[index] for index in range(len(left)))
