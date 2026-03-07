"""
app/dependencies.py — FastAPI 依赖注入

提供 Milvus/Chroma Retriever、Embedder、HybridRetriever 的单例管理。
支持切换向量存储后端。

Author: 帕托莉 🐱
"""

from __future__ import annotations

import logging
import threading

from pymilvus import DataType

from app.rag_config import Settings, VectorStoreBackend, settings
from app.bge_embedder import (
    BaseEmbedder,
    BGEEmbedder,
    MockEmbedder,
    get_embedder,
    reset_embedder,
    set_embedder,
)
from app.retriever.base import BaseRetriever, RetrievedChunk

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════════
# 单例锁
# ═══════════════════════════════════════════════════════════════════════════════════

_singleton_lock = threading.Lock()


# ═══════════════════════════════════════════════════════════════════════════════════
# Milvus Retriever 单例
# ═══════════════════════════════════════════════════════════════════════════════════

_milvus_retriever_instance: "MilvusRetrieverWrapper | None" = None


class MilvusRetrieverWrapper:
    """
    Milvus Retriever 包装器
    
    提供与 BaseRetriever 兼容的接口，同时支持 Milvus 特有的功能。
    """
    
    def __init__(self, config: Settings):
        self.config = config
        self._retriever = None
        self._sparse_generators: dict[str, "SparseVectorGenerator"] = {}
        self._connected = False
    
    def connect(self):
        """建立 Milvus 连接"""
        if self._connected:
            return

        from pymilvus import MilvusClient
        import os

        # 支持 Milvus Server 模式
        uri = self.config.milvus_uri
        if not uri:
            # 空 URI 时使用 host:port 构造
            uri = f"http://{self.config.milvus_host}:{self.config.milvus_port}"

        logger.info(f"Connecting to Milvus Server: {uri}")

        self._client = MilvusClient(
            uri=uri,
            user=self.config.milvus_user or None,
            password=self.config.milvus_password or None,
        )
        self._connected = True
        logger.info("Milvus connected")
    
    def _ensure_collection(self, tenant_id: str, kb_id: str):
        """确保 Collection 存在"""
        collection_name = f"nexus_{tenant_id}_{kb_id}"

        # 检查是否已存在
        try:
            collections = self._client.list_collections()
            if collection_name in collections:
                return collection_name
        except Exception:
            pass

        logger.info(f"Creating collection: {collection_name}")

        # 使用 MilvusClient 简化的 Schema 创建
        # Milvus Lite 模式下，索引会自动创建
        schema = self._client.create_schema(
            auto_id=False,
            enable_dynamic_field=True,
        )

        schema.add_field(field_name="chunk_id", datatype=DataType.VARCHAR, max_length=256, is_primary=True)
        schema.add_field(field_name="doc_id", datatype=DataType.VARCHAR, max_length=256)
        schema.add_field(field_name="content", datatype=DataType.VARCHAR, max_length=65535)
        schema.add_field(field_name="metadata", datatype=DataType.JSON)
        schema.add_field(
            field_name="dense_vector",
            datatype=DataType.FLOAT_VECTOR,
            dim=self.config.embedding_dim,
        )
        schema.add_field(field_name="tenant_id", datatype=DataType.VARCHAR, max_length=64)

        # 添加稀疏向量字段 (Milvus Lite 2.5+ 支持)
        if self.config.use_sparse_vector:
            schema.add_field(
                field_name="sparse_vector",
                datatype=DataType.SPARSE_FLOAT_VECTOR,
            )

        # 设置索引参数
        index_params = self._client.prepare_index_params()
        index_params.add_index(
            field_name="dense_vector",
            index_type="IVF_FLAT",
            metric_type=self.config.milvus_metric_dense,
            params={"nlist": 128}
        )

        # 稀疏向量索引
        if self.config.use_sparse_vector:
            index_params.add_index(
                field_name="sparse_vector",
                index_type="SPARSE_INVERTED_INDEX",
                metric_type="IP",
            )

        self._client.create_collection(
            collection_name=collection_name,
            schema=schema,
            index_params=index_params,
        )

        logger.info(f"Collection created: {collection_name}")
        return collection_name
    
    def add_chunks(
        self,
        tenant_id: str,
        kb_id: str,
        chunk_ids: list[str],
        doc_ids: list[str],
        contents: list[str],
        embeddings: list[list[float]],
        metadatas: list[dict],
    ) -> None:
        """写入 chunks (支持稠密+稀疏向量)"""
        if not self._connected:
            self.connect()

        collection_name = self._ensure_collection(tenant_id, kb_id)

        # 生成稀疏向量
        sparse_vectors = None
        if self.config.use_sparse_vector:
            key = f"{tenant_id}:{kb_id}"

            # 获取或创建稀疏向量生成器
            if key not in self._sparse_generators:
                self._sparse_generators[key] = SparseVectorGenerator(
                    min_df=self.config.sparse_min_df,
                    max_df=self.config.sparse_max_df,
                    norm=self.config.sparse_norm,
                )

            generator = self._sparse_generators[key]

            # Fit 生成器 (包括现有文档 + 新文档)
            existing = self.get_all_chunks(tenant_id, kb_id)
            all_contents = [c.content for c in existing] + contents
            generator.fit(all_contents)

            sparse_vectors = generator.transform(contents)

        # 准备实体
        entities = []
        for i in range(len(chunk_ids)):
            entity = {
                "chunk_id": chunk_ids[i],
                "doc_id": doc_ids[i],
                "content": contents[i],
                "metadata": metadatas[i],
                "dense_vector": embeddings[i],
                "tenant_id": tenant_id,
            }
            if sparse_vectors:
                entity["sparse_vector"] = sparse_vectors[i]
            entities.append(entity)

        # 插入
        self._client.insert(collection_name=collection_name, data=entities)

        logger.info(f"Added {len(chunk_ids)} chunks to {tenant_id}/{kb_id}")
    
    def vector_search(
        self,
        tenant_id: str,
        kb_id: str,
        query_embedding: list[float],
        top_k: int,
    ) -> list[RetrievedChunk]:
        """向量搜索 (兼容 BaseRetriever 接口)"""
        return self.hybrid_search(
            tenant_id=tenant_id,
            kb_id=kb_id,
            query_text="",
            query_embedding=query_embedding,
            top_k=top_k,
            use_sparse=False,
            use_rerank=False,
        )
    
    def hybrid_search(
        self,
        tenant_id: str,
        kb_id: str,
        query_text: str,
        query_embedding: list[float],
        top_k: int,
        use_sparse: bool = True,  # 启用稀疏向量
        use_rerank: bool = True,
    ) -> list[RetrievedChunk]:
        """Milvus 混合搜索（稠密向量 + 稀疏向量 + RRF 融合 + Rerank）"""
        if not self._connected:
            self.connect()

        collection_name = f"nexus_{tenant_id}_{kb_id}"

        # 检查 Collection 是否存在
        try:
            collections = self._client.list_collections()
            if collection_name not in collections:
                return []
        except Exception:
            return []

        candidate_k = top_k * 3 if use_rerank else top_k

        # ════════════════════════════════════════════════════════════════════════════
        # 1. 稠密向量搜索
        # ════════════════════════════════════════════════════════════════════════════
        dense_results = []

        try:
            results = self._client.search(
                collection_name=collection_name,
                data=[query_embedding],
                limit=candidate_k,
                output_fields=["chunk_id", "doc_id", "content", "metadata"],
                search_params={
                    "metric_type": self.config.milvus_metric_dense,
                    "params": {},
                },
            )

            if results and len(results) > 0:
                for rank, r in enumerate(results[0]):
                    dense_results.append({
                        "chunk_id": r["entity"]["chunk_id"],
                        "doc_id": r["entity"]["doc_id"],
                        "content": r["entity"]["content"],
                        "metadata": r["entity"].get("metadata", {}),
                        "dense_rank": rank,
                        "dense_score": r["distance"],
                    })
        except Exception as e:
            logger.error(f"Dense search failed: {e}")

        # ════════════════════════════════════════════════════════════════════════════
        # 2. 稀疏向量搜索
        # ════════════════════════════════════════════════════════════════════════════
        sparse_results = []

        if use_sparse and self.config.use_sparse_vector and query_text:
            key = f"{tenant_id}:{kb_id}"
            generator = self._sparse_generators.get(key)

            if generator and generator._vocab:
                try:
                    sparse_vector = generator.encode_query(query_text)

                    if sparse_vector["indices"]:
                        results = self._client.search(
                            collection_name=collection_name,
                            data=[sparse_vector],
                            limit=candidate_k,
                            output_fields=["chunk_id", "doc_id", "content", "metadata"],
                            anns_field="sparse_vector",
                            search_params={
                                "metric_type": "IP",
                                "params": {},
                            },
                        )

                        if results and len(results) > 0:
                            for rank, r in enumerate(results[0]):
                                sparse_results.append({
                                    "chunk_id": r["entity"]["chunk_id"],
                                    "doc_id": r["entity"]["doc_id"],
                                    "content": r["entity"]["content"],
                                    "metadata": r["entity"].get("metadata", {}),
                                    "sparse_rank": rank,
                                    "sparse_score": r["distance"],
                                })
                except Exception as e:
                    logger.warning(f"Sparse search failed: {e}")

        # ════════════════════════════════════════════════════════════════════════════
        # 3. RRF 融合
        # ════════════════════════════════════════════════════════════════════════════
        if not dense_results and not sparse_results:
            return []

        # 合并结果
        chunk_map = {}
        for r in dense_results:
            chunk_map[r["chunk_id"]] = r.copy()

        for r in sparse_results:
            if r["chunk_id"] in chunk_map:
                chunk_map[r["chunk_id"]]["sparse_rank"] = r["sparse_rank"]
                chunk_map[r["chunk_id"]]["sparse_score"] = r["sparse_score"]
            else:
                chunk_map[r["chunk_id"]] = r.copy()

        # 计算 RRF 分数
        k = self.config.rrf_k
        for chunk_id, r in chunk_map.items():
            rrf_score = 0.0
            if "dense_rank" in r:
                rrf_score += self.config.dense_weight / (k + r["dense_rank"] + 1)
            if "sparse_rank" in r:
                rrf_score += self.config.sparse_weight / (k + r["sparse_rank"] + 1)
            r["rrf_score"] = rrf_score

        sorted_results = sorted(chunk_map.values(), key=lambda x: -x["rrf_score"])

        # ════════════════════════════════════════════════════════════════════════════
        # 4. Re-Rank (可选)
        # ════════════════════════════════════════════════════════════════════════════
        if use_rerank and self.config.use_reranker and query_text and sorted_results:
            try:
                from sentence_transformers import CrossEncoder

                # 使用 CrossEncoder 进行 rerank
                reranker = CrossEncoder(self.config.reranker_model)
                docs = [r["content"] for r in sorted_results[:self.config.reranker_top_k]]
                pairs = [[query_text, doc] for doc in docs]

                rerank_scores = reranker.predict(pairs)

                for i, r in enumerate(sorted_results[:len(docs)]):
                    r["rerank_score"] = float(rerank_scores[i])

                sorted_results = sorted(
                    sorted_results[:len(docs)],
                    key=lambda x: -x.get("rerank_score", x["rrf_score"])
                )
            except Exception as e:
                logger.warning(f"Rerank failed: {e}")

        # 构建返回结果
        return [
            RetrievedChunk(
                chunk_id=r["chunk_id"],
                doc_id=r["doc_id"],
                content=r["content"],
                score=r.get("rerank_score", r["rrf_score"]),
                metadata=r["metadata"],
            )
            for r in sorted_results[:top_k]
        ]
    
    def get_all_chunks(self, tenant_id: str, kb_id: str) -> list[RetrievedChunk]:
        """获取所有 chunks"""
        if not self._connected:
            self.connect()

        collection_name = f"nexus_{tenant_id}_{kb_id}"

        # 检查 Collection 是否存在
        try:
            collections = self._client.list_collections()
            if collection_name not in collections:
                return []
        except Exception:
            return []

        try:
            results = self._client.query(
                collection_name=collection_name,
                output_fields=["chunk_id", "doc_id", "content", "metadata"],
                limit=10000,
            )

            return [
                RetrievedChunk(
                    chunk_id=r["chunk_id"],
                    doc_id=r["doc_id"],
                    content=r["content"],
                    score=1.0,
                    metadata=r.get("metadata", {}),
                )
                for r in results
            ]
        except Exception as e:
            logger.error(f"Query failed: {e}")
            return []
    
    def delete_doc(self, tenant_id: str, kb_id: str, doc_id: str) -> None:
        """删除文档"""
        if not self._connected:
            self.connect()

        collection_name = f"nexus_{tenant_id}_{kb_id}"

        try:
            self._client.delete(
                collection_name=collection_name,
                filter=f'doc_id == "{doc_id}"',
            )
            logger.info(f"Deleted doc {doc_id} from {tenant_id}/{kb_id}")
        except Exception as e:
            logger.error(f"Delete failed: {e}")
    
    def count(self, tenant_id: str, kb_id: str) -> int:
        """返回 chunk 总数"""
        if not self._connected:
            self.connect()

        collection_name = f"nexus_{tenant_id}_{kb_id}"

        try:
            # 使用 query 来获取数量
            results = self._client.query(
                collection_name=collection_name,
                output_fields=["chunk_id"],
                limit=10000,
            )
            return len(results)
        except Exception:
            return 0


