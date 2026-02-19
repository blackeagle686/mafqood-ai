from celery import shared_task


@shared_task
def cluster_task(items):
    # stub: run clustering job
    return {"count": len(items)}
