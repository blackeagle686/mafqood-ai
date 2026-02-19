from celery import shared_task


@shared_task
def process_text_task(text):
    # stub: compute embeddings and optionally classify
    return {"text": text}
