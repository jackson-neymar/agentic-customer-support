# customer_support_chat/app/services/rag/query_enhancer.py
from typing import List, Dict, Any, Optional
class QueryEnhancer:
    """查询增强：改写、扩展、分解"""
    
    def __init__(self, llm):
        self.llm = llm
    
    async def enhance_query(self, query: str, conversation_history: list) -> Dict:
        """
        查询增强策略：
        1. HyDE (Hypothetical Document Embeddings)
        2. Query Decomposition（多跳查询）
        3. Query Expansion（查询扩展）
        """
        
        # 1. 生成假设性文档（HyDE）
        hypothetical_doc = await self._generate_hyde(query)
        
        # 2. 查询分解（如果是复杂问题）
        sub_queries = await self._decompose_query(query)
        
        # 3. 查询扩展（添加同义词、相关词）
        expanded_queries = await self._expand_query(query)
        
        return {
            "original": query,
            "hypothetical_doc": hypothetical_doc,
            "sub_queries": sub_queries,
            "expanded_queries": expanded_queries
        }
    
    async def _generate_hyde(self, query: str) -> str:
        """HyDE: 生成假设性答案文档"""
        
        prompt = f"""Given the question: "{query}"
        
Write a detailed, hypothetical answer that would perfectly answer this question.
This will be used to find similar real documents.

Hypothetical Answer:"""
        
        response = await self.llm.ainvoke(prompt)
        return response.content
    
    async def _decompose_query(self, query: str) -> List[str]:
        """将复杂查询分解为子查询"""
        
        prompt = f"""Break down this complex question into simpler sub-questions:
"{query}"

If it's already simple, return an empty list.
Return as JSON list: ["sub_question1", "sub_question2", ...]"""
        
        response = await self.llm.ainvoke(prompt)
        # 解析JSON
        import json
        try:
            return json.loads(response.content)
        except:
            return [query]
    
    async def _expand_query(self, query: str) -> List[str]:
        """扩展查询（同义词、相关概念）"""
        
        prompt = f"""Generate 2-3 alternative phrasings of this query:
"{query}"

Return as JSON list: ["alternative1", "alternative2", ...]"""
        
        response = await self.llm.ainvoke(prompt)
        import json
        try:
            return json.loads(response.content)
        except:
            return [query]