"""
tests/test_recall.py — RAG 召回率测试
"""
import pytest
from typing import List, Set
from dataclasses import dataclass


@dataclass
class TestCase:
    query: str
    relevant_docs: Set[str]
    metadata: dict = None


@dataclass
class RecallResult:
    query: str
    recall_at_k: float
    mrr: float
    hit: bool
    retrieved_docs: List[str]
    relevant_docs: Set[str]


class RAGRecallTester:
    """RAG 召回率测试工具"""

    def __init__(self, retriever, embedder, top_k: int = 5):
        self.retriever = retriever
        self.embedder = embedder
        self.top_k = top_k
        self.test_cases: List[TestCase] = []

    def add_case(self, query: str, relevant_docs: Set[str], metadata: dict = None):
        self.test_cases.append(TestCase(
            query=query,
            relevant_docs=relevant_docs,
            metadata=metadata or {}
        ))

    def run_tests(self) -> List[RecallResult]:
        results = []
        
        for case in self.test_cases:
            query_embedding = self.embedder.embed_query(case.query)
            search_results = self.retriever.search(
                query_embedding=query_embedding,
                top_k=self.top_k,
            )
            
            retrieved_docs = [r.get("doc_id") for r in search_results]
            retrieved_set = set(retrieved_docs)
            relevant_set = case.relevant_docs
            
            hit_count = len(retrieved_set & relevant_set)
            recall = hit_count / len(relevant_set) if relevant_set else 0.0
            
            mrr = 0.0
            hit = False
            for i, doc_id in enumerate(retrieved_docs, 1):
                if doc_id in relevant_set:
                    mrr = 1.0 / i
                    hit = True
                    break
            
            results.append(RecallResult(
                query=case.query,
                recall_at_k=recall,
                mrr=mrr,
                hit=hit,
                retrieved_docs=retrieved_docs,
                relevant_docs=relevant_set,
            ))
        
        return results

    def print_report(self, results: List[RecallResult]):
        if not results:
            print("没有测试结果")
            return
        
        total = len(results)
        hits = sum(1 for r in results if r.hit)
        avg_recall = sum(r.recall_at_k for r in results) / total
        avg_mrr = sum(r.mrr for r in results) / total
        
        print("\n" + "=" * 60)
        print("RAG 召回率测试报告")
        print("=" * 60)
        print(f"测试用例数: {total}")
        print(f"Top-K: {self.top_k}")
        print("-" * 60)
        print(f"Hit Rate: {hits}/{total} = {hits/total*100:.1f}%")
        print(f"Avg Recall@K: {avg_recall*100:.1f}%")
        print(f"Avg MRR: {avg_mrr:.3f}")
        print("=" * 60)


def quick_test(retriever, embedder, test_queries: List[dict]) -> dict:
    """快速测试接口"""
    tester = RAGRecallTester(retriever, embedder, top_k=5)
    
    for q in test_queries:
        tester.add_case(
            query=q["query"],
            relevant_docs=set(q.get("relevant", []))
        )
    
    results = tester.run_tests()
    
    total = len(results)
    hits = sum(1 for r in results if r.hit)
    avg_recall = sum(r.recall_at_k for r in results) / total if total else 0
    avg_mrr = sum(r.mrr for r in results) / total if total else 0
    
    return {
        "recall": avg_recall,
        "mrr": avg_mrr,
        "hit_rate": hits / total if total else 0,
    }