# ═══════════════════════════════════════════════════════════════════════════════════
# 稀疏向量生成器 (内联避免循环导入)
# ═══════════════════════════════════════════════════════════════════════════════════

class SparseVectorGenerator:
    """TF-IDF 稀疏向量生成器"""
    
    def __init__(self, min_df: int = 1, max_df: float = 0.95, norm: str = "l2"):
        self.min_df = min_df
        self.max_df = max_df
        self.norm = norm
        self._vocab: dict[str, int] = {}
        self._idf: dict[str, float] = {}
        self._doc_count: int = 0
    
    def fit(self, documents: list[str]) -> "SparseVectorGenerator":
        import re
        import numpy as np
        
        self._doc_count = len(documents)
        doc_freq: dict[str, int] = {}
        
        for doc in documents:
            tokens = self._tokenize(doc)
            for token in set(tokens):
                doc_freq[token] = doc_freq.get(token, 0) + 1
        
        self._vocab = {}
        vocab_idx = 0
        for token, df in doc_freq.items():
            if self.min_df <= df <= self.max_df * self._doc_count:
                self._vocab[token] = vocab_idx
                vocab_idx += 1
        
        for token, df in doc_freq.items():
            if token in self._vocab:
                self._idf[token] = np.log((self._doc_count + 1) / (df + 1)) + 1
        
        logger.debug(f"SparseVectorGenerator: vocab_size={len(self._vocab)}")
        return self
    
    def transform(self, documents: list[str]) -> list[dict]:
        import numpy as np
        
        sparse_vectors = []
        
        for doc in documents:
            tokens = self._tokenize(doc)
            
            term_freq: dict[str, float] = {}
            for token in tokens:
                if token in self._vocab:
                    term_freq[token] = term_freq.get(token, 0) + 1
            
            indices = []
            values = []
            tfidf_sum = 0.0
            
            for token, tf in term_freq.items():
                idf = self._idf.get(token, 0)
                tfidf = tf * idf
                indices.append(self._vocab[token])
                values.append(tfidf)
                tfidf_sum += tfidf ** 2
            
            if self.norm == "l2" and tfidf_sum > 0:
                norm_factor = np.sqrt(tfidf_sum)
                values = [v / norm_factor for v in values]
            
            sparse_vectors.append({"indices": indices, "values": values})
        
        return sparse_vectors
    
    def encode_query(self, query: str) -> dict:
        import numpy as np
        
        tokens = self._tokenize(query)
        
        term_freq: dict[str, float] = {}
        for token in tokens:
            if token in self._vocab:
                term_freq[token] = term_freq.get(token, 0) + 1
        
        indices = []
        values = []
        tfidf_sum = 0.0
        
        for token, tf in term_freq.items():
            idf = self._idf.get(token, 0)
            tfidf = tf * idf
            indices.append(self._vocab[token])
            values.append(tfidf)
            tfidf_sum += tfidf ** 2
        
        if self.norm == "l2" and tfidf_sum > 0:
            norm_factor = np.sqrt(tfidf_sum)
            values = [v / norm_factor for v in values]
        
        return {"indices": indices, "values": values}
    
    def _tokenize(self, text: str) -> list[str]:
        import re
        
        tokens = []
        for char in text:
            if "\u4e00" <= char <= "\u9fff":
                tokens.append(char)
        words = re.findall(r'[a-zA-Z0-9]+', text.lower())
        tokens.extend(words)
        return tokens or [text]


