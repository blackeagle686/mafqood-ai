import logging
import httpx
import os
import json
from typing import Dict, Any

logger = logging.getLogger(__name__)

# Usually this would be in config.py

class WebhookNotifier:
    """
    Handles sending asynchronous HTTP callbacks to external systems
    (like the primary .NET application) when critical events occur.
    """
    
    @staticmethod
    def send_high_confidence_match_alert(match_data: Dict[str, Any]) -> bool:
        """
        Sends an alert when a high confidence face match is found.
        """
        from django.conf import settings
        
        webhook_url = os.getenv('MAFQOOD_WEBHOOK_URL', 'https://mafqood.runasp.net/api/ai/match-results')
        api_key = os.getenv('MAFQOOD_WEBHOOK_API_KEY', 'mafqood-shared-secret-key-2026')
        
        logger.info(f"Triggering Webhook alert to .NET system at {webhook_url}")
        
        headers = {
            "X-Api-Key": api_key,
            "Content-Type": "application/json"
        }
        
        try:
            # We use a 30.0s timeout to allow for slow cold-starts on hosting servers
            with httpx.Client(timeout=30.0, follow_redirects=True) as client:
                response = client.post(
                    webhook_url,
                    json={
                        "event_type": "high_confidence_match",
                        "payload": match_data
                    },
                    headers=headers
                )
                
            if response.status_code in (200, 201, 202, 204):
                logger.info("Webhook delivered successfully.")
                return True
            else:
                logger.error(f"Webhook delivery failed with status {response.status_code}: {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to communicate with webhook endpoint: {e}")
            return False

    @staticmethod
    def send_match_results_to_mafqood(payload: Dict[str, Any]) -> bool:
        """
        Sends visual match results to the .NET Mafqood backend.
        Uses X-Api-Key authentication header.
        """
        from django.conf import settings
        
        webhook_url = os.getenv('MAFQOOD_WEBHOOK_URL', 'https://mafqood.runasp.net/api/ai/match-results')
        api_key = os.getenv('MAFQOOD_WEBHOOK_API_KEY', 'mafqood-shared-secret-key-2026')
        
        masked_key = f"{api_key[:4]}...{api_key[-4:]}" if api_key and len(api_key) > 8 else str(api_key)
        logger.info(f"Dispatching match callback to Mafqood at {webhook_url} with API Key: '{masked_key}' (length: {len(api_key) if api_key else 0})")
        
        headers = {
            "X-Api-Key": api_key,
            "Content-Type": "application/json"
        }
        
        try:
            with httpx.Client(timeout=30.0, follow_redirects=True) as client:
                response = client.post(
                    webhook_url,
                    json=payload,
                    headers=headers
                )
                
            if response.status_code in (200, 201, 202, 204):
                logger.info(f"Webhook delivered successfully: {response.status_code}")
                return True
            else:
                logger.error(f"Webhook delivery failed with status {response.status_code}: {response.text}")
                return False
        except Exception as e:
            logger.error(f"Failed to communicate with Mafqood webhook endpoint: {e}")
            return False

    @staticmethod
    def send_dna_match_results_to_mafqood(payload: Dict[str, Any]) -> bool:
        """
        Sends DNA match results to the .NET Mafqood backend.
        Uses X-Api-Key authentication header.
        """
        from django.conf import settings
        
        webhook_url = os.getenv('MAFQOOD_DNA_WEBHOOK_URL', 'https://mafqood.runasp.net/api/ai/dna-match-results')
        api_key = os.getenv('MAFQOOD_WEBHOOK_API_KEY', 'mafqood-shared-secret-key-2026')
        
        masked_key = f"{api_key[:4]}...{api_key[-4:]}" if api_key and len(api_key) > 8 else str(api_key)
        logger.info(f"Dispatching DNA match callback to Mafqood at {webhook_url} with API Key: '{masked_key}'")
        
        headers = {
            "X-Api-Key": api_key,
            "Content-Type": "application/json"
        }
        
        try:
            with httpx.Client(timeout=30.0, follow_redirects=True) as client:
                response = client.post(
                    webhook_url,
                    json=payload,
                    headers=headers
                )
                
            if response.status_code in (200, 201, 202, 204):
                logger.info(f"DNA Webhook delivered successfully: {response.status_code}")
                return True
            else:
                logger.error(f"DNA Webhook delivery failed with status {response.status_code}: {response.text}")
                return False
        except Exception as e:
            logger.error(f"Failed to communicate with Mafqood DNA webhook endpoint: {e}")
            return False


