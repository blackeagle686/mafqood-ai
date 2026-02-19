from celery import shared_task


@shared_task
def upsert_vector_task(id, vector, metadata=None):
    # stub: insert/update into vector DB
    return {"id": id}
