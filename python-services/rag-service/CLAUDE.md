# CLAUDE.md — python-services/rag-service

> 本文件由帕托莉维护，Claude Code 必须在开始前完整阅读。

---

## 服务职责

`rag-service` 是 RAG 知识库检索服务，负责：
1. 文档分片与向量化（Embedding）
2. 混合检索（语义向量 + BM25 关键词）
3. 多租户知识库隔离
4. 向量入库与管理

---

## 技术约束（容器内版本）

| 约束 | 说明 |
|------|------|
| **向量库** | ChromaDB（内存/持久化文件模式，无需独立服务） |
| **Embedding** | sentence-transformers (paraphrase-multilingual-MiniLM-L12-v2 或同等) |
| **BM25** | rank_bm25 纯 Python 实现（无需 ES） |
| **混合排序** | 手动 RRF 实现 |
| **API** | FastAPI, 端口 8003 |
| **禁止** | 不依赖独立 Milvus/ES 服务（容器内无法启动） |

> 生产环境扩展路径：通过 Retriever 抽象层，可无缝切换到 Milvus + ES

---

## 当前任务

### Task-06: 实现 rag-service 基础检索服务

**交付物：**

```
python-services/rag-service/
├── requirements.txt
├── main.py
├── app/
│   ├── api/v1/
│   │   ├── knowledge.py     # 文档管理接口
│   │   └── retrieve.py      # 检索接口
│   ├── retriever/
│   │   ├── base.py          # BaseRetriever 抽象类
│   │   ├── chroma_retriever.py   # ChromaDB 实现
│   │   └── hybrid.py        # BM25 + 向量 RRF 融合
│   ├── embedder.py          # Embedding 工具
│   ├── chunker.py           # 文档分片
│   └── schemas.py
└── tests/
    ├── test_retriever.py
    └── test_hybrid.py
```

**核心接口：**

```python
# POST /api/v1/knowledge/ingest
# Header: X-Tenant-Id: t1
# Body: { "doc_id": "d1", "content": "文档内容", "metadata": {} }

# POST /api/v1/knowledge/retrieve
# Header: X-Tenant-Id: t1
# Body: { "query": "检索词", "top_k": 5, "knowledge_base_id": "kb1" }
# Response: [{ "content": "...", "score": 0.87, "metadata": {} }]
```

**RRF 实现：**

```python
def rrf_merge(bm25_results, vector_results, k=60):
    scores = {}
    for rank, doc_id in enumerate(bm25_results):
        scores[doc_id] = scores.get(doc_id, 0) + 1 / (k + rank + 1)
    for rank, doc_id in enumerate(vector_results):
        scores[doc_id] = scores.get(doc_id, 0) + 1 / (k + rank + 1)
    return sorted(scores.items(), key=lambda x: -x[1])
```

**多租户隔离（ChromaDB）：**

```python
# Collection 命名：nexus_{tenant_id}_{kb_id}
collection_name = f"nexus_{tenant_id}_{knowledge_base_id}"

# 或统一 Collection + metadata filter:
collection.query(
    query_embeddings=[embedding],
    where={"tenant_id": tenant_id},
    n_results=top_k
)
```

---

## 测试要求

- [ ] 写入文档 → 检索出相关内容
- [ ] 不同租户数据严格隔离（租户A的文档不出现在租户B的结果里）
- [ ] 混合检索 RRF 分数合并逻辑正确
- [ ] top_k 参数生效

---

## 注意事项

1. Embedding 模型首次运行会下载（~90MB），测试时可用随机向量 Mock
2. ChromaDB 使用 `chromadb.Client()` 内存模式（测试）
3. 先输出 Retriever 类的接口设计再编码
