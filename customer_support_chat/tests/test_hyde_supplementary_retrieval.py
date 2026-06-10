import pytest

from customer_support_chat.app.services.rag.hybrid_retriever import HybridRetriever
from customer_support_chat.app.services.rag.rag_service import RAGService
from customer_support_chat.app.services.rag.reflection_loop import SelfReflectionLoop
from customer_support_chat.app.services.rag.types import KnowledgeSource, RetrievalResult


class StubMultiQueryRetriever:
    def __init__(self):
        self.calls = []

    async def retrieve(self, query, **kwargs):
        self.calls.append(("retrieve", query, kwargs))
        return [
            RetrievalResult(
                content=f"doc for {query}",
                source=KnowledgeSource.POLICY_DOCS,
                metadata={},
                score=0.5,
            )
        ]

    async def retrieve_multi_query(self, original_query, supplementary_queries=None, **kwargs):
        self.calls.append(("retrieve_multi_query", original_query, supplementary_queries or [], kwargs))
        return [
            RetrievalResult(
                content="multi-query doc",
                source=KnowledgeSource.POLICY_DOCS,
                metadata={},
                score=0.9,
            )
        ]


class StubQueryEnhancer:
    async def enhance_query(self, query, conversation_history):
        return {
            "original": query,
            "hypothetical_doc": "neutral pet policy retrieval document",
            "expanded_queries": ["pet friendly hotel policy", query],
            "sub_queries": ["pet cleaning fee"],
        }


class PassingGrader:
    async def grade(self, *args, **kwargs):
        class Result:
            score = 0.0
        return Result()


class FailingThenPassingHallucinationGrader:
    async def grade(self, *args, **kwargs):
        class Result:
            score = 0.5
        return Result()


class FailingThenPassingRelevanceGrader:
    async def grade(self, *args, **kwargs):
        class Result:
            score = 0.5
        return Result()


@pytest.mark.asyncio
async def test_multi_query_retrieval_reranks_with_original_query():
    retriever = HybridRetriever()
    original_query = "Can I bring my dog?"
    hyde_query = "This hotel forbids all pets."
    seen_queries = []
    rerank_query = None

    async def fake_retrieve(query, **kwargs):
        seen_queries.append(query)
        return [
            RetrievalResult(
                content=f"candidate from {query}",
                source=KnowledgeSource.POLICY_DOCS,
                metadata={},
                score=0.5,
            )
        ]

    def fake_rerank(query, results, top_k):
        nonlocal rerank_query
        rerank_query = query
        return results[:top_k]

    retriever.retrieve = fake_retrieve
    retriever.reranker = object()
    retriever._rerank = fake_rerank

    await retriever.retrieve_multi_query(
        original_query=original_query,
        supplementary_queries=[hyde_query],
        method="hybrid_rerank",
        top_k=1,
    )

    assert seen_queries == [original_query, hyde_query]
    assert rerank_query == original_query


@pytest.mark.asyncio
async def test_rag_service_uses_hyde_as_supplementary_query():
    service = RAGService()
    service.retriever = StubMultiQueryRetriever()
    service._query_enhancer = StubQueryEnhancer()

    result = await service.retrieve_with_rewrite("Can I bring my dog?")

    call = service.retriever.calls[0]
    assert call[0] == "retrieve_multi_query"
    assert call[1] == "Can I bring my dog?"
    assert call[2] == [
        "neutral pet policy retrieval document",
        "pet friendly hotel policy",
        "pet cleaning fee",
    ]
    assert result["query"] == "Can I bring my dog?"
    assert result["retrieval_queries"][0] == "Can I bring my dog?"


@pytest.mark.asyncio
async def test_reflection_loop_regenerates_with_original_question():
    retriever = StubMultiQueryRetriever()
    enhancer = StubQueryEnhancer()
    generated_with = []

    async def generate_answer_fn(question, docs):
        generated_with.append((question, docs))
        return "regenerated answer"

    loop = SelfReflectionLoop(
        hallucination_grader=FailingThenPassingHallucinationGrader(),
        relevance_grader=FailingThenPassingRelevanceGrader(),
        query_enhancer=enhancer,
        retriever=retriever,
        generate_answer_fn=generate_answer_fn,
    )
    loop.MAX_RETRIES = 1

    await loop.run(
        query="Can I bring my dog?",
        documents=["initial doc"],
        initial_answer="initial answer",
    )

    assert retriever.calls[0][0] == "retrieve_multi_query"
    assert retriever.calls[0][1] == "Can I bring my dog?"
    assert generated_with[0][0] == "Can I bring my dog?"
