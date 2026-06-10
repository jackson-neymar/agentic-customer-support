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

    SYSTEM_PROMPT = """你是幻觉检测专家。你的任务是评估生成回答中是否包含无法由给定源文档支持的声明。

评分标准：
- 0.0：回答完全基于给定文档
- 0.1-0.3：有轻微外推，但整体忠实于文档
- 0.3-0.6：支持性内容和无支持声明混杂
- 0.6-0.9：大部分声明缺乏支持，只有少量文档依据
- 1.0：完全编造，没有文档支持

请严格评估：任何没有明确文档支持的事实性声明都应提高评分。"""

    def __init__(self, model_name: str = "gpt-4o"):
        self.llm = ChatOpenAI(
            model=model_name,
            temperature=0
        ).with_structured_output(HallucinationScore)

    async def grade(self, question: str, documents: List[str], answer: str) -> HallucinationScore:
        """评估回答中的幻觉程度"""
        docs_text = "\n\n---\n\n".join(documents) if documents else "No documents provided."

        user_prompt = f"""## 源文档：
{docs_text}

## 用户问题：
{question}

## 生成回答：
{answer}

请基于源文档评估该生成回答的幻觉程度。"""

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

    SYSTEM_PROMPT = """你是相关性评估专家。你的任务是评估生成回答在多大程度上回应了用户问题。

评分标准：
- 0.0：回答与问题完全无关
- 0.1-0.3：有轻微关联，但没有回答核心问题
- 0.3-0.6：部分回答了问题，但遗漏关键方面
- 0.6-0.8：回答了主要问题，但仍有少量缺口
- 0.8-1.0：全面且直接地回答了问题

评估时请考虑：是否回答了用户真正问的内容？是否完整？是否聚焦于问题？"""

    def __init__(self, model_name: str = "gpt-4o"):
        self.llm = ChatOpenAI(
            model=model_name,
            temperature=0
        ).with_structured_output(RelevanceScore)

    async def grade(self, question: str, answer: str) -> RelevanceScore:
        """评估回答与问题的相关性"""
        user_prompt = f"""## 用户问题：
{question}

## 生成回答：
{answer}

请评估该回答对用户问题的回应程度。"""

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
