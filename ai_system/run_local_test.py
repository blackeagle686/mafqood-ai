import os
import sys

# Set environment variables for local testing
os.environ["CELERY_ALWAYS_EAGER"] = "True"
os.environ["CHROMA_DB_PATH"] = "./chroma_db_test"
# os.environ["INSIGHTFACE_OFFLINE"] = "1" # Use for real model

# Add paths to sys.path
sys.path.append(os.path.abspath("."))
sys.path.append(os.path.abspath("./app"))

import django
from django.conf import settings

# Initialize Django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "app.mafqood_project.settings")
django.setup()

from services.face_search_service import FaceSearchService
from infra.repositories.vector_db_repo import VectorDB
import shutil

def run_test():
    print("🚀 Starting Local Core Flow Test with REAL data...")
    
    # Initialize components
    vdb = VectorDB()
    service = FaceSearchService()
    
    print(f"📊 Current Face Count: {vdb.get_count()}")
    
    # Use a REAL image from the project
    test_image = "images_vdb/mo-cly-1.jpg"
    if not os.path.exists(test_image):
         print(f"❌ Could not find {test_image}. Please make sure it exists.")
         return

    print(f"📥 Indexing real image: {test_image}")
    index_res = service.index_image(test_image, metadata={"name": "Mo Cly", "status": "missing"})
    print(f"✅ Index Result: {index_res}")
    
    print("🔎 Searching for the same face...")
    # Searching with the same image should yield a high similarity match
    search_res = service.search_face_by_image(test_image, n_results=1, cleanup=False)
    print(f"✅ Search Result: {search_res}")
    
    if search_res.get("status") == "success" and search_res.get("search_results"):
        match = search_res["search_results"][0]
        sim = match["similarity"]
        person_name = match["metadata"].get("name", "Unknown")
        print(f"⭐ Match Found! Name: {person_name}, Similarity: {sim}%")
    else:
        print("❌ No match found or search failed.")

if __name__ == "__main__":
    try:
        run_test()
    except Exception as e:
        print(f"💥 Test Failed: {e}")
