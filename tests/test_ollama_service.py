import unittest
from unittest.mock import patch, MagicMock
from backend.services.ollama_service import OllamaService, OllamaServiceException

class TestOllamaService(unittest.TestCase):
    def setUp(self):
        self.service = OllamaService(ollama_host="http://localhost:11434", model_name="qwen2.5:7b", timeout_seconds=2.0)

    @patch("httpx.Client.post")
    def test_01_ollama_success_response(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "response": '{"sonographic_findings_text": "Thấy nang đơn thùy 35mm.", "clinical_conclusion_text": "U nang thanh dịch buồng trứng (O-RADS 2)."}'
        }
        mock_post.return_value = mock_resp

        cdss_findings = {
            "measurements_summary": {"dmax_mm": 35.0, "dorth_mm": 25.0, "d3_mm": 30.0, "volume_ml": 13.7},
            "orads_stratification": {"category_code": "O-RADS 2", "category_name": "Almost Certainly Benign", "malignancy_risk": "< 1%"},
            "iota_evaluation": {"verdict": "BENIGN", "b_rules_met": ["B1: Unilocular cyst"]}
        }
        res = self.service.generate_narrative(cdss_findings, patient_info={"patient_age": "32"})
        self.assertIn("sonographic_findings_text", res)
        self.assertIn("clinical_conclusion_text", res)
        self.assertEqual(res["model_used"], "qwen2.5:7b")

    @patch("httpx.Client.post")
    def test_02_ollama_connection_error_raises_exception(self, mock_post):
        import httpx
        mock_post.side_effect = httpx.ConnectError("Could not connect to Ollama")
        cdss_findings = {"measurements_summary": {"dmax_mm": 35.0}}
        with self.assertRaises(OllamaServiceException):
            self.service.generate_narrative(cdss_findings)

if __name__ == "__main__":
    unittest.main()
