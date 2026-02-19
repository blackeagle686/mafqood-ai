from fastapi import FastAPI
from app.api import router as api_router


def test_api_router():
    app = FastAPI()
    app.include_router(api_router)
    assert app is not None
