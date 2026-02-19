from app.db.vector_db import VectorDB


def test_vectordb():
    db = VectorDB()
    assert db.insert('1', []) is True
