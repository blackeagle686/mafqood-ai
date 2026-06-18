from abc import ABC, abstractmethod
from typing import List, Dict, Any

class IDNARepository(ABC):
    """Abstract interface for DNA Profile data access."""
    
    @abstractmethod
    def add_profile(self, profile: Dict[str, Any]) -> bool:
        """Add a new DNA profile to the database."""
        pass
    
    @abstractmethod
    def get_unresolved_profiles_for_matching(self) -> List[Dict[str, Any]]:
        """
        Retrieves all unresolved DNA profiles formatted as generic dictionaries.
        """
        pass

    @abstractmethod
    def get_all_profiles(self) -> List[Dict[str, Any]]:
        """
        Retrieves all DNA profiles.
        """
        pass



