import pytest
from services.dna_search_service import DNASearchService

class TestDNASearchService:
    
    @pytest.fixture
    def sample_profiles(self):
        # A child
        child = {
            "D3S1358": [15, 16],
            "vWA": [14, 17],
            "TH01": [6, 9.3],
            "FGA": [20, 24],
            "AMEL": [X, Y] if 'X' in globals() else ["X", "Y"] # handled as strings/numbers below
        }
        # Parent (shares one allele at each locus)
        father = {
            "D3S1358": [16, 18], # shares 16
            "vWA": [17, 18],    # shares 17
            "TH01": [9.3, 10],  # shares 9.3
            "FGA": [20, 22],    # shares 20
        }
        # Unrelated person
        unrelated = {
            "D3S1358": [12, 14], # no match
            "vWA": [15, 16],    # no match
            "TH01": [7, 8],      # no match
            "FGA": [21, 23],    # no match
        }
        # Sibling (shares some alleles, some homozygous, some heterozygous)
        sibling = {
            "D3S1358": [15, 16], # shares 2 alleles (2 pts)
            "vWA": [14, 18],    # shares 1 allele (1 pt)
            "TH01": [6, 7],     # shares 1 allele (1 pt)
            "FGA": [21, 25],    # shares 0 alleles (0 pts)
        }
        return {
            "child": child,
            "father": father,
            "unrelated": unrelated,
            "sibling": sibling
        }

    def test_validate_profile(self):
        # Valid profile
        valid = {"vWA": [14, 17], "TH01": [6.0]}
        is_valid, errors = DNASearchService.validate_profile(valid)
        assert is_valid is True
        assert len(errors) == 0

        # Invalid: not numeric alleles
        invalid_type = {"vWA": ["fourteen", 17]}
        is_valid, errors = DNASearchService.validate_profile(invalid_type)
        assert is_valid is False
        assert any("must be a number" in err for err in errors)

        # Invalid: too many alleles
        invalid_count = {"vWA": [14, 15, 16]}
        is_valid, errors = DNASearchService.validate_profile(invalid_count)
        assert is_valid is False
        assert any("either 1 or 2 alleles" in err for err in errors)

        # Invalid: not list
        invalid_structure = {"vWA": 14}
        is_valid, errors = DNASearchService.validate_profile(invalid_structure)
        assert is_valid is False
        assert any("must be a list" in err for err in errors)

    def test_evaluate_direct_match(self, sample_profiles):
        child = sample_profiles["child"]
        
        # Perfect self match (ignoring AMEL)
        res = DNASearchService.evaluate_direct_match(child, child)
        assert res["match_score"] == 1.0
        assert res["overlap_count"] == 4 # AMEL excluded
        
        # No overlap at all
        res = DNASearchService.evaluate_direct_match({"TH01": [6, 7]}, {"vWA": [12, 14]})
        assert res["match_score"] == 0.0
        assert res["overlap_count"] == 0
        
        # Partial match
        part_a = {"TH01": [6, 7], "vWA": [12, 14]}
        part_b = {"TH01": [6, 7], "vWA": [13, 14]} # vWA different order-independent checks
        res = DNASearchService.evaluate_direct_match(part_a, part_b)
        assert res["match_score"] == 0.5
        assert "TH01" in res["matches"]
        assert "vWA" in res["mismatches"]

    def test_evaluate_parent_child_kinship(self, sample_profiles):
        child = sample_profiles["child"]
        father = sample_profiles["father"]
        unrelated = sample_profiles["unrelated"]
        
        # Perfect parent-child sharing
        res = DNASearchService.evaluate_parent_child_kinship(child, father)
        assert res["kinship_score"] == 1.0
        assert len(res["compatible_loci"]) == 4
        assert len(res["incompatible_loci"]) == 0
        
        # Non-parent check
        res = DNASearchService.evaluate_parent_child_kinship(child, unrelated)
        assert res["kinship_score"] == 0.0
        assert len(res["compatible_loci"]) == 0
        assert len(res["incompatible_loci"]) == 4

    def test_evaluate_sibling_kinship(self, sample_profiles):
        child = sample_profiles["child"]
        sibling = sample_profiles["sibling"]
        unrelated = sample_profiles["unrelated"]
        
        # Sibling match (D3S1358=2, vWA=1, TH01=1, FGA=0 -> 4 pts out of 8 possible)
        res = DNASearchService.evaluate_sibling_kinship(child, sibling)
        assert res["sibling_score"] == 0.5
        assert res["ibs_scores"]["D3S1358"] == 2
        assert res["ibs_scores"]["vWA"] == 1
        assert res["ibs_scores"]["TH01"] == 1
        assert res["ibs_scores"]["FGA"] == 0
        
        # Unrelated sibling match (D3S1358=0, vWA=0, TH01=0, FGA=0 -> 0 pts)
        res = DNASearchService.evaluate_sibling_kinship(child, unrelated)
        assert res["sibling_score"] == 0.0

    def test_search_profiles(self, sample_profiles):
        query = sample_profiles["child"]
        targets = [
            {"id": "father_profile", "str_data": sample_profiles["father"]},
            {"id": "sibling_profile", "str_data": sample_profiles["sibling"]},
            {"id": "unrelated_profile", "str_data": sample_profiles["unrelated"]}
        ]
        
        # Kinship parent_child search (min_overlap=3 since profiles only have 4 loci in common)
        results = DNASearchService().search_profiles(query, targets, search_type="parent_child", min_overlap=3)
        assert len(results) == 3
        # Father must rank first
        assert results[0]["target_id"] == "father_profile"
        assert results[0]["score"] == 1.0
        # Sibling should be second (shares alleles at D3S1358, vWA, TH01, but not FGA)
        assert results[1]["target_id"] == "sibling_profile"
        assert results[1]["score"] == 0.75
        # Unrelated should be last
        assert results[2]["target_id"] == "unrelated_profile"
        assert results[2]["score"] == 0.0
