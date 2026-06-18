from core.interfaces.dna_repository import IDNARepository
from typing import List, Dict, Any
from app.ai.models import DNAProfile

class DjangoDNARepository(IDNARepository):
    """Django ORM implementation of the IDNARepository."""
    
    def add_profile(self, profile: Dict[str, Any]) -> bool:
        """Add a new DNA profile to the database."""
        # Typically handled via signals or direct model creation elsewhere.
        return True

    def get_all_profiles(self) -> List[Dict[str, Any]]:
        """Retrieves all DNA profiles."""
        db_profiles = DNAProfile.objects.select_related('post').all()
        targets = []
        for p in db_profiles:
            targets.append({
                "id": p.post.post_id,
                "str_data": p.str_data,
                "metadata": {
                    "userId": p.post.user_id, 
                    "postType": "missing" if p.post.post_type == 0 else "found"
                }
            })
        return targets

    def get_unresolved_profiles_for_matching(self) -> List[Dict[str, Any]]:
        db_profiles = DNAProfile.objects.filter(post__is_resolved=False)
        targets = []
        for p in db_profiles:
            targets.append({
                "id": p.post.post_id,
                "str_data": p.str_data,
                "metadata": {
                    "userId": p.post.user_id, 
                    "postType": "missing" if p.post.post_type == 0 else "found"
                }
            })
        return targets
