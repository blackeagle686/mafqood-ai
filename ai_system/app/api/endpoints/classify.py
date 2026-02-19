from fastapi import APIRouter

router = APIRouter()


@router.post('/classify')
async def classify(text: str):
    """Classification API stub.
    """
    return {"text": text, "label": "unknown"}
