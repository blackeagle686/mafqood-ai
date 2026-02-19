from app.core import cv_pipeline


def test_preprocess():
    res = cv_pipeline.preprocess_image('path')
    assert isinstance(res, dict)
