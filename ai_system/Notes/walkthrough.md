# Face Embedding Pipeline and Vector DB Walkthrough

This walkthrough covers the implementation of the production-ready CV pipeline for face detection/embedding and its integration with ChromaDB.

## Changes Made

### 1. Vector DB Integration
Implemented a robust `VectorDB` class in `app/db/vector_db.py` using ChromaDB.
- **Persistence**: Data is stored in `./chroma_db` (configurable).
- **Search**: Uses cosine similarity for vector comparison.
- **Methods**: `upsert`, `search`, `delete`, and `get_count`.

### 2. CV Pipeline
Implemented a clean, interface-driven pipeline in `app/core/cv_pipeline.py`.
- **Face Detection**: Uses `RetinaFace` for high-accuracy detection.
- **Face Embedding**: Uses `InsightFace` (buffalo_l) for high-quality feature extraction.
- **Singleton Model Loader**: Models are loaded once and reused across requests to save memory and CPU.
- **Error Handling**: Comprehensive try-except blocks and logging throughout the pipeline.

### 3. Configuration & Dependencies
- Updated `app/config.py` with configurable paths and model settings.
- Added necessary dependencies to `requirements.txt`.

### 3. API Endpoints
Implemented fully asynchronous and synchronous endpoints in `app/api/endpoints/cv.py`.
- **POST `/cv/process`**: Uploads an image and dispatches it for background processing (asynchronous). Returns a `task_id`.
- **POST `/cv/search`**: Uploads an image, processes it immediately, and searches for matches in ChromaDB (synchronous).
- **GET `/cv/health`**: Simple health check for the CV service.

### 4. Background Processing (Celery)
- **Task**: `process_image_task` handles the full CV pipeline and vector database insertion.
- **Scaling**: Configured to work with Celery's `--autoscale`. Workers load models once using a Singleton pattern to optimize RAM.

## How to Verify

### API Verification
You can use `curl` or Postman to test the endpoints:

**Process Image (Background):**
```bash
curl -X POST -F "file=@person.jpg" http://localhost:8000/cv/process
```

**Search Face (Immediate):**
```bash
curl -X POST -F "file=@target.jpg" http://localhost:8000/cv/search
```

### 5. Web Interface (Templates)
Implemented a clean, premium frontend using Vanilla CSS and Jinja2 templates.
- **Landing Page**: Overview of the system and quick navigation.
- **Report Page**: Form to upload missing person images and details (name, last seen, etc.).
- **Search Page**: Interface to upload an image and find matches via vector search.
- **Results Page**: Displays matching faces with similarity percentages and metadata.

## How to Verify Frontend

1.  **Start the Server**: `uvicorn app.main:app --reload`.
2.  **Access the UI**: Open `http://localhost:8000` in your browser.
3.  **Test Reporting**: Use the "تبليغ عن مفقود" page to upload an image and details. This will trigger a Celery task.
4.  **Test Searching**: Use the "بحث عن شخص" page to find matches. This will run a real-time vector search.

## Deployment Note
The `Dockerfile` has been updated to use `app.main:app` as the entry point, ensuring both the API and the web interface are served.

---
*The system is now fully equipped with a modern UI and a robust AI backend.*

### Manual Verification on GPU Server
- Deploy to the GPU server.
- Start workers: `celery -A app.celery_app worker --loglevel=info --autoscale=10,3`.
- Upload sample images to the `/cv/process` and `/cv/search` endpoints.
- Monitor logs for "Found X faces" and successful ChromaDB upserts.
- Verify that the worker count adjusts based on task load.

## 📹 Video Analysis Pipeline (CCTV)

A new pipeline for analyzing video files and CCTV footage has been implemented.

### 1. Video Frame Sampling
The `VideoProcessor` in `app/core/video_pipeline.py` uses `OpenCV` to read video files and sample frames at a configurable rate (e.g., every 15 frames).

### 2. Async Video Processing
Large video files are processed in the background using Celery:
- **Task**: `process_video_task` in `app/tasks/cv_tasks.py`.
- **Flow**: Upload -> Temp Save -> Celery Sampling -> Face Detection -> Vector Search -> Result Aggregation.

### 3. Video Search UI
A new page `/video_search` allows users to upload video files, configure sampling rates, and start the analysis.

### How to Verify Video Analysis
1. Access `http://localhost:8000/video_search`.
2. Upload a video containing faces.
3. Check the Celery worker logs for "Processing frame X at Y.Ys".
4. The API returns a list of all matches found throughout the video with their respective timestamps.
