"""
app/retriever/milvus_retriever.py — Milvus 原生混合检索实现

支持：
1. Dense Vector (稠密向量) - SentenceTransformer 语义嵌入
2. Sparse Vector (稀疏向量) - Milvus 原生 BM25/TF-IDF 稀疏向量
3. 混合检索 - RRF (Reciprocal Rank Fusion) 融合
4. Re-Rank - Cross-Encoder 重排序
5. 多租户隔离

Author: 帕托莉 🐱
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from typing import Any, Optional

import numpy as np
from pymilvus import (
    Collection,
    CollectionSchema,
    DataType,
    FieldSchema,
    MilvusClient,
    MilvusException,
    connections,
    utility,
)

from app.embedder import BaseEmbedder
from app.retriever.base import BaseRetriever, RetrievedChunk

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════════
# 配置
# ═══════════════════════════════════════════════════════════════════════════════════

@dataclass
class MilvusConfig:
    """Milvus 连接配置"""
    host: str = "localhost"
    port: int = 19530
    user: str = ""
    password: str = ""
    db_name: str = "default"
    
    # Collection 配置
    dimension: int = 384  # MiniLM-L12-v2 输出维度
    metric_type_dense: str = "COSINE"  # 稠密向量度量类型
    metric_type_sparse: str = "IP"  # 稀疏向量度量类型 (内积)
    
    # 索引配置
    index_type_dense: str = "GPU_IVF_FLAT"  # 稠密向量索引
    index_type_sparse: str = "SPARSE_INVERTED_INDEX"  # 稀疏向量索引
    
    @property
    def uri(self) -> str:
        if self.user and self.password:
            return f"http://{self.host}:{self.port}"
        return f"http://{self.host}:{self.port}"


@dataclass
class MilvusRetrieverConfig:
    """Milvus Retriever 配置"""
    milvus_config: MilvusConfig = field(default_factory=MilvusConfig)
    
    # 稀疏向量生成
    use_sparse: bool = True
    min_df: int = 1  # 最小文档频率
    max_df: float = 0.95  # 最大文档频率
    norm: str = "l2"  # 归一化方式
    
    # 混合检索
    rrf_k: int = 60  # RRF 平滑常数
    dense_weight: float = 0.5  # 稠密向量权重
    sparse_weight: float = 0.5  # 稀疏向量权重
    
    # Re-Rank
    use_rerank: bool = True
    rerank_top_k: int = 10  # Re-Rank 候选数量
    rerank_model: str = "BAAI/bge-reranker-base"  # Re-Rank 模型


# ═══════════════════════════════════════════════════════════════════════════════════
# 稀疏向量生成 (TF-IDF)
# ═══════════════════════════════════════════════════════════════════════════════════

class SparseVectorGenerator:
    """
    TF-IDF 稀疏向量生成器
    
    生成 Milvus 原生支持的稀疏向量格式：
    {
        "indices": [0, 5, 10, ...],  # 词项索引
        "values": [0.5, 0.3, 0.8, ...]  # TF-IDF 权重
    }
    
    这等价于 BM25 的稀疏表示，Milvus 会自动计算 IDF。
    """
    
    def __init__(
        self,
        min_df: int = 1,
        max_df: float = 0.95,
        norm: str = "l2",
    ):
        self.min_df = min_df
        self.max_df = max_df
        self.norm = norm
        self._vocab: dict[str, int] = {}
        self._idf: dict[str, float] = {}
        self._doc_count: int = 0
    
    def fit(self, documents: list[str]) -> "SparseVectorGenerator":
        """
        从文档集合学习词汇表和 IDF 权重
        
        Args:
            documents: 文档列表
        """
        self._doc_count = len(documents)
        
        # 1. Tokenize 并统计文档频率
        doc_freq: dict[str, int] = {}
        tokenized_docs: list[list[str]] = []
        
        for doc in documents:
            tokens = self._tokenize(doc)
            tokenized_docs.append(tokens)
            
            # 统计文档频率
            unique_tokens = set(tokens)
            for token in unique_tokens:
                doc_freq[token] = doc_freq.get(token, 0) + 1
        
        # 2. 构建词汇表 (过滤低频/高频词)
        self._vocab = {}
        vocab_idx = 0
        for token, df in doc_freq.items():
            if self.min_df <= df <= self.max_df * self._doc_count:
                self._vocab[token] = vocab_idx
                vocab_idx += 1
        
        # 3. 计算 IDF
        for token, df in doc_freq.items():
            if token in self._vocab:
                # IDF = log((N + 1) / (df + 1)) + 1 (标准 BM25 IDF)
                self._idf[token] = np.log((self._doc_count + 1) / (df + 1)) + 1
        
        logger.info(
            f"SparseVectorGenerator: vocab_size={len(self._vocab)}, "
            f"doc_count={self._doc_count}"
        )
        
        return self
    
    def transform(self, documents: list[str]) -> list[dict[str, Any]]:
        """
        将文档转换为稀疏向量
        
        Returns:
            稀疏向量列表，格式为 Milvus 期望的 {"indices": [], "values": []}
        """
        sparse_vectors = []
        
        for doc in documents:
            tokens = self._tokenize(doc)
            
            # 统计词频
            term_freq: dict[str, float] = {}
            for token in tokens:
                if token in self._vocab:
                    term_freq[token] = term_freq.get(token, 0) + 1
            
            # 计算 TF-IDF
            indices = []
            values = []
            tfidf_sum = 0.0
            
            for token, tf in term_freq.items():
                idf = self._idf.get(token, 0)
                tfidf = tf * idf  # TF-IDF = TF * IDF
                indices.append(self._vocab[token])
                values.append(tfidf)
                tfidf_sum += tfidf ** 2
            
            # L2 归一化
            if self.norm == "l2" and tfidf_sum > 0:
                norm_factor = np.sqrt(tfidf_sum)
                values = [v / norm_factor for v in values]
            
            sparse_vectors.append({
                "indices": indices,
                "values": values,
            })
        
        return sparse_vectors
    
    def fit_transform(self, documents: list[str]) -> list[dict[str, Any]]:
        """Fit 并 transform"""
        self.fit(documents)
        return self.transform(documents)
    
    def encode_query(self, query: str) -> dict[str, Any]:
        """
        将查询转换为稀疏向量
        
        使用与文档相同的方法，但只返回查询中存在的词项。
        """
        tokens = self._tokenize(query)
        
        # 统计词频
        term_freq: dict[str, float] = {}
        for token in tokens:
            if token in self._vocab:
                term_freq[token] = term_freq.get(token, 0) + 1
        
        # 计算权重 (查询只计算 TF，使用文档的 IDF)
        indices = []
        values = []
        tfidf_sum = 0.0
        
        for token, tf in term_freq.items():
            idf = self._idf.get(token, 0)
            tfidf = tf * idf
            indices.append(self._vocab[token])
            values.append(tfidf)
            tfidf_sum += tfidf ** 2
        
        # 归一化
        if self.norm == "l2" and tfidf_sum > 0:
            norm_factor = np.sqrt(tfidf_sum)
            values = [v / norm_factor for v in values]
        
        return {
            "indices": indices,
            "values": values,
        }
    
    def _tokenize(self, text: str) -> list[str]:
        """
        简单分词：保留汉字序列和英文单词
        
        Args:
            text: 输入文本
            
        Returns:
            分词列表
        """
        import re
        
        tokens = []
        
        # 中文：按字符切分（可扩展为更复杂的分词器）
        for char in text:
            if '\u4e00' <= char <= '\u9fff':
                tokens.append(char)
        
        # 英文：按字母数字切分
        words = re.findall(r'[a-zA-Z0-9]+', text.lower())
        tokens.extend(words)
        
        return tokens or [text]
    
    @property
    def vocab_size(self) -> int:
        """词汇表大小"""
        return len(self._vocab)


# ═══════════════════════════════════════════════════════════════════════════════════
# Re-Ranker
# ═══════════════════════════════════════════════════════════════════════════════════

class CrossEncoderReranker:
    """
    Cross-Encoder 重排序器
    
    使用交叉编码器对候选文档进行精确的相关性评分。
    比双编码器 (Bi-Encoder) 更准确但更慢。
    """
    
    def __init__(
        self,
        model_name: str = "BAAI/bge-reranker-base",
        device: str = "cpu",
        max_length: int = 512,
    ):
        self.model_name = model_name
        self.device = device
        self.max_length = max_length
        self._model = None
        self._tokenizer = None
    
    def _load_model(self):
        """懒加载模型"""
        if self._model is not None:
            return
        
        try:
            from sentence_transformers import CrossEncoder
            
            self._model = CrossEncoder(
                self.model_name,
                device=self.device,
                max_length=self.max_length,
            )
            logger.info(f"CrossEncoderReranker: loaded model={self.model_name}")
        except ImportError:
            logger.warning("sentence-transformers not installed, rerank disabled")
            self._model = None
    
    def rerank(
        self,
        query: str,
        documents: list[str],
        top_k: int = 5,
    ) -> list[tuple[int, float]]:
        """
        对文档进行重排序
        
        Args:
            query: 查询文本
            documents: 文档列表
            top_k: 返回前 K 个
            
        Returns:
            [(doc_idx, score), ...] 按分数降序排列
        """
        if not documents or self._model is None:
            return [(i, 1.0 / (i + 1)) for i in range(min(top_k, len(documents)))]
        
        self._load_model()
        
        if self._model is None:
            return [(i, 1.0) for i in range(min(top_k, len(documents)))]
        
        try:
            # 构建 query-document 对
            pairs = [[query, doc] for doc in documents]
            
            # 获取相关性分数
            scores = self._model.predict(pairs)
            
            # 按分数降序排序
            ranked = sorted(
                enumerate(scores),
                key=lambda x: -x[1]
            )[:top_k]
            
            return ranked
            
        except Exception as e:
            logger.error(f"Rerank failed: {e}")
            return [(i, 1.0 / (i + 1)) for i in range(min(top_k, len(documents)))]


# ═══════════════════════════════════════════════════════════════════════════════════
# Milvus Retriever
# ═══════════════════════════════════════════════════════════════════════════════════

class MilvusRetriever(BaseRetriever):
    """
    Milvus 原生混合检索器
    
    支持：
    - 稠密向量检索 (Dense Vector)
    - 稀疏向量检索 (Sparse Vector) 
    - 混合检索 (Hybrid Search)
    - Re-Rank
    - 多租户隔离
    """
    
    def __init__(
        self,
        config: MilvusRetrieverConfig,
        embedder: BaseEmbedder,
    ):
        self.config = config
        self.embedder = embedder
        
        # Milvus 客户端
        self._client: MilvusClient | None = None
        
        # 每个 kb 的稀疏向量生成器
        self._sparse_generators: dict[str, SparseVectorGenerator] = {}
        
        # Re-Ranker
        self._reranker: CrossEncoderReranker | None = None
        
        # 连接状态
        self._connected = False
    
    def connect(self) -> None:
        """建立 Milvus 连接"""
        if self._connected:
            return
        
        cfg = self.config.milvus_config
        
        try:
            # 使用 MilvusClient (新版 API)
            self._client = MilvusClient(
                uri=cfg.uri,
                user=cfg.user or None,
                password=cfg.password or None,
                db_name=cfg.db_name,
            )
            
            self._connected = True
            logger.info(
                f"Milvus connected: {cfg.host}:{cfg.port}, db={cfg.db_name}"
            )
            
        except Exception as e:
            logger.error(f"Milvus connection failed: {e}")
            raise
    
    def disconnect(self) -> None:
        """断开 Milvus 连接"""
        if self._client:
            self._client.close()
            self._client = None
            self._connected = False
            logger.info("Milvus disconnected")
    
    def _get_collection_name(self, tenant_id: str, kb_id: str) -> str:
        """生成 Collection 名称"""
        return f"nexus_{tenant_id}_{kb_id}"
    
    def _ensure_collection(self, tenant_id: str, kb_id: str) -> Collection:
        """
        确保 Collection 存在，不存在则创建
        
        Collection Schema:
        - chunk_id: 主键 (VARCHAR)
        - doc_id: 文档 ID (VARCHAR)
        - content: 内容 (VARCHAR)
        - metadata: 元数据 (JSON)
        - dense_vector: 稠密向量 (FLOAT_VECTOR)
        - sparse_vector: 稀疏向量 (SPARSE_FLOAT_VECTOR) # Milvus 2.5+ 支持
        - tenant_id: 租户 ID (VARCHAR, 用于过滤)
        """
        if self._client is None:
            raise RuntimeError("Not connected to Milvus")
        
        collection_name = self._get_collection_name(tenant_id, kb_id)
        
        # 检查是否存在
        if utility.has_collection(collection_name, using="default"):
            collection = Collection(collection_name)
            collection.load()
            return collection
        
        # 创建 Collection Schema
        dim = self.config.milvus_config.dimension
        
        fields = [
            FieldSchema(
                name="chunk_id",
                dtype=DataType.VARCHAR,
                max_length=256,
                is_primary=True,
            ),
            FieldSchema(
                name="doc_id",
                dtype=DataType.VARCHAR,
                max_length=256,
            ),
            FieldSchema(
                name="content",
                dtype=DataType.VARCHAR,
                max_length=65535,
            ),
            FieldSchema(
                name="metadata",
                dtype=DataType.JSON,
            ),
            FieldSchema(
                name="dense_vector",
                dtype=DataType.FLOAT_VECTOR,
                dim=dim,
                description="稠密向量 (SentenceTransformer)",
            ),
        ]
        
        # 添加稀疏向量字段 (Milvus 2.5+ 支持)
        if self.config.use_sparse:
            fields.append(
                FieldSchema(
                    name="sparse_vector",
                    dtype=DataType.SPARSE_FLOAT_VECTOR,
                    description="稀疏向量 (TF-IDF)",
                )
            )
        
        fields.append(
            FieldSchema(
                name="tenant_id",
                dtype=DataType.VARCHAR,
                max_length=64,
                description="租户 ID (用于过滤)",
            )
        )
        
        schema = CollectionSchema(
            fields=fields,
            description=f"Nexus RAG Collection for {tenant_id}/{kb_id}",
            enable_dynamic_field=True,
        )
        
        # 创建 Collection
        collection = Collection(
            name=collection_name,
            schema=schema,
            using="default",
        )
        
        # 创建索引
        self._create_indexes(collection)
        
        # 加载 Collection
        collection.load()
        
        logger.info(f"Collection created: {collection_name}")
        
        return collection
    
    def _create_indexes(self, collection: Collection) -> None:
        """为 Collection 创建索引"""
        cfg = self.config.milvus_config
        
        # 稠密向量索引
        collection.create_index(
            field_name="dense_vector",
            index_params={
                "index_type": cfg.index_type_dense,
                "metric_type": cfg.metric_type_dense,
                "params": {"nlist": 128},
            }
        )
        
        # 稀疏向量索引 (如果有)
        if self.config.use_sparse:
            try:
                collection.create_index(
                    field_name="sparse_vector",
                    index_params={
                        "index_type": cfg.index_type_sparse,
                        "metric_type": cfg.metric_type_sparse,
                    }
                )
            except MilvusException as e:
                logger.warning(f"Sparse vector index creation failed: {e}")
    
    def add_chunks(
        self,
        tenant_id: str,
        kb_id: str,
        chunk_ids: list[str],
        doc_ids: list[str],
        contents: list[str],
        embeddings: list[list[float]],
        metadatas: list[dict[str, Any]],
    ) -> None:
        """
        将文档 chunks 写入 Milvus
        
        同时生成并存储：
        1. 稠密向量 (使用 embedder)
        2. 稀疏向量 (使用 TF-IDF)
        """
        if self._client is None:
            self.connect()
        
        if len(chunk_ids) == 0:
            return
        
        # 确保 Collection 存在
        collection = self._ensure_collection(tenant_id, kb_id)
        
        # 生成稀疏向量
        sparse_vectors = None
        if self.config.use_sparse:
            key = f"{tenant_id}:{kb_id}"
            
            if key not in self._sparse_generators:
                # 需要先 fit 所有文档
                generator = SparseVectorGenerator(
                    min_df=self.config.min_df,
                    max_df=self.config.max_df,
                    norm=self.config.norm,
                )
                # Fit on existing documents
                existing = self.get_all_chunks(tenant_id, kb_id)
                if existing:
                    existing_contents = [c.content for c in existing]
                    generator.fit(existing_contents + contents)
                else:
                    generator.fit(contents)
                self._sparse_generators[key] = generator
            else:
                # 增量添加
                generator = self._sparse_generators[key]
                # 更新 IDF (简化处理：重新 fit)
                existing = self.get_all_chunks(tenant_id, kb_id)
                all_contents = [c.content for c in existing] + contents
                generator.fit(all_contents)
            
            sparse_vectors = generator.transform(contents)
        
        # 准备插入数据
        entities = []
        for i, chunk_id in enumerate(chunk_ids):
            entity = {
                "chunk_id": chunk_id,
                "doc_id": doc_ids[i],
                "content": contents[i],
                "metadata": metadatas[i],
                "dense_vector": embeddings[i],
                "tenant_id": tenant_id,
            }
            
            if sparse_vectors:
                entity["sparse_vector"] = sparse_vectors[i]
            
            entities.append(entity)
        
        # 插入数据
        self._client.insert(
            collection_name=self._get_collection_name(tenant_id, kb_id),
            data=entities,
        )
        
        # Flush 确保数据可见
        self._client.flush(self._get_collection_name(tenant_id, kb_id))
        
        logger.info(
            f"Added {len(chunk_ids)} chunks to {tenant_id}/{kb_id}"
        )
    
    def vector_search(
        self,
        tenant_id: str,
        kb_id: str,
        query_embedding: list[float],
        top_k: int,
    ) -> list[RetrievedChunk]:
        """
        纯稠密向量搜索 (实现 BaseRetriever 接口)
        """
        return self.hybrid_search(
            tenant_id=tenant_id,
            kb_id=kb_id,
            query_text="",  # 纯向量搜索不需要文本
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
        use_sparse: bool | None = None,
        use_rerank: bool | None = None,
    ) -> list[RetrievedChunk]:
        """
        混合检索入口
        
        Args:
            tenant_id: 租户 ID
            kb_id: 知识库 ID
            query_text: 查询文本 (用于稀疏向量和 rerank)
            query_embedding: 查询的稠密向量
            top_k: 返回数量
            use_sparse: 是否使用稀疏向量 (None=使用配置)
            use_rerank: 是否使用 rerank (None=使用配置)
            
        Returns:
            检索结果列表
        """
        if self._client is None:
            self.connect()
        
        use_sparse = use_sparse if use_sparse is not None else self.config.use_sparse
        use_rerank = use_rerank if use_rerank is not None else self.config.use_rerank
        
        collection_name = self._get_collection_name(tenant_id, kb_id)
        
        if not utility.has_collection(collection_name, using="default"):
            return []
        
        # 计算候选数量 (rerank 需要更多候选)
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
                filter=f'tenant_id == "{tenant_id}"',
                search_params={
                    "metric_type": self.config.milvus_config.metric_type_dense,
                    "params": {},
                },
            )
            
            if results and len(results) > 0:
                dense_results = [
                    (r["entity"]["chunk_id"], r["entity"]["doc_id"], 
                     r["entity"]["content"], r["entity"].get("metadata", {}),
                     r["distance"])
                    for r in results[0]
                ]
                
        except Exception as e:
            logger.error(f"Dense search failed: {e}")
        
        # ════════════════════════════════════════════════════════════════════════════
        # 2. 稀疏向量搜索
        # ════════════════════════════════════════════════════════════════════════════
        sparse_results = []
        
        if use_sparse and query_text:
            key = f"{tenant_id}:{kb_id}"
            generator = self._sparse_generators.get(key)
            
            if generator:
                try:
                    sparse_vector = generator.encode_query(query_text)
                    
                    if sparse_vector["indices"]:  # 确保有词项
                        results = self._client.search(
                            collection_name=collection_name,
                            data=[sparse_vector],
                            limit=candidate_k,
                            output_fields=["chunk_id", "doc_id", "content", "metadata"],
                            filter=f'tenant_id == "{tenant_id}"',
                            anns_field="sparse_vector",
                            search_params={
                                "metric_type": self.config.milvus_config.metric_type_sparse,
                                "params": {},
                            },
                        )
                        
                        if results and len(results) > 0:
                            sparse_results = [
                                (r["entity"]["chunk_id"], r["entity"]["doc_id"],
                                 r["entity"]["content"], r["entity"].get("metadata", {}),
                                 r["distance"])
                                for r in results[0]
                            ]
                            
                except Exception as e:
                    logger.warning(f"Sparse search failed: {e}")
        
        # ════════════════════════════════════════════════════════════════════════════
        # 3. RRF 融合
        # ════════════════════════════════════════════════════════════════════════════
        if not dense_results and not sparse_results:
            return []
        
        if not sparse_results:
            # 只有稠密结果
            fused = [(r[0], r[4]) for r in dense_results]
        elif not dense_results:
            # 只有稀疏结果
            fused = [(r[0], r[4]) for r in sparse_results]
        else:
            # RRF 融合
            fused = self._rrf_fusion(
                dense_results=dense_results,
                sparse_results=sparse_results,
                k=self.config.rrf_k,
                dense_weight=self.config.dense_weight,
                sparse_weight=self.config.sparse_weight,
            )
        
        # ════════════════════════════════════════════════════════════════════════════
        # 4. Re-Rank
        # ════════════════════════════════════════════════════════════════════════════
        if use_rerank and query_text:
            fused = self._rerank_fusion(
                fused_results=fused,
                query_text=query_text,
                candidate_k=self.config.rerank_top_k,
            )
        
        # 构建返回结果
        results = []
        for chunk_id, score, *_ in fused[:top_k]:
            # 找到完整信息
            for r in dense_results + sparse_results:
                if r[0] == chunk_id:
                    results.append(RetrievedChunk(
                        chunk_id=chunk_id,
                        doc_id=r[1],
                        content=r[2],
                        score=float(score),
                        metadata=r[3],
                    ))
                    break
        
        return results
    
    def _rrf_fusion(
        self,
        dense_results: list,
        sparse_results: list,
        k: int = 60,
        dense_weight: float = 0.5,
        sparse_weight: float = 0.5,
    ) -> list[tuple]:
        """
        RRF (Reciprocal Rank Fusion) 融合
        
        score(d) = Σ weight_i / (k + rank_i(d) + 1)
        """
        scores: dict[str, tuple] = {}
        
        # 稠密向量得分
        for rank, (chunk_id, doc_id, content, metadata, distance) in enumerate(dense_results):
            rrf_score = dense_weight / (k + rank + 1)
            if chunk_id not in scores:
                scores[chunk_id] = (chunk_id, 0.0, doc_id, content, metadata)
            scores[chunk_id] = (
                chunk_id,
                scores[chunk_id][1] + rrf_score,
                doc_id,
                content,
                metadata,
            )
        
        # 稀疏向量得分
        for rank, (chunk_id, doc_id, content, metadata, distance) in enumerate(sparse_results):
            rrf_score = sparse_weight / (k + rank + 1)
            if chunk_id not in scores:
                scores[chunk_id] = (chunk_id, 0.0, doc_id, content, metadata)
            scores[chunk_id] = (
                chunk_id,
                scores[chunk_id][1] + rrf_score,
                doc_id,
                content,
                metadata,
            )
        
        # 按分数降序
        return sorted(scores.values(), key=lambda x: -x[1])
    
    def _rerank_fusion(
        self,
        fused_results: list,
        query_text: str,
        candidate_k: int,
    ) -> list[tuple]:
        """
        使用 Re-Rank 进行二次排序
        """
        if self._reranker is None:
            self._reranker = CrossEncoderReranker(
                model_name=self.config.rerank_model,
            )
        
        # 获取候选文档
        candidates = fused_results[:candidate_k]
        if not candidates:
            return fused_results
        
        # 提取文档内容
        docs = [r[2] for r in candidates]  # content
        doc_ids = [r[0] for r in candidates]  # chunk_id
        
        # Re-Rank
        reranked = self._reranker.rerank(query_text, docs, top_k=len(docs))
        
        # 重建结果
        reranked_results = []
        for doc_idx, score in reranked:
            chunk_id = doc_ids[doc_idx]
            # 找到原始信息
            for r in candidates:
                if r[0] == chunk_id:
                    reranked_results.append((r[0], score, r[2], r[3], r[4]))
                    break
        
        return reranked_results
    
    def get_all_chunks(
        self,
        tenant_id: str,
        kb_id: str,
    ) -> list[RetrievedChunk]:
        """获取指定租户+知识库的所有 chunks"""
        if self._client is None:
            self.connect()
        
        collection_name = self._get_collection_name(tenant_id, kb_id)
        
        if not utility.has_collection(collection_name, using="default"):
            return []
        
        try:
            results = self._client.query(
                collection_name=collection_name,
                filter=f'tenant_id == "{tenant_id}"',
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
    
    def delete_doc(
        self,
        tenant_id: str,
        kb_id: str,
        doc_id: str,
    ) -> None:
        """删除指定文档的所有 chunks"""
        if self._client is None:
            self.connect()
        
        collection_name = self._get_collection_name(tenant_id, kb_id)
        
        try:
            self._client.delete(
                collection_name=collection_name,
                filter=f'doc_id == "{doc_id}"',
            )
            self._client.flush(collection_name)
            logger.info(f"Deleted doc {doc_id} from {tenant_id}/{kb_id}")
            
        except Exception as e:
            logger.error(f"Delete failed: {e}")
    
    def count(self, tenant_id: str, kb_id: str) -> int:
        """返回指定租户+知识库的 chunk 总数"""
        if self._client is None:
            self.connect()
        
        collection_name = self._get_collection_name(tenant_id, kb_id)
        
        try:
            results = self._client.query(
                collection_name=collection_name,
                filter=f'tenant_id == "{tenant_id}"',
                output_fields=["count(*)"],
                limit=1,
            )
            
            return results[0]["count(*)"] if results else 0
            
        except Exception:
            return 0
