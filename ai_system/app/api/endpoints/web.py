from fastapi import APIRouter, Request, UploadFile, File, Form, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
import os
import shutil
import uuid
from typing import Optional
from app.core.cv_pipeline import FaceCVPipeline
from app.db.vector_db import VectorDB
from app.tasks.cv_tasks import process_image_task

router = APIRouter()

# Setup templates
templates = Jinja2Templates(directory="app/templates")

TEMP_DIR = "temp_uploads"
os.makedirs(TEMP_DIR, exist_ok=True)

@router.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@router.get("/video_search", response_class=HTMLResponse)
async def video_search_page(request: Request):
    return templates.TemplateResponse("video_search.html", {"request": request})

@router.get("/report", response_class=HTMLResponse)
async def report_page(request: Request):
    return templates.TemplateResponse("report.html", {"request": request})

@router.get("/search", response_class=HTMLResponse)
async def search_page(request: Request):
    return templates.TemplateResponse("search.html", {"request": request})

@router.post("/search/results", response_class=HTMLResponse)
async def search_results(
    request: Request, 
    file: UploadFile = File(...)
):
    try:
        # Save temp file
        ext = os.path.splitext(file.filename)[1]
        temp_path = os.path.join(TEMP_DIR, f"web_search_{uuid.uuid4()}{ext}")
        
        with open(temp_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        # Run pipeline synchronously for immediate results
        pipeline = FaceCVPipeline()
        results = pipeline.process_image(temp_path)
        
        # Cleanup
        if os.path.exists(temp_path):
            os.remove(temp_path)
            
        if not results:
            return templates.TemplateResponse("results.html", {"request": request, "results": []})
            
        # Search Vector DB
        query_embedding = results[0].embedding
        vdb = VectorDB()
        search_res = vdb.search(query_embedding=query_embedding, n_results=10)
        
        # Format results for template
        formatted_results = []
        if search_res and "ids" in search_res and search_res["ids"]:
            for i in range(len(search_res["ids"][0])):
                dist = search_res["distances"][0][i]
                formatted_results.append({
                    "id": search_res["ids"][0][i],
                    "distance": dist,
                    "metadata": search_res["metadatas"][0][i],
                    "similarity": round(100 * (1 - dist), 1)
                })
        
        return templates.TemplateResponse("results.html", {
            "request": request, 
            "results": formatted_results,
            "faces_found": len(results)
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/api/cv/process")
async def handle_report(
    file: UploadFile = File(...),
    name: str = Form(...),
    last_seen: str = Form(...),
    details: Optional[str] = Form(None)
):
    """
    Handle the form submission from the report page.
    Saves metadata and dispatches CV task.
    """
    try:
        # Save uploaded file
        ext = os.path.splitext(file.filename)[1]
        temp_filename = f"{uuid.uuid4()}{ext}"
        temp_path = os.path.join(TEMP_DIR, temp_filename)
        
        with open(temp_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        # Dispatch task to Celery with metadata
        metadata = {
            "name": name,
            "last_seen": last_seen,
            "details": details
        }
        abs_path = os.path.abspath(temp_path)
        process_image_task.delay(abs_path, metadata)
        
        return {"status": "success", "message": "تم استلام البلاغ ويجري معالجته حالياً."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
