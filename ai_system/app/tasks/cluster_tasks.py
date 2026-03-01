from celery import shared_task
from app.core.clustering_agent import ClusteringAgent
import logging

logger = logging.getLogger(__name__)

@shared_task(bind=True, max_retries=3)
def perform_clustering_task(self):
    """
    Heavy background task that runs the ML clustering (DBSCAN) 
    over the entire vector database and updates metadata.
    """
    logger.info("Executing background perform_clustering_task...")
    try:
        agent = ClusteringAgent()
        results = agent.perform_clustering()
        logger.info(f"Clustering task completed: {results}")
        return results
    except Exception as e:
        logger.error(f"Error in perform_clustering_task: {e}")
        self.retry(exc=e, countdown=60)

@shared_task
def evaluate_and_trigger_clustering():
    """
    Scheduled task (via Celery Beat) meant to run periodically (e.g. every 15 mins).
    Evaluates if enough new data was added to warrant a full DB re-cluster.
    """
    logger.info("Evaluating if system requires re-clustering...")
    try:
        agent = ClusteringAgent()
        needs_clustering = agent.evaluate_system_state()
        
        if needs_clustering:
            logger.info("System evaluation determined clustering is needed. Triggering...")
            perform_clustering_task.delay()
            return {"status": "triggered"}
        else:
            logger.info("System evaluation determined clustering is NOT needed.")
            return {"status": "skipped"}
            
    except Exception as e:
        logger.error(f"Error evaluating system state: {e}")
        return {"status": "error", "message": str(e)}
