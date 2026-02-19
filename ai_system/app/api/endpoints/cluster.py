from fastapi import APIRouter

router = APIRouter()


@router.post('/cluster')
async def cluster(data: dict):
    """Clustering API stub.
    """
    return {"status": "ok", "clusters": []}
