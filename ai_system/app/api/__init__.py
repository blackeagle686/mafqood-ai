from fastapi import APIRouter

router = APIRouter()

from .endpoints import upload, search, classify, cluster, cv, web

router.include_router(web.router, tags=["Web Interface"])
router.include_router(upload.router, prefix="/api")
router.include_router(search.router, prefix="/api")
router.include_router(classify.router, prefix="/api")
router.include_router(cluster.router, prefix="/api")
router.include_router(cv.router, prefix="/cv", tags=["Computer Vision"])
