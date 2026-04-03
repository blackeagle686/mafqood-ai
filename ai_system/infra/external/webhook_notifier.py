import logging
import httpx
import os
import json
from typing import Dict, Any

logger = logging.getLogger(__name__)

# Usually this would be in config.py
DOTNET_SYSTEM_WEBHOOK_URL = os.getenv("DOTNET_WEBHOOK_URL", "http://dotnet-system:5000/api/webhooks/mafqood-match")

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
        logger.info(f"Triggering Webhook alert to .NET system at {DOTNET_SYSTEM_WEBHOOK_URL}")
        try:
            # We use a brief timeout so we don't block our celery tasks for too long
            with httpx.Client(timeout=5.0) as client:
                response = client.post(
                    DOTNET_SYSTEM_WEBHOOK_URL,
                    json={
                        "event_type": "high_confidence_match",
                        "payload": match_data
                    }
                )
                
            if response.status_code in (200, 201, 202):
                logger.info("Webhook delivered successfully.")
                return True
            else:
                logger.error(f"Webhook delivery failed with status {response.status_code}: {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to communicate with webhook endpoint: {e}")
            return False
