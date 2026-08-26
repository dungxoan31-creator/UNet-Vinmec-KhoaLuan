"""
Medical Knowledge Base (KB) Retrieval, Ground Truth, and Clinical Decision Support Test Suite.
Verifies compliance with Tier-1 Clinical Guidelines (IOTA, ACR O-RADS, ESGO/ISUOG).
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from knowledge.retrieval.cdss_reasoning_layer import CDSSReasoningEngine
from knowledge.retrieval.medical_knowledge_retriever import MedicalKnowledgeRetriever


class TestMedicalKnowledgeBase(unittest.TestCase):
    def setUp(self):
        self.retriever = MedicalKnowledgeRetriever()
        self.cdss = CDSSReasoningEngine(self.retriever)

    def test_01_sources_corpus_integrity(self):
        """Verify that all Tier-1 sources are loaded with verified metadata."""
        sources = self.retriever.sources
        self.assertIn("SRC-ACR-ORADS-US-2022", sources)
        self.assertIn("SRC-IOTA-CONSENSUS-2026", sources)
        self.assertIn("SRC-ESGO-ISUOG-IOTA-ESGE-2021", sources)
        self.assertIn("SRC-IOTA-ADNEX-BMJ-2014", sources)
        self.assertIn("SRC-IOTA-SIMPLE-RULES-2016", sources)

        # Check metadata fields
        src = sources["SRC-ACR-ORADS-US-2022"]
        self.assertEqual(src["organization"], "American College of Radiology (ACR)")
        self.assertEqual(src["audit_status"], "VERIFIED_PRIMARY_SOURCE")
        print(f"[PASS] Sources Loaded: {len(sources)} Tier-1 guidelines and consensus documents")

    def test_02_iota_terminology_and_rules_retrieval(self):
        """Verify that IOTA terms and rules are accurately retrievable."""
        lexicon = self.retriever.normalized_iota.get("iota_terminology_lexicon")
        self.assertIsNotNone(lexicon)
        terms = {t["term_name"]: t for t in lexicon.get("terms", [])}

        self.assertIn("Papillary Projection", terms)
        pap = terms["Papillary Projection"]
        self.assertIn("≥ 3.0 mm", pap["definition"])
        self.assertEqual(pap["confidence"], "high")

        # Check Simple Rules
        rules = self.retriever.normalized_iota.get("iota_simple_rules")
        self.assertIsNotNone(rules)
        self.assertEqual(len(rules["benign_descriptors_rules"]), 5)
        self.assertEqual(len(rules["malignant_descriptors_rules"]), 5)
        print("[PASS] IOTA Terms & Simple Rules verified with verbatim clinical definitions")

    def test_03_orads_categories_and_management(self):
        """Verify ACR O-RADS risk categories and management guidelines."""
        orads_2 = self.retriever.get_orads_category_details("ORADS-2")
        self.assertIsNotNone(orads_2)
        self.assertEqual(orads_2["risk_of_malignancy"], "< 1%")

        orads_5 = self.retriever.get_orads_category_details("ORADS-5")
        self.assertIsNotNone(orads_5)
        self.assertEqual(orads_5["risk_of_malignancy"], "≥ 50%")
        print("[PASS] O-RADS US Risk Categories & Management verified")

    def test_04_ovarian_pathology_search(self):
        """Verify search and differential diagnosis of ovarian pathology."""
        res_dermoid = self.retriever.search_pathology("teratoma")
        self.assertGreaterEqual(len(res_dermoid), 1)
        self.assertEqual(res_dermoid[0]["pathology_name"], "Mature Cystic Teratoma (Dermoid Cyst)")
        self.assertIn("Rokitansky Nodule", res_dermoid[0]["classic_ultrasound_triad"]["feature_1"])

        res_endometrioma = self.retriever.search_pathology("endometrioma")
        self.assertGreaterEqual(len(res_endometrioma), 1)
        self.assertEqual(res_endometrioma[0]["pathology_name"], "Ovarian Endometrioma (Chocolate Cyst)")
        print("[PASS] Ovarian Pathology Lexicon & Ultrasound Triads verified")

    def test_05_cdss_benign_case_reasoning(self):
        """
        Verify CDSS evaluation on a classic benign unilocular simple cyst.
        """
        vision = {
            "max_diameter_mm": 42.0,
            "ortho_diameter_mm": 35.0,
            "has_solid_component": False,
            "papillary_projections_count": 0,
            "acoustic_shadowing": False,
            "fluid_echogenicity": "anechoic",
            "locules_count": 1,
            "color_score": 1,
        }
        res = self.cdss.evaluate_case(vision, patient_context={"age": 32, "is_postmenopausal": False})

        self.assertEqual(res["orads_stratification"]["category_code"], "O-RADS 2")
        self.assertEqual(res["orads_stratification"]["malignancy_risk"], "< 1%")
        self.assertEqual(res["iota_evaluation"]["verdict"], "BENIGN (Satisfies IOTA B-Rules)")
        self.assertIn("SRC-ACR-ORADS-US-2022", res["citations"])
        print(
            f"[PASS] CDSS Benign Evaluation: {res['orads_stratification']['category_code']} ({res['orads_stratification']['malignancy_risk']})"
        )

    def test_06_cdss_malignant_high_risk_case_reasoning(self):
        """
        Verify CDSS evaluation on a suspicious multilocular-solid tumor with ascites.
        """
        vision = {
            "max_diameter_mm": 115.0,
            "ortho_diameter_mm": 88.0,
            "has_solid_component": True,
            "max_solid_diameter_mm": 35.0,
            "papillary_projections_count": 5,
            "acoustic_shadowing": False,
            "fluid_echogenicity": "mixed",
            "locules_count": 4,
            "color_score": 4,
            "has_ascites": True,
        }
        res = self.cdss.evaluate_case(vision, patient_context={"age": 62, "is_postmenopausal": True})

        self.assertEqual(res["orads_stratification"]["category_code"], "O-RADS 5")
        self.assertEqual(res["orads_stratification"]["malignancy_risk"], "≥ 50%")
        self.assertEqual(res["iota_evaluation"]["verdict"], "MALIGNANT (Satisfies IOTA M-Rules)")
        self.assertIn("M2: Presence of ascites", res["iota_evaluation"]["m_rules_met"])
        self.assertIn("M3: ≥ 4 papillary projections", res["iota_evaluation"]["m_rules_met"])
        self.assertIn("M5: Very strong blood flow (Color Score 4)", res["iota_evaluation"]["m_rules_met"])
        print(f"[PASS] CDSS Malignant Evaluation: {res['orads_stratification']['category_code']} with 3 M-rules")

    def test_07_cdss_uncertainty_triggering(self):
        """
        Verify that clinical uncertainty alert is raised when a solid component has no Doppler flow.
        """
        vision = {
            "max_diameter_mm": 28.0,
            "ortho_diameter_mm": 20.0,
            "has_solid_component": True,
            "max_solid_diameter_mm": 12.0,
            "papillary_projections_count": 0,
            "acoustic_shadowing": False,
            "fluid_echogenicity": "anechoic",
            "locules_count": 1,
            "color_score": 1,
        }
        res = self.cdss.evaluate_case(vision, patient_context={"age": 29})
        self.assertTrue(res["uncertainty_evaluation"]["is_uncertain"])
        self.assertGreaterEqual(len(res["uncertainty_evaluation"]["clinical_alerts"]), 1)
        print("[PASS] CDSS Uncertainty Detection & Advisory Alert verified")


if __name__ == "__main__":
    unittest.main()