# ═══════════════════════════════════════════════════════════════════════════════════
# 全局 Retriever 单例
# ═══════════════════════════════════════════════════════════════════════════════════

_retriever_instance: BaseRetriever | None = None
_hybrid_instance: "HybridRetrieverWrapper | None" = None


def get_milvus_retriever() -> MilvusRetrieverWrapper:
    """获取 Milvus Retriever 单例"""
    global _retriever_instance

    if _retriever_instance is None:
        with _singleton_lock:
            if _retriever_instance is None:
                # 根据配置选择后端
                if settings.vector_store_backend == VectorStoreBackend.CHROMA:
                    logger.info("Using ChromaDB backend")
                    _retriever_instance = ChromaRetrieverWrapper(settings)
                else:
                    logger.info("Using Milvus backend")
                    _retriever_instance = MilvusRetrieverWrapper(settings)
                    _retriever_instance.connect()

    return _retriever_instance


class ChromaRetrieverWrapper:
    """ChromaDB Retriever 包装器 - 与 MilvusRetrieverWrapper 接口兼容"""

    def __init__(self, config: Settings):
        self.config = config
        import chromadb

        # 使用持久化模式
        import os
        persist_dir = config.chroma_persist_directory
        os.makedirs(persist_dir, exist_ok=True)
        self._client = chromadb.PersistentClient(path=persist_dir)
        self._sparse_generators: dict[str, SparseVectorGenerator] = {}
        logger.info(f"ChromaDB initialized: {persist_dir}")

    def _get_collection(self, tenant_id: str, kb_id: str):
        """获取或创建 Collection"""
        import re
        # 清洗名称
        def safe_name(s: str) -> str:
            cleaned = re.sub(r"[^a-zA-Z0-9._-]", "-", s)
            cleaned = cleaned.strip("-._")
            return cleaned[:60] or "x"

        name = f"nexus-{safe_name(tenant_id)}-{safe_name(kb_id)}"
        return self._client.get_or_create_collection(
            name=name,
            metadata={"hnsw:space": "cosine"},
        )

    def add_chunks(
        self,
        tenant_id: str,
        kb_id: str,
        chunk_ids: list[str],
        doc_ids: list[str],
        contents: list[str],
        embeddings: list[list[float]],
        metadatas: list[dict],
    ) -> None:
        """写入 chunks"""
        if not chunk_ids:
            return

        col = self._get_collection(tenant_id, kb_id)

        # 为稀疏向量生成器学习词汇
        if self.config.use_sparse_vector:
            key = f"{tenant_id}:{kb_id}"
            if key not in self._sparse_generators:
                self._sparse_generators[key] = SparseVectorGenerator()

            generator = self._sparse_generators[key]
            # 获取现有文档
            existing = self.get_all_chunks(tenant_id, kb_id)
            all_contents = [c.content for c in existing] + contents
            generator.fit(all_contents)

        # 准备 metadata
        enriched_meta = []
        for i, meta in enumerate(metadatas):
            m = dict(meta)
            m["tenant_id"] = tenant_id
            m["kb_id"] = kb_id
            m["doc_id"] = doc_ids[i]
            # ChromaDB metadata 只支持 str/int/float/bool
            cleaned = {
                k: v if isinstance(v, (str, int, float, bool)) else str(v)
                for k, v in m.items()
            }
            enriched_meta.append(cleaned)

        col.add(
            ids=chunk_ids,
            embeddings=embeddings,
            documents=contents,
            metadatas=enriched_meta,
        )

        logger.info(f"Added {len(chunk_ids)} chunks to {tenant_id}/{kb_id}")

    def vector_search(
        self,
        tenant_id: str,
        kb_id: str,
        query_embedding: list[float],
        top_k: int,
    ) -> list[RetrievedChunk]:
        """向量搜索"""
        return self.hybrid_search(
            tenant_id=tenant_id,
            kb_id=kb_id,
            query_text="",
            query_embedding=query_embedding,
            top_k=top_k,
            use_sparse=False,
            use_rerank=False,
        )

    def hybrid_search(
        self,
        tenant_id: str,
        kb_id: str,
        query_text: str,
        query_embedding: list[float],
        top_k: int,
        use_sparse: bool = True,
        use_rerank: bool = True,
    ) -> list[RetrievedChunk]:
        """混合搜索（向量 + BM25 + RRF + Rerank）"""
        col = self._get_collection(tenant_id, kb_id)

        n = col.count()
        if n == 0:
            return []

        candidate_k = min(top_k * 3 if use_rerank else top_k, n)

        # 1. 向量搜索
        result = col.query(
            query_embeddings=[query_embedding],
            n_results=candidate_k,
            include=["documents", "metadatas", "distances"],
        )

        dense_results = []
        ids = result["ids"][0]
        docs = result["documents"][0]
        metas = result["metadatas"][0]
        dists = result["distances"][0]

        for rank, (cid, doc, meta, dist) in enumerate(zip(ids, docs, metas, dists)):
            dense_results.append({
                "chunk_id": cid,
                "doc_id": meta.get("doc_id", ""),
                "content": doc,
                "metadata": {k: v for k, v in meta.items() if k not in ("tenant_id", "kb_id", "doc_id")},
                "dense_rank": rank,
                "dense_score": max(0.0, 1.0 - dist / 2.0),  # cosine 距离转相似度
            })

        # 2. 稀疏向量搜索（BM25 模拟）
        sparse_results = []
        if use_sparse and self.config.use_sparse_vector and query_text:
            key = f"{tenant_id}:{kb_id}"
            generator = self._sparse_generators.get(key)

            if generator and generator._vocab:
                # 简单的 BM25 模拟：计算查询词与文档的重叠度
                query_tokens = set(generator._tokenize(query_text))

                for rank, r in enumerate(dense_results):
                    doc_tokens = set(generator._tokenize(r["content"]))
                    overlap = len(query_tokens & doc_tokens)
                    if overlap > 0:
                        sparse_results.append({
                            **r,
                            "sparse_rank": rank,
                            "sparse_score": overlap / len(query_tokens),
                        })

        # 3. RRF 融合
        chunk_map = {}
        for r in dense_results:
            chunk_map[r["chunk_id"]] = r.copy()

        for r in sparse_results:
            if r["chunk_id"] in chunk_map:
                chunk_map[r["chunk_id"]]["sparse_rank"] = r["sparse_rank"]
                chunk_map[r["chunk_id"]]["sparse_score"] = r["sparse_score"]

        k = self.config.rrf_k
        for chunk_id, r in chunk_map.items():
            rrf_score = 0.0
            if "dense_rank" in r:
                rrf_score += self.config.dense_weight / (k + r["dense_rank"] + 1)
            if "sparse_rank" in r:
                rrf_score += self.config.sparse_weight / (k + r["sparse_rank"] + 1)
            r["rrf_score"] = rrf_score

        sorted_results = sorted(chunk_map.values(), key=lambda x: -x["rrf_score"])

        # 4. Rerank
        if use_rerank and self.config.use_reranker and query_text and sorted_results:
            try:
                from sentence_transformers import CrossEncoder

                reranker = CrossEncoder(self.config.reranker_model)
                docs = [r["content"] for r in sorted_results[:self.config.reranker_top_k]]
                pairs = [[query_text, doc] for doc in docs]

                rerank_scores = reranker.predict(pairs)

                for i, r in enumerate(sorted_results[:len(docs)]):
                    r["rerank_score"] = float(rerank_scores[i])

                sorted_results = sorted(
                    sorted_results[:len(docs)],
                    key=lambda x: -x.get("rerank_score", x["rrf_score"])
                )
            except Exception as e:
                logger.warning(f"Rerank failed: {e}")

        # 构建返回结果
        return [
            RetrievedChunk(
                chunk_id=r["chunk_id"],
                doc_id=r["doc_id"],
                content=r["content"],
                score=r.get("rerank_score", r["rrf_score"]),
                metadata=r["metadata"],
            )
            for r in sorted_results[:top_k]
        ]

    def get_all_chunks(self, tenant_id: str, kb_id: str) -> list[RetrievedChunk]:
        """获取所有 chunks"""
        col = self._get_collection(tenant_id, kb_id)
        n = col.count()
        if n == 0:
            return []

        result = col.get(
            include=["documents", "metadatas"],
            limit=n,
        )

        chunks = []
        for cid, doc, meta in zip(result["ids"], result["documents"], result["metadatas"]):
            chunks.append(
                RetrievedChunk(
                    chunk_id=cid,
                    doc_id=meta.get("doc_id", ""),
                    content=doc,
                    score=0.0,
                    metadata={k: v for k, v in meta.items() if k not in ("tenant_id", "kb_id", "doc_id")},
                )
            )
        return chunks

    def delete_doc(self, tenant_id: str, kb_id: str, doc_id: str) -> None:
        """删除文档"""
        col = self._get_collection(tenant_id, kb_id)
        col.delete(where={"doc_id": doc_id})
        logger.info(f"Deleted doc {doc_id} from {tenant_id}/{kb_id}")

    def count(self, tenant_id: str, kb_id: str) -> int:
        """返回 chunk 总数"""
        col = self._get_collection(tenant_id, kb_id)
        return col.count()


