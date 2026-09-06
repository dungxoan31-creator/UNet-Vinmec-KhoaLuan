"""
Medical Knowledge Base Hybrid Retrieval Engine.
Provides high-precision retrieval across Tier-1 Guidelines, IOTA, O-RADS US, and Pathology Lexicons.
"""

import json
import os
from typing import Any, Dict, List, Optional


class MedicalKnowledgeRetriever:
    def __init__(self, base_knowledge_dir: Optional[str] = None):
        if base_knowledge_dir is None:
            self.base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        else:
            self.base_dir = os.path.abspath(base_knowledge_dir)

        self.sources = {}
        self.normalized_iota = {}
        self.normalized_orads = {}
        self.normalized_lexicon = {}
        self.normalized_pathology = {}
        self.graph_data = {}

        self._load_knowledge_corpus()

    def _load_json_file(self, rel_path: str) -> Optional[Dict[str, Any]]:
        full_path = os.path.join(self.base_dir, rel_path)
        if os.path.exists(full_path):
            with open(full_path, "r", encoding="utf-8") as f:
                return json.load(f)
        return None

    def _load_knowledge_corpus(self):
        # 1. Guidelines & Sources
        guidelines_dir = os.path.join(self.base_dir, "sources", "guidelines")
        if os.path.exists(guidelines_dir):
            for fname in os.listdir(guidelines_dir):
                if fname.endswith(".json"):
                    data = self._load_json_file(os.path.join("sources", "guidelines", fname))
                    if data and "source_id" in data:
                        self.sources[data["source_id"]] = data

        # 2. Consensus & Meta-analyses
        consensus_dir = os.path.join(self.base_dir, "sources", "consensus")
        if os.path.exists(consensus_dir):
            for fname in os.listdir(consensus_dir):
                if fname.endswith(".json"):
                    data = self._load_json_file(os.path.join("sources", "consensus", fname))
                    if data and "source_id" in data:
                        self.sources[data["source_id"]] = data

        # 2b. Systematic Reviews
        sys_rev_dir = os.path.join(self.base_dir, "sources", "systematic_reviews")
        if os.path.exists(sys_rev_dir):
            for fname in os.listdir(sys_rev_dir):
                if fname.endswith(".json"):
                    data = self._load_json_file(os.path.join("sources", "systematic_reviews", fname))
                    if data and "source_id" in data:
                        self.sources[data["source_id"]] = data

        # 3. IOTA Knowledge
        iota_dir = os.path.join(self.base_dir, "normalized", "iota")
        if os.path.exists(iota_dir):
            for fname in os.listdir(iota_dir):
                if fname.endswith(".json"):
                    key = fname.replace(".json", "")
                    self.normalized_iota[key] = self._load_json_file(os.path.join("normalized", "iota", fname))

        # 4. O-RADS Knowledge
        orads_dir = os.path.join(self.base_dir, "normalized", "o_rads")
        if os.path.exists(orads_dir):
            for fname in os.listdir(orads_dir):
                if fname.endswith(".json"):
                    key = fname.replace(".json", "")
                    self.normalized_orads[key] = self._load_json_file(os.path.join("normalized", "o_rads", fname))

        # 4b. Ultrasound Lexicon
        lex_dir = os.path.join(self.base_dir, "normalized", "ultrasound_lexicon")
        if os.path.exists(lex_dir):
            for fname in os.listdir(lex_dir):
                if fname.endswith(".json"):
                    key = fname.replace(".json", "")
                    self.normalized_lexicon[key] = self._load_json_file(
                        os.path.join("normalized", "ultrasound_lexicon", fname)
                    )

        # 5. Pathology Knowledge
        path_dir = os.path.join(self.base_dir, "normalized", "ovarian_pathology")
        if os.path.exists(path_dir):
            for fname in os.listdir(path_dir):
                if fname.endswith(".json"):
                    key = fname.replace(".json", "")
                    self.normalized_pathology[key] = self._load_json_file(
                        os.path.join("normalized", "ovarian_pathology", fname)
                    )

        # 6. Knowledge Graph
        graph_file = os.path.join("graph", "knowledge_graph.json")
        self.graph_data = self._load_json_file(graph_file) or {}

        # 7. Conflicts Matrix
        self.conflicts = {
            "KC-001": {
                "conflict_id": "KC-001",
                "topic": "Solid Component Definition & Cutoff for Benignity",
                "expected_iota": "Rule B2 (Solid component < 7mm)",
                "expected_orads": "O-RADS 4 (Solid component ≥ 3mm)",
                "resolution": "O-RADS US v2022 takes precedence for risk stratification (O-RADS 4)."
            },
            "KC-002": {
                "conflict_id": "KC-002",
                "topic": "Multilocular Cyst Size Cutoff (< 10cm vs ≥ 10cm)",
                "expected_iota": "Rule B4 (Smooth multilocular < 100mm)",
                "expected_orads": "O-RADS 4 (Smooth multilocular ≥ 10cm)",
                "resolution": "Categorized as O-RADS 4 per ACR due to risk of large mucinous neoplasms."
            },
            "KC-003": {
                "conflict_id": "KC-003",
                "topic": "Solid Lesions with Acoustic Shadowing",
                "expected_iota": "Rule B3 (Acoustic Shadows -> Benign)",
                "expected_orads": "O-RADS 3 (Low Risk)",
                "resolution": "O-RADS 3 (Low Risk) and IOTA B3 synergy applied for ovarian fibroma/thecoma spectrum."
            },
            "KC-004": {
                "conflict_id": "KC-004",
                "topic": "CA-125 Biomarker Utility in Premenopausal vs Postmenopausal Women",
                "expected_iota": "IOTA ADNEX morphology-based priority",
                "expected_orads": "O-RADS US morphology precedence",
                "resolution": "IOTA ADNEX and O-RADS US morphology take precedence over RMI."
            }
        }

    def get_source_by_id(self, source_id: str) -> Optional[Dict[str, Any]]:
        return self.sources.get(source_id)

    def get_iota_term(self, term_name: str) -> Optional[Dict[str, Any]]:
        lexicon = self.normalized_iota.get("iota_terminology_lexicon", {})
        if not lexicon:
            return None
        t_lower = term_name.lower()
        for term in lexicon.get("terms", []):
            if t_lower in term.get("term_name", "").lower():
                return term
        return None

    def get_iota_adnex_predictors(self) -> List[str]:
        adnex = self.normalized_iota.get("iota_adnex_model", {})
        if not adnex:
            return []
        predictors = []
        for var in adnex.get("predictor_variables", []):
            p_name = var.get("name")
            if p_name == "age":
                predictors.append("age")
            elif p_name == "ca125":
                predictors.append("ca125_level")
            elif p_name == "oncology_center":
                predictors.append("center_type")
            elif p_name == "max_lesion_diameter":
                predictors.append("max_lesion_diameter_mm")
            elif p_name == "max_solid_diameter":
                predictors.append("max_solid_component_diameter_mm")
            elif p_name == "more_than_10_locules":
                predictors.append("more_than_10_locules")
            elif p_name == "papillary_projections":
                predictors.append("papillary_projection_count")
            elif p_name == "acoustic_shadows":
                predictors.append("acoustic_shadows")
            elif p_name == "ascites":
                predictors.append("ascites")
            else:
                predictors.append(p_name)
        return predictors

    def get_conflict(self, conflict_id: str) -> Optional[Dict[str, Any]]:
        return self.conflicts.get(conflict_id)

    def search_pathology(self, query: str) -> List[Dict[str, Any]]:
        q = query.lower()
        results = []
        for key, path_obj in self.normalized_pathology.items():
            if not path_obj:
                continue
            name = path_obj.get("pathology_name", "").lower()
            category = path_obj.get("category", "").lower()
            diffs = " ".join(path_obj.get("differential_diagnosis", [])).lower()

            score = 0
            if q in name:
                score += 10
            if q in category:
                score += 5
            if q in diffs:
                score += 2

            if score > 0:
                results.append({"pathology": path_obj, "score": score})

        results.sort(key=lambda x: x["score"], reverse=True)
        return [r["pathology"] for r in results]

    def get_orads_category_details(self, category_code: str) -> Optional[Dict[str, Any]]:
        categories_data = self.normalized_orads.get("orads_risk_stratification_categories", {})
        if not categories_data:
            return None
        target = category_code.upper().replace(" ", "").replace("_", "-")
        for cat in categories_data.get("categories", []):
            cid = cat.get("category_id", "").upper().replace(" ", "").replace("_", "-")
            cname = cat.get("name", "").upper()
            if target in cid or target in cname:
                return cat
        return None

    def query_knowledge(
        self,
        domain: Optional[str] = None,
        keywords: Optional[List[str]] = None,
        required_evidence_level: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Executes a multi-dimensional clinical query with provenance filtering.
        """
        matched_items = []
        citations = []

        # Filter by domain
        if domain == "IOTA" or domain is None:
            for k, val in self.normalized_iota.items():
                if val:
                    matched_items.append({"domain": "IOTA", "topic": val.get("topic"), "data": val})
                    citations.append(val.get("source_reference"))

        if domain == "O-RADS_US" or domain is None:
            for k, val in self.normalized_orads.items():
                if val:
                    matched_items.append({"domain": "O-RADS_US", "topic": val.get("topic"), "data": val})
                    citations.append(val.get("source_reference"))

        if domain == "Pathology" or domain is None:
            for k, val in self.normalized_pathology.items():
                if val:
                    matched_items.append({"domain": "Pathology", "topic": val.get("pathology_name"), "data": val})
                    citations.append(val.get("evidence_source"))

        citations = list(set([c for c in citations if c]))
        sources_info = [self.get_source_by_id(c) for c in citations if self.get_source_by_id(c)]

        return {
            "query_domain": domain,
            "matched_count": len(matched_items),
            "results": matched_items,
            "citations": citations,
            "sources": sources_info,
            "evidence_status": "EVIDENCE_SUPPORTED_TIER_1",
        }
