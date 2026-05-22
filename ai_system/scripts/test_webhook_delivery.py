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

    print(f"Testing send_match_results_to_mafqood...")
    success1 = WebhookNotifier.send_match_results_to_mafqood(payload)
    
    print("\nTesting send_high_confidence_match_alert...")
    match_data = {
        "missing_post_id": 1001,
        "found_post_id": 1002,
        "score": 0.95,
        "metadata": {"status": "missing"}
    }
    success2 = WebhookNotifier.send_high_confidence_match_alert(match_data)
    
    if success1:
        print("✅ Match results webhook delivered successfully!")
    else:
        print("❌ Match results webhook delivery failed (check status/error above).")

    if success2:
        print("✅ High confidence match alert webhook delivered successfully!")
    else:
        print("❌ High confidence match alert webhook delivery failed (check status/error above).")

if __name__ == "__main__":
    run_test()
