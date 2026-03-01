import logging
from typing import Dict, Any, List, Optional
import numpy as np
from sklearn.cluster import DBSCAN
from app.db.vector_db import VectorDB

logger = logging.getLogger(__name__)

class ClusteringAgent:
    """
    Intelligent agent responsible for monitoring the missing persons database
    and autonomously grouping similar faces and cases into clusters.
    """
    
    def __init__(self, eps_threshold: float = 0.4, min_samples: int = 2):
        """
        Args:
            eps_threshold: The maximum distance between two samples for one to be considered 
                           as in the neighborhood of the other. Since we use Cosine Distance 
                           (where 0 is identical), an eps of 0.3 to 0.5 is usually good for faces.
            min_samples: The number of samples in a neighborhood for a point to be considered 
                         as a core point.
        """
        self.vdb = VectorDB()
        self.eps = eps_threshold
        self.min_samples = min_samples
        
    def evaluate_system_state(self) -> bool:
        """
        Background monitoring logic. Dynamically checks if the system needs a re-cluster.
        For example, triggers if X new cases were added since the last run.
        """
        try:
            total_cases = self.vdb.get_count()
            logger.info(f"System Check: Total cases in DB: {total_cases}")
            
            # Simple threshold logic: Only cluster if we have enough data points.
            # In a production scenario, we would track delta since last run here.
            if total_cases >= self.min_samples:
                return True
            return False
        except Exception as e:
            logger.error(f"Error evaluating system state: {e}")
            return False

    def perform_clustering(self) -> Dict[str, Any]:
        """
        Fetches all vectors, runs DBSCAN clustering, and updates metadata.
        Returns statistics of the clustered data.
        """
        logger.info("Initializing clustering operation...")
        
        try:
            # 1. Fetch all embeddings and metadata from DB
            data = self.vdb.collection.get(include=['embeddings', 'metadatas', 'documents'])
            
            ids = data.get('ids', [])
            embeddings = data.get('embeddings', [])
            metadatas = data.get('metadatas', [])
            
            if not ids or not embeddings:
                return {"status": "success", "message": "No data available to cluster."}
            
            # 2. Convert to numpy array
            X = np.array(embeddings)
            
            # 3. Apply DBSCAN Clustering
            # We use 'cosine' metric because our vectors are normalized face embeddings.
            clustering = DBSCAN(eps=self.eps, min_samples=self.min_samples, metric='cosine').fit(X)
            labels = clustering.labels_
            
            n_clusters = len(set(labels)) - (1 if -1 in labels else 0)
            n_noise = list(labels).count(-1)
            
            logger.info(f"Clustering complete. Found {n_clusters} clusters and {n_noise} un-clustered cases.")
            
            # 4. Update Database Metadata with cluster assignments
            for i, label in enumerate(labels):
                if not metadatas[i]:
                    metadatas[i] = {}
                
                # Update specific metadata field for the cluster ID.
                # Label -1 means "Noise" or unclustered.
                metadatas[i]['cluster_id'] = int(label)
                
            # Upsert the updated metadata back to ChromaDB
            self.vdb.collection.update(
                ids=ids,
                metadatas=metadatas
            )
            
            return {
                "status": "success",
                "total_cases_processed": len(ids),
                "n_clusters": n_clusters,
                "n_noise_cases": n_noise,
                "message": "Clustering successful."
            }
            
        except Exception as e:
            logger.error(f"Failed to perform clustering: {e}")
            return {"status": "error", "message": str(e)}

    def get_cluster_results(self, cluster_id: Optional[int] = None) -> Dict[str, Any]:
        """
        Fetches cases grouped by their cluster_id from the databases.
        If cluster_id is specified, returns only cases from that cluster.
        """
        try:
            where_clause = None
            if cluster_id is not None:
                where_clause = {"cluster_id": cluster_id}
                
            # Fetch data with filtering
            data = self.vdb.collection.get(
                where=where_clause,
                include=['metadatas']
            )
            
            ids = data.get('ids', [])
            metadatas = data.get('metadatas', [])
            
            # Group the results locally if no specific cluster was asked for
            grouped_results = {}
            for i, meta in enumerate(metadatas):
                c_id = meta.get('cluster_id', -1)
                
                if c_id not in grouped_results:
                    grouped_results[c_id] = []
                    
                grouped_results[c_id].append({
                    "id": ids[i],
                    "metadata": meta
                })
                
            return {
                "status": "success",
                "total_fetched": len(ids),
                "clusters": grouped_results
            }
            
        except Exception as e:
            logger.error(f"Error fetching cluster results: {e}")
            return {"status": "error", "message": str(e)}