def get_hybrid_retriever() -> "HybridRetrieverWrapper":
    """获取 Hybrid Retriever 单例"""
    global _hybrid_instance
    
    if _hybrid_instance is None:
        with _singleton_lock:
            if _hybrid_instance is None:
                _hybrid_instance = HybridRetrieverWrapper(
                    retriever=get_milvus_retriever(),
                    embedder=get_embedder(),
                )
    
    return _hybrid_instance


class HybridRetrieverWrapper:
    """混合检索器包装器"""
    
    def __init__(self, retriever: MilvusRetrieverWrapper, embedder: BaseEmbedder):
        self._retriever = retriever
        self._embedder = embedder
    
    def retrieve(
        self,
        tenant_id: str,
        kb_id: str,
        query: str,
        top_k: int,
    ) -> list[RetrievedChunk]:
        """混合检索"""
        query_embedding = self._embedder.embed_query(query)
        
        return self._retriever.hybrid_search(
            tenant_id=tenant_id,
            kb_id=kb_id,
            query_text=query,
            query_embedding=query_embedding,
            top_k=top_k,
            use_sparse=True,
            use_rerank=True,
        )


# ═══════════════════════════════════════════════════════════════════════════════════
# 兼容性别名 (向后兼容)
# ═══════════════════════════════════════════════════════════════════════════════════

def get_retriever() -> MilvusRetrieverWrapper:
    """获取 Retriever (兼容性别名)"""
    return get_milvus_retriever()


def reset_retriever() -> None:
    """重置 Retriever 单例"""
    global _retriever_instance, _hybrid_instance
    _retriever_instance = None
    _hybrid_instance = None
