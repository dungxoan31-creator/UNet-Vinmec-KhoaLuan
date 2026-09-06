"""
Ollama Local LLM Clinical Reasoning Service for Ovarian Ultrasound System.
"""
import json
import os
import httpx
from typing import Any, Dict, Optional

class OllamaServiceException(Exception):
    """Custom exception raised when Ollama service is unreachable or errors."""
    pass

class OllamaService:
    def __init__(
        self,
        ollama_host: Optional[str] = None,
        model_name: Optional[str] = None,
        timeout_seconds: float = 3.5
    ):
        self.ollama_host = ollama_host or os.getenv("OLLAMA_HOST", "http://localhost:11434")
        self.model_name = model_name or os.getenv("OLLAMA_MODEL", "qwen2.5:7b")
        self.timeout_seconds = float(timeout_seconds)

    def is_available(self) -> bool:
        """Quick health check to verify if Ollama daemon is live."""
        try:
            with httpx.Client(timeout=1.5) as client:
                r = client.get(f"{self.ollama_host}/api/tags")
                return r.status_code == 200
        except Exception:
            return False

    def generate_narrative(
        self,
        cdss_findings: Dict[str, Any],
        patient_info: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Sends structured CDSS ultrasound findings to local Ollama LLM
        and parses pure JSON response containing medical narrative.
        """
        patient_info = patient_info or {}
        patient_age = patient_info.get("patient_age", "30-39")

        system_prompt = (
            "Bạn là Bác sĩ Chuyên khoa Chẩn đoán Hình ảnh Sản Phụ khoa giàu kinh nghiệm tại Bệnh viện ĐKQT Vinmec. "
            "Nhiệm vụ của bạn là nhận các đặc trưng siêu âm buồng trứng đã trích xuất và tổng hợp thành đoạn văn mô tả "
            "hình thái và kết luận chẩn đoán bằng tiếng Việt chuẩn y khoa.\n"
            "BẮT BUỘC trả về định dạng JSON duy nhất như sau:\n"
            "{\n"
            '  "sonographic_findings_text": "Mô tả chi tiết hình thái, kích thước, cấu trúc nang, dịch túi cùng...",\n'
            '  "clinical_conclusion_text": "Kết luận chẩn đoán phân tầng O-RADS, IOTA và hướng xử lý..."\n'
            "}"
        )

        user_prompt = f"""
[THÔNG TIN BỆNH NHÂN]: Tuổi / Nhóm tuổi: {patient_age}
[TỔNG HỢP ĐẶC TRƯƠNG TỔN THƯƠNG]:
{json.dumps(cdss_findings, ensure_ascii=False, indent=2)}

Vui lòng sinh đoạn văn mô tả kết quả siêu âm và kết luận chẩn đoán y khoa.
"""

        payload = {
            "model": self.model_name,
            "prompt": f"{system_prompt}\n\n{user_prompt}",
            "stream": False,
            "format": "json",
            "options": {
                "temperature": 0.2,
                "top_p": 0.9
            }
        }

        try:
            with httpx.Client(timeout=self.timeout_seconds) as client:
                resp = client.post(f"{self.ollama_host}/api/generate", json=payload)
                if resp.status_code != 200:
                    raise OllamaServiceException(f"Ollama returned status code {resp.status_code}")
                
                res_data = resp.json()
                raw_response = res_data.get("response", "")
                parsed_json = json.loads(raw_response)
                
                return {
                    "sonographic_findings_text": parsed_json.get("sonographic_findings_text", ""),
                    "clinical_conclusion_text": parsed_json.get("clinical_conclusion_text", ""),
                    "model_used": self.model_name,
                    "success": True
                }
        except Exception as e:
            raise OllamaServiceException(f"Ollama LLM execution failed: {e}")
