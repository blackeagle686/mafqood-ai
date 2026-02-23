import requests
import time
import sys

BASE_URL = "http://localhost:8000"

def test_async_classification():
    print("Testing async classification...")
    # 1. Send request
    text = "انت حمار وقح جدا"
    response = requests.post(f"{BASE_URL}/api/classify?text={text}&async_mode=True")
    
    if response.status_code != 200:
        print(f"FAILED to start task: {response.text}")
        return
    
    task_id = response.json().get("task_id")
    print(f"Task started. ID: {task_id}")
    
    # 2. Poll for status
    for _ in range(10):
        status_response = requests.get(f"{BASE_URL}/api/classify/status/{task_id}")
        if status_response.status_code != 200:
            print(f"FAILED to get status: {status_response.text}")
            break
            
        data = status_response.json()
        status = data.get("status")
        print(f"Current status: {status}")
        
        if status == "SUCCESS":
            result = data.get("result")
            print(f"Task completed successfully! Result: {result}")
            if result.get("label") == "bad":
                print("PASSED: Correctly classified as 'bad'.")
            else:
                print(f"FAILED: Expected 'bad', got {result.get('label')}")
            return
        
        time.sleep(2)
    
    print("FAILED: Task took too long or didn't reach SUCCESS status.")

if __name__ == "__main__":
    test_async_classification()
