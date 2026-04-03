import re
import unicodedata
import os
import logging
from services.bad_words import BAD_WORDS
from services.llm_service import LLMService

logger = logging.getLogger(__name__)

class TextCleaner:
    @staticmethod
    def normalize_arabic(text: str) -> str:
        """Normalize Arabic text by removing diacritics and unifying characters."""
        # Remove diacritics
        text = "".join(c for c in text if not unicodedata.combining(c))
        
        # Normalize Alef
        text = re.sub("[إأآا]", "ا", text)
        # Normalize Teh Marbuta
        text = re.sub("ة", "ه", text)
        # Normalize Yeh
        text = re.sub("ى", "ي", text)
        
        return text

    @staticmethod
    def clean(text: str) -> str:
        """General cleaning: lowercase, remove punctuation, etc."""
        text = text.lower()
        # Remove punctuation and special characters
        text = re.sub(r'[^\w\s]', '', text)
        # Handle Arabic specific normalization
        text = TextCleaner.normalize_arabic(text)
        return text.strip()

class BadWordsClassifier:
    def __init__(self):
        self.bad_words = set(BAD_WORDS["ar"] + BAD_WORDS["en"])
        # Pre-normalize the bad words list for faster matching
        self.normalized_bad_words = {TextCleaner.clean(word) for word in self.bad_words}
        self.llm_service = LLMService()

    def classify(self, text: str) -> str:
        """Classify text as 'bad' or 'good' using LLM first, falling back to static list."""
        
        # 1. LLM Classification for contextual appropriateness
        llm_result = self.llm_service.classify_text_appropriateness(text)
        if llm_result in ["bad", "good"]:
            return llm_result

        # 2. Fallback to static linear list
        cleaned_text = TextCleaner.clean(text)
        tokens = cleaned_text.split()
        for token in tokens:
            if token in self.normalized_bad_words:
                return "bad"
        return "good"

# Instance for external use
classifier = BadWordsClassifier()

def text_to_embedding(text: str) -> list:
    """Stub for future embedding implementation."""
    return []

def classify_text(text: str) -> str:
    """Main classification function."""
    return classifier.classify(text)
