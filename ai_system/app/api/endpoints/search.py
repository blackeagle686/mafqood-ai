from fastapi import APIRouter

router = APIRouter()


@router.get('/search')
async def search(q: str):
    """Search endpoint (stub) — searches Chroma vector DB.
    """
    return {"query": q, "results": []}
