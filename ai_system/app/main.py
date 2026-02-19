from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from app.api import router as api_router
import os

app = FastAPI(
    title="مفقود - نظام البحث عن المفقودين بالذكاء الاصطناعي",
    description="نظام متقدم للتعرف على الوجوه والبحث الشعاعي لمساعدة العائلات في العثور على ذويهم.",
    version="1.0.0"
)

# Ensure static directory exists
os.makedirs("app/static", exist_ok=True)

# Mount static files for CSS/JS
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Include all API and Web routes
app.include_router(api_router)

@app.get("/health")
async def health_check():
    return {"status": "ok", "message": "Nizami is running smoothly."}
