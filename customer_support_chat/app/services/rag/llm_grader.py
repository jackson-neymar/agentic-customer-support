"""LLM-based Graders for RAG Self-Reflection Pipeline.
Uses GPT-4o for high-quality evaluation of retrieval and generation quality.
"""
import logging
from typing import List
from pydantic import BaseModel, Field
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage

logger = logging.getLogger(__name__)


class HallucinationScore(BaseModel):
    """幻觉评分结构化输出"""
    score: float = Field(ge=0, le=1, description="幻觉评分 0-1, 0=完全基于文档, 1=完全编造")
    reasoning: str = Field(description="评分理由说明")
    problematic_claims: List[str] = Field(default_factory=list, description="缺乏文档支持的声明")


class RelevanceScore(BaseModel):
    """相关性评分结构化输出"""
    score: float = Field(ge=0, le=1, description="相关性评分 0-1, 0=完全无关, 1=完美回答")
    reasoning: str = Field(description="评分理由")
    missing_aspects: List[str] = Field(default_factory=list, description="未覆盖的问题方面")


class HallucinationGrader:
    """幻觉检测评分器"""

    SYSTEM_PROMPT = """You are a hallucination detection expert. Your job is to evaluate whether a generated answer contains claims that are NOT supported by the provided source documents.

Scoring guidelines:
- 0.0: Answer is entirely grounded in the provided documents
- 0.1-0.3: Minor extrapolations but generally faithful
- 0.3-0.6: Contains some unsupported claims mixed with supported ones
- 0.6-0.9: Mostly unsupported claims with few document references
- 1.0: Entirely fabricated with no document support

Be strict: any factual claim without clear document support should increase the score."""

    def __init__(self, model_name: str = "gpt-4o"):
        self.llm = ChatOpenAI(
            model=model_name,
            temperature=0
        ).with_structured_output(HallucinationScore)

    async def grade(self, question: str, documents: List[str], answer: str) -> HallucinationScore:
        """评估回答中的幻觉程度"""
        docs_text = "\n\n---\n\n".join(documents) if documents else "No documents provided."

        user_prompt = f"""## Source Documents:
{docs_text}

## User Question:
{question}

## Generated Answer:
{answer}

Evaluate the hallucination level of the generated answer based on the source documents."""

        messages = [
            SystemMessage(content=self.SYSTEM_PROMPT),
            HumanMessage(content=user_prompt)
        ]

        try:
            result = await self.llm.ainvoke(messages)
            return result
        except Exception as e:
            logger.error(f"Hallucination grading failed: {e}")
            # 失败时返回保守评分（认为可能有幻觉）
            return HallucinationScore(score=0.5, reasoning=f"Grading failed: {str(e)}")


class RelevanceGrader:
    """相关性评分器"""

    SYSTEM_PROMPT = """You are a relevance assessment expert. Your job is to evaluate how well a generated answer addresses the user's question.

Scoring guidelines:
- 0.0: Answer is completely irrelevant to the question
- 0.1-0.3: Tangentially related but doesn't address the core question
- 0.3-0.6: Partially addresses the question but misses key aspects
- 0.6-0.8: Addresses the main question with minor gaps
- 0.8-1.0: Comprehensively and directly answers the question

Consider: Does it answer what was asked? Is it complete? Is it focused on the question?"""

    def __init__(self, model_name: str = "gpt-4o"):
        self.llm = ChatOpenAI(
            model=model_name,
            temperature=0
        ).with_structured_output(RelevanceScore)

    async def grade(self, question: str, answer: str) -> RelevanceScore:
        """评估回答与问题的相关性"""
        user_prompt = f"""## User Question:
{question}

## Generated Answer:
{answer}

Evaluate how well the answer addresses the user's question."""

        messages = [
            SystemMessage(content=self.SYSTEM_PROMPT),
            HumanMessage(content=user_prompt)
        ]

        try:
            result = await self.llm.ainvoke(messages)
            return result
        except Exception as e:
            logger.error(f"Relevance grading failed: {e}")
            return RelevanceScore(score=0.5, reasoning=f"Grading failed: {str(e)}")
