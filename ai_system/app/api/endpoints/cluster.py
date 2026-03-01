from fastapi import APIRouter, HTTPException, BackgroundTasks
from app.tasks.cluster_tasks import perform_clustering_task
from app.core.clustering_agent import ClusteringAgent
import logging

logger = logging.getLogger(__name__)
router = APIRouter()
agent = ClusteringAgent()

@router.post('/cluster/trigger')
async def trigger_cluster():
    """
    Manually triggers the clustering algorithm to run over the VectorDB.
    Runs asynchronously via Celery.
    """
    try:
        # Dispatch Celery task
        task = perform_clustering_task.delay()
        return {"status": "queued", "task_id": task.id, "message": "Clustering job triggered in background."}
    except Exception as e:
        logger.error(f"Error triggering cluster: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get('/cluster/results')
async def get_cluster_results(cluster_id: int = None):
    """
    Retrieves the grouped results from the VectorDB organized by their cluster_id.
    """
    try:
        results = agent.get_cluster_results(cluster_id=cluster_id)
        return results
    except Exception as e:
        logger.error(f"Error fetching cluster results: {e}")
        raise HTTPException(status_code=500, detail=str(e))
