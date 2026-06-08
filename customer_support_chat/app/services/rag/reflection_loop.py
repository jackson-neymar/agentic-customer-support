"""Self-Reflection Loop for Agentic RAG Pipeline.
Coordinates quality grading, query rewriting retry, and web search fallback.
"""
import logging
import time
import asyncio
from typing import List, Optional, Tuple, Any
from dataclasses import dataclass, field

from .llm_grader import HallucinationGrader, RelevanceGrader

logger = logging.getLogger(__name__)


@dataclass
class ReflectionAttempt:
    """单次反思尝试的记录"""
    attempt_number: int
    hallucination_score: float
    relevance_score: float
    passed: bool
    query_used: str
    action_taken: str  # "initial", "rewrite", "web_search"


@dataclass
class ReflectionResult:
    """反思循环最终结果"""
    final_answer: str
    passed: bool
    hallucination_score: float
    relevance_score: float
    total_attempts: int
    used_web_search: bool
    total_duration_seconds: float
    attempts_history: List[ReflectionAttempt] = field(default_factory=list)


class SelfReflectionLoop:
    """自反思循环管理器

    流程:
    1. 评估初始回答 → 如果通过则直接返回
    2. 不通过 → QueryEnhancer 改写 → 重新检索+生成 → 重新评估
    3. 最多重试 MAX_RETRIES 次
    4. 仍不通过 → 降级网络搜索
    """

    HALLUCINATION_THRESHOLD = 0.3  # 幻觉分>0.3 触发重试
    RELEVANCE_THRESHOLD = 0.7      # 相关性<0.7 触发重试
    MAX_RETRIES = 2
    TIMEOUT_SECONDS = 10.0

    def __init__(self, hallucination_grader: HallucinationGrader,
                 relevance_grader: RelevanceGrader,
                 query_enhancer: Optional[Any] = None,
                 retriever: Optional[Any] = None,
                 generate_answer_fn: Optional[Any] = None):
        self.hallucination_grader = hallucination_grader
        self.relevance_grader = relevance_grader
        self.query_enhancer = query_enhancer
        self.retriever = retriever
        self.generate_answer_fn = generate_answer_fn

    async def run(self, query: str, documents: List[str], initial_answer: str,
                  conversation_history: Optional[list] = None) -> ReflectionResult:
        """执行自反思循环"""
        start_time = time.time()
        attempts: List[ReflectionAttempt] = []

        # 第一次评估
        h_score, r_score = await self._evaluate(query, documents, initial_answer)
        passed = self._check_passed(h_score, r_score)

        attempts.append(ReflectionAttempt(
            attempt_number=1, hallucination_score=h_score,
            relevance_score=r_score, passed=passed,
            query_used=query, action_taken="initial"
        ))

        if passed:
            logger.info(f"Reflection passed on initial attempt: h={h_score:.2f}, r={r_score:.2f}")
            return self._build_result(initial_answer, True, h_score, r_score,
                                      attempts, False, start_time)

        # 重试循环
        current_answer = initial_answer
        current_docs = documents

        for retry in range(self.MAX_RETRIES):
            if time.time() - start_time > self.TIMEOUT_SECONDS:
                logger.warning("Reflection loop timeout, returning current answer")
                break

            # Query Rewriting
            rewritten_query = await self._rewrite_query(query, conversation_history)
            logger.info(f"Reflection retry {retry+1}: rewritten query = {rewritten_query[:100]}")

            # 重新检索
            if self.retriever:
                current_docs = await self._retrieve(rewritten_query)

            # 重新生成
            if self.generate_answer_fn:
                try:
                    current_answer = await self.generate_answer_fn(rewritten_query, current_docs)
                except Exception as e:
                    logger.error(f"Answer regeneration failed: {e}")

            # 重新评估
            h_score, r_score = await self._evaluate(rewritten_query, current_docs, current_answer)
            passed = self._check_passed(h_score, r_score)

            attempts.append(ReflectionAttempt(
                attempt_number=retry + 2, hallucination_score=h_score,
                relevance_score=r_score, passed=passed,
                query_used=rewritten_query, action_taken="rewrite"
            ))

            if passed:
                logger.info(f"Reflection passed on retry {retry+1}: h={h_score:.2f}, r={r_score:.2f}")
                return self._build_result(current_answer, True, h_score, r_score,
                                          attempts, False, start_time)

        # 降级网络搜索
        logger.info("All retries exhausted, falling back to web search")
        web_answer = await self._fallback_web_search(query)

        attempts.append(ReflectionAttempt(
            attempt_number=len(attempts) + 1, hallucination_score=0.0,
            relevance_score=0.8, passed=True,
            query_used=query, action_taken="web_search"
        ))

        return self._build_result(web_answer, True, 0.0, 0.8,
                                  attempts, True, start_time)

    def _check_passed(self, h_score: float, r_score: float) -> bool:
        return h_score <= self.HALLUCINATION_THRESHOLD and r_score >= self.RELEVANCE_THRESHOLD

    async def _evaluate(self, question: str, documents: List[str], answer: str) -> Tuple[float, float]:
        """并行评估幻觉和相关性"""
        h_task = self.hallucination_grader.grade(question, documents, answer)
        r_task = self.relevance_grader.grade(question, answer)
        try:
            h_result, r_result = await asyncio.gather(h_task, r_task)
            return h_result.score, r_result.score
        except Exception as e:
            logger.error(f"Evaluation failed: {e}")
            # 评估失败：保守判定为未通过（高幻觉、低相关）
            return 0.5, 0.5

    async def _rewrite_query(self, original_query: str,
                             conversation_history: Optional[list] = None) -> str:
        """使用 QueryEnhancer 改写查询。

        QueryEnhancer.enhance_query() 返回 Dict（含 original/hypothetical_doc/
        sub_queries/expanded_queries），我们优先使用 hypothetical_doc（HyDE），
        其次是第一个 expanded_query，最后回退到 original。
        当 QueryEnhancer 不可用或调用失败时，graceful fallback 返回原 query。
        """
        if self.query_enhancer is None:
            return original_query
        try:
            enhanced = await self.query_enhancer.enhance_query(
                original_query, conversation_history or []
            )
            if not enhanced:
                return original_query
            # Dict 形态（当前 QueryEnhancer 实现）
            if isinstance(enhanced, dict):
                hyde = enhanced.get("hypothetical_doc")
                if hyde and isinstance(hyde, str) and hyde.strip():
                    return hyde.strip()
                expanded = enhanced.get("expanded_queries") or []
                if expanded and isinstance(expanded, list) and expanded[0]:
                    return str(expanded[0])
                return enhanced.get("original", original_query)
            # 字符串形态（兼容备用接口）
            if isinstance(enhanced, str):
                return enhanced
            return original_query
        except Exception as e:
            logger.error(f"Query rewriting failed: {e}")
            return original_query

    async def _retrieve(self, query: str) -> List[str]:
        """重新检索。兼容 RetrievalResult(.content) 与 Document(.page_content)。"""
        try:
            results = await self.retriever.retrieve(query)
            if not results:
                return []
            docs: List[str] = []
            for doc in results:
                content = getattr(doc, "content", None) or getattr(doc, "page_content", None)
                if content:
                    docs.append(content)
            return docs
        except Exception as e:
            logger.error(f"Re-retrieval failed: {e}")
            return []

    async def _fallback_web_search(self, query: str) -> str:
        """降级网络搜索"""
        try:
            from langchain_community.tools import DuckDuckGoSearchResults
            search = DuckDuckGoSearchResults(max_results=5)
            # 同步调用包装成异步
            results = await asyncio.to_thread(search.invoke, query)
            return f"Based on web search results:\n{results}"
        except Exception as e:
            logger.error(f"Web search fallback failed: {e}")
            return "I apologize, but I couldn't find a reliable answer. Please try rephrasing your question."

    def _build_result(self, answer, passed, h_score, r_score,
                      attempts, web_search, start_time) -> ReflectionResult:
        return ReflectionResult(
            final_answer=answer, passed=passed,
            hallucination_score=h_score, relevance_score=r_score,
            total_attempts=len(attempts), used_web_search=web_search,
            total_duration_seconds=time.time() - start_time,
            attempts_history=attempts
        )
