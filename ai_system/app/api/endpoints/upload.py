from fastapi import APIRouter, UploadFile, File, Form

router = APIRouter()


@router.post('/upload')
async def upload_file(file: UploadFile = File(...), metadata: str = Form(None)):
    """رفع الصور والنصوص — stub endpoint
    Accepts uploaded file and optional metadata.
    """
    return {"filename": file.filename, "metadata": metadata}
