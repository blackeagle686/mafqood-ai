import os
import sys
import django

# Add project paths to Python sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../app')))

# Initialize Django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "app.mafqood_project.settings")
django.setup()

from infra.external.webhook_notifier import WebhookNotifier

def run_test():
    print("🚀 Initiating webhook delivery test to the .NET Backend...")

    # Mock payload matching the schema currently dispatched by app/ai/views.py
    payload = {
        "userId": "user-lost-456",
        "postId": 1001,
        "matchedResults": [
            {
                "userId": "user-found-123",
                "postId": 1002,
                "confidenceScore": 0.85
            }
        ]
    }

    print(f"Payload to send: {payload}")
    success = WebhookNotifier.send_match_results_to_mafqood(payload)
    
    if success:
        print("✅ Webhook delivered successfully and received a successful response from the .NET backend!")
    else:
        print("❌ Webhook delivery failed. Check output logs above for response code/details.")

if __name__ == "__main__":
    run_test()
