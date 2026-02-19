from app.core import nlp_pipeline


def test_embedding():
    emb = nlp_pipeline.text_to_embedding('hello')
    assert isinstance(emb, list)
