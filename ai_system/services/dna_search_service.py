import logging
from typing import Dict, Any, List, Tuple, Set

logger = logging.getLogger(__name__)

# Standard forensic STR loci (e.g., CODIS core loci and other common markers)
STANDARD_STR_LOCI: Set[str] = {
    "CSF1PO", "FGA", "TH01", "TPOX", "vWA", 
    "D3S1358", "D5S818", "D7S820", "D8S1179", 
    "D13S317", "D16S539", "D18S51", "D21S11", 
    "D1S1656", "D2S1338", "D2S441", "D10S1248", 
    "D12S391", "D19S433", "D22S1045", "Penta D", 
    "Penta E", "AMEL" # AMEL is Amelogenin for sex determination
}


class DNASearchService:
    """
    Service for DNA STR (Short Tandem Repeat) profile analysis and matching.
    Supports direct identity comparison, parent-child compatibility, 
    and general kinship likelihood estimation.
    """

    @staticmethod
    def validate_profile(str_data: Dict[str, List[Any]]) -> Tuple[bool, List[str]]:
        """
        Validates the structure of a DNA STR profile.
        Checks that alleles are valid input types and each locus has 1 or 2 alleles.
        For standard loci, alleles must be numbers. For 'AMEL' (amelogenin), they must be 'X' or 'Y'.
        
        Args:
            str_data: Dictionary mapping loci to lists of alleles
            
        Returns:
            Tuple of (is_valid, list of error messages)
        """
        errors = []
        if not isinstance(str_data, dict):
            return False, ["STR data must be a dictionary."]
            
        for locus, alleles in str_data.items():
            if not isinstance(alleles, list):
                errors.append(f"Locus '{locus}' alleles must be a list.")
                continue
                
            if len(alleles) not in (1, 2):
                errors.append(f"Locus '{locus}' must have either 1 or 2 alleles (got {len(alleles)}).")
                
            for allele in alleles:
                if locus == "AMEL":
                    if not isinstance(allele, str) or allele not in ("X", "Y"):
                        errors.append(f"AMEL allele '{allele}' must be either 'X' or 'Y'.")
                else:
                    if not isinstance(allele, (int, float)):
                        errors.append(f"Allele '{allele}' in locus '{locus}' must be a number.")
                        
        return len(errors) == 0, errors

    @staticmethod
    def evaluate_direct_match(
        profile_a: Dict[str, List[float]], 
        profile_b: Dict[str, List[float]]
    ) -> Dict[str, Any]:
        """
        Compares two STR profiles to determine if they belong to the exact same person.
        Requires a 100% match across overlapping loci to be considered a positive identity.
        
        Args:
            profile_a: First STR profile data
            profile_b: Second STR profile data
            
        Returns:
            Dictionary containing match results (score, overlaps, matching/mismatched loci)
        """
        overlap_loci = set(profile_a.keys()) & set(profile_b.keys())
        
        # Exclude AMEL from similarity scoring as it only defines sex determination
        overlap_loci.discard("AMEL")
        
        if not overlap_loci:
            return {
                "match_score": 0.0,
                "overlap_count": 0,
                "matches": [],
                "mismatches": []
            }
            
        matching_loci = []
        mismatched_loci = []
        
        for locus in overlap_loci:
            # Sort alleles to allow order-independent exact equality checks
            alleles_a = sorted(profile_a[locus])
            alleles_b = sorted(profile_b[locus])
            
            if alleles_a == alleles_b:
                matching_loci.append(locus)
            else:
                mismatched_loci.append(locus)
                
        match_score = len(matching_loci) / len(overlap_loci)
        
        return {
            "match_score": round(match_score, 4),
            "overlap_count": len(overlap_loci),
            "matches": matching_loci,
            "mismatches": mismatched_loci
        }

    @staticmethod
    def evaluate_parent_child_kinship(
        child_profile: Dict[str, List[float]], 
        parent_profile: Dict[str, List[float]]
    ) -> Dict[str, Any]:
        """
        Evaluates a parent-child relationship compatibility.
        A biological child MUST inherit exactly one allele from each biological parent
        at every locus (mendelian inheritance rule).
        
        Args:
            child_profile: The child's STR profile
            parent_profile: The putative parent's STR profile
            
        Returns:
            Dictionary with kinship stats (compatibility score, exclusions, and compatibility ratio)
        """
        overlap_loci = set(child_profile.keys()) & set(parent_profile.keys())
        overlap_loci.discard("AMEL")
        
        if not overlap_loci:
            return {
                "kinship_score": 0.0,
                "overlap_count": 0,
                "compatible_loci": [],
                "incompatible_loci": []
            }
            
        compatible_loci = []
        incompatible_loci = []
        
        for locus in overlap_loci:
            child_alleles = child_profile[locus]
            parent_alleles = parent_profile[locus]
            
            # Parent and child must share at least one allele at this locus
            shared = set(child_alleles) & set(parent_alleles)
            if shared:
                compatible_loci.append(locus)
            else:
                incompatible_loci.append(locus)
                
        kinship_score = len(compatible_loci) / len(overlap_loci)
        
        return {
            "kinship_score": round(kinship_score, 4),
            "overlap_count": len(overlap_loci),
            "compatible_loci": compatible_loci,
            "incompatible_loci": incompatible_loci
        }

    @staticmethod
    def evaluate_sibling_kinship(
        profile_a: Dict[str, List[float]], 
        profile_b: Dict[str, List[float]]
    ) -> Dict[str, Any]:
        """
        Evaluates sibling kinship using Identity by State (IBS) scoring.
        Siblings can share 0, 1, or 2 alleles at any given locus.
        
        Scoring system:
          - Both alleles match (e.g. [12, 14] vs [12, 14]): 2 points
          - One allele matches (e.g. [12, 14] vs [12, 16]): 1 point
          - Zero alleles match (e.g. [12, 14] vs [15, 16]): 0 points
          
        Args:
            profile_a: First sibling STR profile
            profile_b: Second sibling STR profile
            
        Returns:
            Dictionary containing the sibling kinship ratio and detailed IBS scores
        """
        overlap_loci = set(profile_a.keys()) & set(profile_b.keys())
        overlap_loci.discard("AMEL")
        
        if not overlap_loci:
            return {
                "sibling_score": 0.0,
                "overlap_count": 0,
                "ibs_scores": {}
            }
            
        total_points = 0
        ibs_scores = {}
        
        for locus in overlap_loci:
            alleles_a = profile_a[locus]
            alleles_b = profile_b[locus]
            
            # Make copies to manipulate
            temp_a = list(alleles_a)
            temp_b = list(alleles_b)
            
            matches = 0
            # Calculate overlapping alleles with multiplicity (e.g., handles homozygous loci)
            for item in list(temp_a):
                if item in temp_b:
                    matches += 1
                    temp_a.remove(item)
                    temp_b.remove(item)
            
            # Cap matches at 2
            matches = min(matches, 2)
            ibs_scores[locus] = matches
            total_points += matches
            
        # Max points possible is 2 * overlap_count
        max_possible_points = 2 * len(overlap_loci)
        sibling_score = total_points / max_possible_points
        
        return {
            "sibling_score": round(sibling_score, 4),
            "overlap_count": len(overlap_loci),
            "ibs_scores": ibs_scores
        }

    def search_profiles(
        self,
        query_profile: Dict[str, List[float]],
        target_profiles: List[Dict[str, Any]],
        search_type: str = "direct",
        min_overlap: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Searches a query STR profile against a list of target STR profiles and ranks them.
        
        Args:
            query_profile: The source STR profile dict
            target_profiles: List of target records containing:
                             [{"id": "profile_1", "str_data": {...}, "metadata": {...}}]
            search_type: Type of match logic to use ("direct", "parent_child", "sibling")
            min_overlap: Minimum number of overlapping loci required to run evaluation
            
        Returns:
            Sorted list of matches containing search scores and profile references
        """
        # Validate query profile first
        is_valid, validation_errors = self.validate_profile(query_profile)
        if not is_valid:
            logger.warning(f"Invalid query DNA profile submitted: {validation_errors}")
            return []
            
        results = []
        
        for target in target_profiles:
            target_id = target.get("id")
            target_str = target.get("str_data")
            metadata = target.get("metadata") or {}
            
            if not target_str:
                continue
                
            # Perform verification
            if search_type == "direct":
                eval_res = self.evaluate_direct_match(query_profile, target_str)
                score_key = "match_score"
            elif search_type == "parent_child":
                eval_res = self.evaluate_parent_child_kinship(query_profile, target_str)
                score_key = "kinship_score"
            elif search_type == "sibling":
                eval_res = self.evaluate_sibling_kinship(query_profile, target_str)
                score_key = "sibling_score"
            else:
                logger.error(f"Unknown search type: {search_type}")
                continue
                
            overlap_count = eval_res.get("overlap_count", 0)
            if overlap_count < min_overlap:
                continue
                
            results.append({
                "target_id": target_id,
                "score": eval_res[score_key],
                "overlap_count": overlap_count,
                "details": eval_res,
                "metadata": metadata
            })
            
        # Sort in descending order based on similarity scores
        results.sort(key=lambda x: x["score"], reverse=True)
        return results
