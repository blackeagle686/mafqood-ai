from abc import ABC, abstractmethod
from typing import Dict, Any, Optional

class IFaceRepository(ABC):
    """Abstract interface for Face Search operations."""
    
    @abstractmethod
    def add_face(self, image_path:str, meta_data: Dict[str, Any]) -> bool:
        """Add a new face to the database."""
        pass

    @abstractmethod
    def search_face(self, image_path: str, n_results: int = 5, cleanup: bool = True, use_age_progression: bool = True) -> Dict[str, Any]:
        """Search for similar faces in the database."""
        pass

