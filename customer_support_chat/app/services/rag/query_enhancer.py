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
        """HyDE: 生成中性的检索增强文档，不作为事实依据"""

        prompt = f"""给定用户问题："{query}"

请生成一段用于检索增强的中性假设文档。
描述与回答该问题相关的概念、政策维度、实体和术语。
不要编造具体价格、日期、承诺、库存/可用性、政策结论或事实性结论。
使用中性表述。这段文本只用于匹配相似的真实文档，不作为最终回答依据。

假设检索文档："""

        response = await self.llm.ainvoke(prompt)
        return response.content
    
    async def _decompose_query(self, query: str) -> List[str]:
        """将复杂查询分解为子查询"""
        
        prompt = f"""请将下面这个复杂问题拆解成更简单的子问题：
"{query}"

如果问题本身已经很简单，请返回空列表。
只返回 JSON 数组，不要添加解释文字，例如：["子问题1", "子问题2"]"""
        
        response = await self.llm.ainvoke(prompt)
        # 解析JSON
        import json
        try:
            return json.loads(response.content)
        except:
            return [query]
    
    async def _expand_query(self, query: str) -> List[str]:
        """扩展查询（同义词、相关概念）"""
        
        prompt = f"""请为下面的查询生成 2-3 个中文替代表述或相关检索说法：
"{query}"

只返回 JSON 数组，不要添加解释文字，例如：["替代表述1", "替代表述2"]"""
        
        response = await self.llm.ainvoke(prompt)
        import json
        try:
            return json.loads(response.content)
        except:
            return [query]