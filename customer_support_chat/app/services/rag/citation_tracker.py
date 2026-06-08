# customer_support_chat/app/services/rag/citation_tracker.py

from typing import List, Dict
from customer_support_chat.app.services.rag.types import RetrievalResult
from typing import List, Dict, Any, Optional
class CitationTracker:
    """追踪答案来源，提供引用"""
    
    def format_answer_with_citations(
        self, 
        answer: str, 
        sources: List[RetrievalResult]
    ) -> str:
        """为答案添加引用标注"""
        
        citations: List[str] = []
        for i, source in enumerate(sources, 1):
            title = source.metadata.get('title', 'Unknown')
            source_type = source.source.value
            citation = f"[{i}] {title} ({source_type})"
            citations.append(citation)
        
        # 在答案末尾添加引用
        formatted = f"{answer}\n\n**来源：**\n"
        formatted += "\n".join(citations)
        
        return formatted
    
    def generate_source_cards(
        self, 
        sources: List[RetrievalResult]
    ) -> List[Dict[str, Any]]:
        """生成来源卡片（用于前端展示）"""
        
        cards: List[Dict[str, Any]] = []
        for source in sources:
            card = {
                "title": source.metadata.get("title", ""),
                "snippet": source.content[:200] + "..." if len(source.content) > 200 else source.content,
                "source_type": source.source.value,
                "url": source.metadata.get("url", ""),
                "score": round(source.score, 3)
            }
            cards.append(card)
        
        return cards