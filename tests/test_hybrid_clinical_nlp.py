# tests/test_hybrid_clinical_nlp.py
import unittest
from unittest.mock import patch
from backend.services.clinical_nlp_service import ClinicalNLPService


class TestHybridClinicalNLP(unittest.TestCase):
    def setUp(self):
        self.nlp = ClinicalNLPService()

    @patch("backend.services.ollama_service.OllamaService.generate_narrative")
    def test_01_use_ollama_success(self, mock_ollama_gen):
        mock_ollama_gen.return_value = {
            "sonographic_findings_text": "Ollama Findings Text Test",
            "clinical_conclusion_text": "Ollama Conclusion Text Test",
            "model_used": "qwen2.5:7b",
            "success": True
        }
        findings = {"max_diameter_mm": 35.0, "ortho_diameter_mm": 25.0}
        res = self.nlp.generate_clinical_narrative(findings, use_ollama=True)
        self.assertIn("Ollama Findings Text Test", res["sonographic_findings_text"])
        self.assertIn("Ollama Local LLM", res["generation_mode"])

    @patch("backend.services.ollama_service.OllamaService.generate_narrative")
    def test_02_ollama_fallback_to_deterministic(self, mock_ollama_gen):
        from backend.services.ollama_service import OllamaServiceException
        mock_ollama_gen.side_effect = OllamaServiceException("Service Offline")
        
        findings = {"max_diameter_mm": 35.0, "ortho_diameter_mm": 25.0}
        res = self.nlp.generate_clinical_narrative(findings, use_ollama=True)
        self.assertIn("Deterministic Medical KB NLP Engine", res["generation_mode"])
        self.assertIn("KHẢO SÁT TỔN THƯƠNG PHẦN PHỤ", res["sonographic_findings_text"])


if __name__ == "__main__":
    unittest.main()
