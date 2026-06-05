from __future__ import annotations

import hashlib
import json
import math
import re
import shutil
from pathlib import Path
from typing import Any


DEFAULT_VECTOR_STORE_PATH = Path("data/rag/chroma_db")
COLLECTION_NAME = "audit_standards"
EMBEDDING_MODEL = "local_hashing_v1"
VECTOR_DB_ENGINE = "chroma"
VECTOR_DIMENSIONS = 384


class LocalVectorStore:
    """Chroma-backed persistent vector store for audit-standard retrieval."""

    def __init__(
        self,
        store_path: Path | str = DEFAULT_VECTOR_STORE_PATH,
        dimensions: int = VECTOR_DIMENSIONS,
    ) -> None:
        """保存向量库路径和 embedding 维度配置。"""
        self.store_path = Path(store_path)
        self.dimensions = dimensions

    def build_from_json(self, source_path: Path | str) -> list[dict[str, Any]]:
        """从审计准则 JSON 构建持久化 Chroma 集合。"""
        source = Path(source_path)
        standards = json.loads(source.read_text(encoding="utf-8"))
        records = [self._record_from_standard(item) for item in standards]

        client = self._client()
        try:
            # 每次重建索引都先清空旧集合，避免旧版本 embedding 污染新检索结果。
            self._reset_collection(client)
            collection = self._get_collection(client)
            collection.add(
                ids=[record["id"] for record in records],
                documents=[record["content"] for record in records],
                metadatas=[
                    {
                        "title": record["title"],
                        "keywords_json": json.dumps(record["keywords"], ensure_ascii=False),
                        "embedding_model": record["embedding_model"],
                        "source_path": source.as_posix(),
                    }
                    for record in records
                ],
                embeddings=[record["vector"] for record in records],
            )
            self._write_manifest(source, len(records))
        finally:
            client.close()
        return records

    def search(self, query: str, limit: int = 3) -> list[dict[str, Any]]:
        """按查询文本检索最相近的审计准则，并返回带相似度的结果。"""
        client = self._client()
        try:
            collection = self._get_collection(client)
            if collection.count() == 0:
                return []

            # 这里仍然使用本地 hashing embedding，只是把持久化和检索交给 Chroma。
            result = collection.query(
                query_embeddings=[self.embed(query)],
                n_results=limit,
                include=["metadatas", "documents", "distances"],
            )
            ids = result.get("ids", [[]])[0]
            documents = result.get("documents", [[]])[0]
            metadatas = result.get("metadatas", [[]])[0]
            distances = result.get("distances", [[]])[0]

            items: list[dict[str, Any]] = []
            for item_id, document, metadata, distance in zip(ids, documents, metadatas, distances):
                similarity = max(0.0, 1.0 - float(distance))
                if similarity <= 0:
                    continue
                items.append(
                    {
                        "id": item_id,
                        "title": metadata.get("title", item_id),
                        "keywords": self._load_keywords(metadata.get("keywords_json", "[]")),
                        "content": document,
                        "similarity": round(similarity, 6),
                        "retrieval_mode": "chroma_vector",
                        "vector_db": VECTOR_DB_ENGINE,
                    }
                )
            return items
        finally:
            client.close()

    def ensure_built(self, source_path: Path | str) -> None:
        """确保向量库已存在且 manifest 与当前配置一致，否则自动重建。"""
        source = Path(source_path)
        manifest = self._load_manifest()
        if not manifest:
            self.build_from_json(source)
            return

        # manifest 用来判断“当前磁盘索引是否和代码预期一致”。
        if (
            manifest.get("vector_db") != VECTOR_DB_ENGINE
            or manifest.get("embedding_model") != EMBEDDING_MODEL
            or manifest.get("dimensions") != self.dimensions
            or manifest.get("source_path") != source.as_posix()
            or manifest.get("record_count", 0) <= 0
        ):
            self.build_from_json(source)
            return

        try:
            client = self._client()
            try:
                if self._get_collection(client).count() <= 0:
                    self.build_from_json(source)
            finally:
                client.close()
        except Exception:
            self.build_from_json(source)

    def embed(self, text: str) -> list[float]:
        """把文本转换为可复现的 hashing 向量，适合离线演示环境。"""
        # 采用可复现的本地向量化方案，保证答辩和离线环境也能稳定运行。
        vector = [0.0] * self.dimensions
        for token in tokenize(text):
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            index = int.from_bytes(digest[:4], "big") % self.dimensions
            vector[index] += 1.0
        return normalize(vector)

    def _client(self):
        """创建 Chroma 持久化客户端，并在缺依赖时给出明确错误。"""
        try:
            import chromadb
        except ImportError as exc:
            raise RuntimeError("chromadb is not installed") from exc

        self.store_path.mkdir(parents=True, exist_ok=True)
        return chromadb.PersistentClient(path=str(self.store_path))

    def _get_collection(self, client):
        """获取或创建统一的审计准则集合。"""
        return client.get_or_create_collection(
            name=COLLECTION_NAME,
            metadata={
                "vector_db": VECTOR_DB_ENGINE,
                "embedding_model": EMBEDDING_MODEL,
                "dimensions": self.dimensions,
                "hnsw:space": "cosine",
            },
        )

    def _reset_collection(self, client) -> None:
        """删除旧集合和 manifest，为完整重建索引做准备。"""
        try:
            client.delete_collection(COLLECTION_NAME)
        except Exception:
            pass
        self._delete_manifest()

    def _manifest_path(self) -> Path:
        """返回本地索引 manifest 文件路径。"""
        return self.store_path / "manifest.json"

    def _write_manifest(self, source: Path, record_count: int) -> None:
        """写入索引元信息，用于后续判断是否需要重建。"""
        payload = {
            "vector_db": VECTOR_DB_ENGINE,
            "embedding_model": EMBEDDING_MODEL,
            "dimensions": self.dimensions,
            "source_path": source.as_posix(),
            "record_count": record_count,
            "collection_name": COLLECTION_NAME,
        }
        self._manifest_path().write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def _load_manifest(self) -> dict[str, Any]:
        """读取索引 manifest；不存在时返回空字典。"""
        manifest_path = self._manifest_path()
        if not manifest_path.exists():
            return {}
        return json.loads(manifest_path.read_text(encoding="utf-8"))

    def _delete_manifest(self) -> None:
        """删除 manifest，配合集合重建保持状态一致。"""
        manifest_path = self._manifest_path()
        if manifest_path.exists():
            manifest_path.unlink()

    def _record_from_standard(self, item: dict[str, Any]) -> dict[str, Any]:
        """把一条审计准则转换为 Chroma 可写入的标准记录。"""
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

    def clear(self) -> None:
        """清空本地向量库目录，主要用于测试或手动重置。"""
        if self.store_path.exists():
            shutil.rmtree(self.store_path)

    @staticmethod
    def _load_keywords(value: str) -> list[str]:
        """从 metadata 中恢复关键词列表，异常时返回空列表。"""
        try:
            loaded = json.loads(value)
        except json.JSONDecodeError:
            return []
        if isinstance(loaded, list):
            return [str(item) for item in loaded]
        return []


def tokenize(text: str) -> list[str]:
    """为 hashing embedding 生成中英文混合 token。"""
    # 中文按字/2-gram/3-gram 切片，英文和数字按 token 保留，兼顾中英混合材料。
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
    """对向量做 L2 归一化，零向量保持原样。"""
    norm = math.sqrt(sum(value * value for value in vector))
    if norm == 0:
        return vector
    return [value / norm for value in vector]
