from abc import ABC, abstractmethod
from typing import Dict, Any, Optional

class ILLMClient(ABC):
    """Abstract interface for LLM services."""
    
    @abstractmethod
    def classify_text_appropriateness(self, text: str) -> str:
        pass

    @abstractmethod
    def extract_entities_from_post(self, text: str, image_url: Optional[str] = None) -> Dict[str, Any]:
        pass

    @abstractmethod
    def _call_llm_messages(self, messages: list, temperature: float = 0.7) -> Optional[str]:
        pass
    
    