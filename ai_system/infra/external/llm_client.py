import os
import logging
import json
from typing import Dict, Any, Optional
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

class LLMService:
    """
    Service responsible for interacting with Large Language Models directly.
    Provides methods for text classification and entity extraction.
    """
    
    def __init__(self):
        # Default API key if none found in environment variables
        self.api_key = os.getenv("OPENROUTER_API_KEY")
        if not self.api_key:
             logger.warning("OPENROUTER_API_KEY not found in environment. LLM services may fail.")
             
        self.client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=self.api_key,
        )
        self.model = "qwen/qwen3-vl-30b-a3b-thinking"
        
        self.headers = {
            "HTTP-Referer": "https://mafqood.ai", 
            "X-OpenRouter-Title": "Mafqood AI", 
        }

    def _call_llm(self, prompt: Any, temperature: float = 0.0) -> Optional[str]:
        """Helper method to encapsulate the OpenAI client call."""
        try:
            completion = self.client.chat.completions.create(
                extra_headers=self.headers,
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=temperature
            )
            return completion.choices[0].message.content.strip()
        except Exception as e:
            logger.error(f"Error calling LLM OpenRouter API: {e}")
            return None

    def classify_text_appropriateness(self, text: str) -> str:
        """
        Classifies Arabic/English text for severe profanity, hate speech, or explicit content.
        Returns 'bad' or 'good'.
        """
        logger.info("Calling LLM to classify text content for appropriateness...")
        prompt = (
            "You are a content moderation AI. Analyze the following Arabic/English text from a social media post "
            "reporting a missing or found child. Determine if the text contains severe profanity, hate speech, "
            "or explicit inappropriate content. Reply ONLY with the word 'bad' if it is highly inappropriate, "
            "or 'good' if it is safe/acceptable. Do not explain.\n\n"
            f"Text: \"{text}\""
        )
        
        response = self._call_llm(prompt)
        if response:
            response_lower = response.lower()
            if "bad" in response_lower:
                return "bad"
            elif "good" in response_lower:
                return "good"
                
        # Return none or fallback string if LLM fails
        return "unknown"

    def extract_entities_from_post(self, text: str, image_url: Optional[str] = None) -> Dict[str, Any]:
        """
        Extracts structured entities (status, location, age) from unstructured Arabic posts,
        and uses the image via VLM capabilities to extract further visual context like clothing and age estimations.
        """
        logger.info("Passing post text and image to VLM for entity extraction...")
        extracted = {
            "status": "missing",
            "location": "unknown",
            "age_estimation": None,
            "clothing": "unknown"
        }
        
        prompt_text = (
            "You are an AI/VLM assistant extracting data from Arabic social media posts about missing and found people. "
            "Extract the following information from the text AND the provided image. "
            "Return ONLY a valid JSON object. Do not include markdown formatting.\n"
            "Fields:\n"
            "- 'status': string. Either 'missing' or 'found'. Infer this from context (e.g., عثر = found, مفقود = missing).\n"
            "- 'location': string. The city, street, or landmark mentioned. If none, return 'unknown'.\n"
            "- 'age_estimation': integer. Attempt to find the age mentioned in text, or estimate it visually from the image. If none, return null.\n"
            "- 'clothing': string. Briefly describe the clothing seen in the image or mentioned in the text. If none, return 'unknown'.\n\n"
            f"Text: \"{text}\"\n\nJSON Output:"
        )
        
        if image_url:
            prompt = [
                {"type": "text", "text": prompt_text},
                {"type": "image_url", "image_url": {"url": image_url}}
            ]
        else:
            prompt = prompt_text
            
        response_text = self._call_llm(prompt)
        
        if response_text:
            try:
                # The model might include ```json tags even if told not to, so strip them
                if response_text.startswith("```json"):
                    response_text = response_text[7:]
                if response_text.endswith("```"):
                    response_text = response_text[:-3]
                    
                json_data = json.loads(response_text)
                
                # Update default values with new extracted data
                for key in ["status", "location", "age_estimation", "clothing"]:
                    if key in json_data and json_data[key] is not None:
                        extracted[key] = json_data[key]
                        
                logger.info(f"LLM successfully extracted: {extracted}")
                    
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse JSON from LLM: {e}")
                
        return extracted
