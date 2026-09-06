# Ollama Hybrid Clinical Reasoning Engine Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and integrate a local Ollama LLM clinical reasoning service into the FastAPI backend for ovarian ultrasound AI diagnosis, with seamless fallback to deterministic medical KB NLP rules when Ollama is unavailable.

**Architecture:** A dedicated `OllamaService` handles HTTP communications with the local Ollama daemon (`http://localhost:11434`), generating structured Vietnamese clinical narratives based on Attention U-Net geometric measurements and IOTA/O-RADS features. The `ClinicalNLPService` orchestrates LLM invocation with a fail-safe fallback to the deterministic Medical KB template engine.

**Tech Stack:** Python 3.11+, FastAPI, Pydantic v2, httpx, PyTest, Ollama REST API.

**Spec:** [docs/superpowers/specs/2026-09-01-ollama-clinical-reasoning-design.md](file:///C:/Users/PeaceD/Documents/Kh-a-lu-n/docs/superpowers/specs/2026-09-01-ollama-clinical-reasoning-design.md)

## Global Constraints

- **Python Runtime**: Python >= 3.10 (Project configured for Python 3.11).
- **Ollama REST API**: Host `http://localhost:11434`, default model `qwen2.5:7b` (configurable via `OLLAMA_MODEL` env).
- **Fallback Rule**: ZERO downtime, ZERO unhandled HTTP exception on missing/offline Ollama. Must fallback seamlessly to `Deterministic Medical KB NLP Engine`.
- **Language**: Publication-grade Vietnamese medical terminology for sonographic findings & diagnostic conclusions.

---

### Task 1: `OllamaService` Core Client Module

**Files:**
- Create: `backend/services/ollama_service.py`
- Test: `tests/test_ollama_service.py`

**Interfaces:**
- Consumes: Ollama REST API (`POST http://localhost:11434/api/generate`)
- Produces: `OllamaService.generate_narrative(cdss_findings: dict, patient_info: dict) -> dict`

- [ ] **Step 1: Write failing unit test for `OllamaService`**

```python
# tests/test_ollama_service.py
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv\Scripts\python -m unittest tests/test_ollama_service.py`  
Expected: FAIL with `ModuleNotFoundError: No module named 'backend.services.ollama_service'`

- [ ] **Step 3: Implement `backend/services/ollama_service.py`**

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv\Scripts\python -m unittest tests/test_ollama_service.py`  
Expected: PASS (2 tests passed)

- [ ] **Step 5: Commit**

```bash
git add backend/services/ollama_service.py tests/test_ollama_service.py
git commit -m "feat(nlp): add OllamaService client for local LLM clinical reasoning"
```

---

### Task 2: Hybrid Orchestration in `ClinicalNLPService` & Fallback Layer

**Files:**
- Modify: `backend/services/clinical_nlp_service.py:13-168`
- Modify/Create: `tests/test_hybrid_clinical_nlp.py`

**Interfaces:**
- Consumes: `OllamaService`, `CDSSReasoningEngine`
- Produces: `ClinicalNLPService.generate_clinical_narrative(..., use_ollama=True)`

- [ ] **Step 1: Write failing unit test for hybrid fallback in `ClinicalNLPService`**

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv\Scripts\python -m unittest tests/test_hybrid_clinical_nlp.py`  
Expected: FAIL due to unexpected keyword argument `use_ollama` or missing import.

- [ ] **Step 3: Update `backend/services/clinical_nlp_service.py`**

```python
"""
Clinical NLP & Narrative Generation Service:
Synthesizes Attention U-Net Computer Vision findings + Medical Knowledge Base (IOTA / O-RADS) + Ollama Local LLM Reasoning.
Includes fail-safe automatic fallback to deterministic Medical KB.
"""
from typing import Any, Dict, Optional
from knowledge.retrieval.cdss_reasoning_layer import CDSSReasoningEngine
from knowledge.retrieval.medical_knowledge_retriever import MedicalKnowledgeRetriever
from backend.services.ollama_service import OllamaService, OllamaServiceException


class ClinicalNLPService:
    def __init__(
        self,
        retriever: Optional[MedicalKnowledgeRetriever] = None,
        cdss_engine: Optional[CDSSReasoningEngine] = None,
        ollama_service: Optional[OllamaService] = None,
    ):
        self.retriever = retriever or MedicalKnowledgeRetriever()
        self.cdss = cdss_engine or CDSSReasoningEngine(self.retriever)
        self.ollama = ollama_service or OllamaService()

    def generate_clinical_narrative(
        self,
        vision_findings: Dict[str, Any],
        patient_info: Optional[Dict[str, Any]] = None,
        doctor_pathology: Optional[str] = None,
        use_ollama: bool = True,
    ) -> Dict[str, Any]:
        """
        Generates structured ultrasound description text and clinical conclusion.
        Uses Ollama Local LLM when available & enabled; falls back to Deterministic KB if unavailable.
        """
        patient_info = patient_info or {}
        patient_age = patient_info.get("patient_age", "30")
        try:
            age_int = int("".join([c for c in str(patient_age) if c.isdigit()]))
        except Exception:
            age_int = 30
        is_postmenopausal = age_int >= 50 or "mãn kinh" in str(patient_info.get("patient_age", "")).lower()

        # 1. Run CDSS Evaluation (IOTA & O-RADS v2022)
        cdss_result = self.cdss.evaluate_case(
            vision_findings, patient_context={"age": age_int, "is_postmenopausal": is_postmenopausal}
        )

        # 2. Attempt Ollama Local LLM Reasoning if enabled
        if use_ollama:
            try:
                ollama_res = self.ollama.generate_narrative(
                    cdss_findings=cdss_result,
                    patient_info=patient_info
                )
                return {
                    "sonographic_findings_text": ollama_res["sonographic_findings_text"],
                    "clinical_conclusion_text": ollama_res["clinical_conclusion_text"],
                    "cdss_summary": {
                        "orads_code": cdss_result.get("orads_stratification", {}).get("category_code"),
                        "orads_name": cdss_result.get("orads_stratification", {}).get("category_name"),
                        "malignancy_risk": cdss_result.get("orads_stratification", {}).get("malignancy_risk"),
                        "iota_verdict": cdss_result.get("iota_evaluation", {}).get("verdict"),
                    },
                    "generation_mode": f"Ollama Local LLM Clinical Reasoning ({ollama_res.get('model_used', 'qwen2.5:7b')})",
                    "guideline_provenance": [
                        "SRC-ACR-ORADS-US-2022",
                        "SRC-IOTA-CONSENSUS-2026",
                        "SRC-OLLAMA-LOCAL-LLM"
                    ],
                    "disclaimer": "Văn bản chẩn đoán được tổng hợp tự động bởi Ollama Local LLM & CDSS Engine. Bác sĩ cần thẩm định trước khi ký duyệt."
                }
            except OllamaServiceException as e:
                print(f"[ClinicalNLPService] Ollama LLM notice: {e} -> Reverting to Deterministic Medical KB Engine.")

        # 3. Deterministic Fallback Pipeline
        meas = cdss_result.get("measurements_summary", {})
        dmax = meas.get("dmax_mm", 0.0)
        dorth = meas.get("dorth_mm", 0.0)
        d3 = meas.get("d3_mm", 0.0)
        vol = meas.get("volume_ml", 0.0)

        orads = cdss_result.get("orads_stratification", {})
        orads_code = orads.get("category_code", "O-RADS 2")
        orads_name = orads.get("category_name", "Almost Certainly Benign")
        risk_pct = orads.get("malignancy_risk", "< 1%")
        orads_mgmt = orads.get("management_recommendation", "Theo dõi định kỳ.")

        iota = cdss_result.get("iota_evaluation", {})
        iota_verdict = iota.get("verdict", "BENIGN")
        b_rules = iota.get("b_rules_met", [])
        m_rules = iota.get("m_rules_met", [])

        cdss_class = vision_findings.get("cdss_classification", {})
        auto_suspicion = cdss_class.get("primary_suspicion")
        pathology_name = doctor_pathology or auto_suspicion or "U nang buồng trứng (Ovarian Cyst)"

        findings_paragraphs = []
        if dmax == 0:
            findings_paragraphs.append(
                "• BUỒNG TRỨNG HAI BÊN: Kích thước và cấu trúc nhu mô trong giới hạn bình thường. "
                "Thấy các nang noãn sinh lý kích thước đều, phân bố ngoại vi, không có tổn thương khu trú dạng u."
            )
        else:
            findings_paragraphs.append(
                f"• KHẢO SÁT TỔN THƯƠNG PHẦN PHỤ: Phát hiện khối cấu trúc dạng nang tại vùng buồng trứng/phần phụ. "
                f"Kích thước đo đạc trên 3 bình diện trực giao: D1 (Trục lớn nhất) = {dmax:.1f} mm, "
                f"D2 (Trục trực giao) = {dorth:.1f} mm, D3 (Chiều sâu) = {d3:.1f} mm. "
                f"Thể tích ước tính theo công thức Elip elipsoid (chuẩn ISUOG): V = {vol:.2f} mL."
            )
            findings_paragraphs.append(
                "• TÍNH CHẤT HÌNH THÁI VÀ DỊCH NANG: Nang đơn thùy (Unilocular), ranh giới rõ, thành mỏng đều nhắn (< 3 mm). "
                "Bên trong chứa dịch trống âm hoàn toàn (Anechoic), có hiện tượng tăng cường âm rõ phía sau. "
                "Không thấy vách ngăn, không thấy chồi nhú và không có nốt đặc nội nang."
            )
            findings_paragraphs.append(
                "• SIÊU ÂM DOPPLER NĂNG LƯỢNG / MÀU: Không phát hiện tín hiệu dòng chảy mạch máu bất thường (Color Score 1)."
            )

        findings_paragraphs.append(
            "• TÚI CÙNG VÀ Ổ BỤNG: Không thấy dịch tự do bệnh lý trong túi cùng Douglas và khoang phúc mạc."
        )

        conclusion_lines = []
        if dmax == 0:
            conclusion_lines.append("1. Hình ảnh siêu âm buồng trứng hai bên bình thường (O-RADS 1).")
            conclusion_lines.append("2. Chưa phát hiện bất thường phụ khoa khu trú trên siêu âm.")
        else:
            conclusion_lines.append(f"1. Hình ảnh tổn thương dạng nang buồng trứng theo dõi: {pathology_name}.")
            conclusion_lines.append(
                f"2. Phân tầng nguy cơ ACR O-RADS US v2022: {orads_code} ({orads_name}) — Tỉ lệ nguy cơ ác tính ước tính: {risk_pct}."
            )
            if b_rules:
                b_str = ", ".join(b_rules)
                conclusion_lines.append(f"3. Phù hợp tiêu chuẩn lành tính IOTA Simple Rules ({b_str}).")
            if m_rules:
                m_str = ", ".join(m_rules)
                conclusion_lines.append(f"3. CẢNH BÁO IOTA: Có dấu hiệu nghi ngờ ác tính ({m_str}).")
            conclusion_lines.append(f"4. Đề xuất lâm sàng: {orads_mgmt}")

        return {
            "sonographic_findings_text": "\n\n".join(findings_paragraphs),
            "clinical_conclusion_text": "\n".join(conclusion_lines),
            "cdss_summary": {
                "orads_code": orads_code,
                "orads_name": orads_name,
                "malignancy_risk": risk_pct,
                "iota_verdict": iota_verdict,
                "dmax_mm": dmax,
                "volume_ml": vol,
            },
            "generation_mode": "Deterministic Medical KB NLP Engine (Fallback)",
            "guideline_provenance": [
                "SRC-ACR-ORADS-US-2022",
                "SRC-IOTA-CONSENSUS-2026",
                "SRC-ESGO-ISUOG-IOTA-ESGE-2021",
            ],
            "disclaimer": "Đoạn văn mô tả và kết luận được tự động tổng hợp từ mô hình Attention U-Net & Cơ sở Tri thức Y khoa. Bác sĩ chuyên khoa cần kiểm tra và chỉnh sửa trước khi ký duyệt.",
        }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv\Scripts\python -m unittest tests/test_hybrid_clinical_nlp.py`  
Expected: PASS (2 tests passed)

- [ ] **Step 5: Commit**

```bash
git add backend/services/clinical_nlp_service.py tests/test_hybrid_clinical_nlp.py
git commit -m "feat(nlp): implement hybrid Ollama LLM + deterministic KB fallback in ClinicalNLPService"
```

---

### Task 3: API Endpoints & FastAPI Integration

**Files:**
- Modify: `backend/app/routers/reviews.py:78-97`
- Modify: `backend/app/routers/v1_endpoints.py:115-135`
- Test: `tests/test_v1_endpoints.py`

**Interfaces:**
- Consumes: `ClinicalNLPService.generate_clinical_narrative`
- Produces: `POST /api/generate-narrative` and `POST /api/v1/cdss/evaluate` with `use_ollama` parameter

- [ ] **Step 1: Write failing API test in `tests/test_v1_endpoints.py`**

```python
# Add method to TestV1Endpoints in tests/test_v1_endpoints.py
def test_05_generate_narrative_with_ollama_flag(self):
    payload = {
        "vision_findings": {"max_diameter_mm": 42.0, "ortho_diameter_mm": 30.0},
        "patient_info": {"patient_age": "34"},
        "use_ollama": True
    }
    r = self.client.post("/api/generate-narrative", json=payload)
    self.assertEqual(r.status_code, 200)
    data = r.json()
    self.assertIn("generation_mode", data)
    self.assertIn("sonographic_findings_text", data)
```

- [ ] **Step 2: Run test to verify current output**

Run: `.venv\Scripts\python -m pytest tests/test_v1_endpoints.py -k test_05_generate_narrative_with_ollama_flag`  
Expected: Verify `generation_mode` field presence.

- [ ] **Step 3: Update `backend/app/routers/reviews.py`**

```python
@router.post("/api/generate-narrative")
def generate_clinical_narrative(payload: dict):
    """
    Generates natural language sonographic findings description and diagnostic conclusion
    by combining Attention U-Net geometric measurements, Medical Knowledge Base (IOTA / O-RADS),
    and Ollama Local LLM reasoning (with automatic deterministic fallback).
    """
    try:
        vision_findings = payload.get("vision_findings", {})
        patient_info = payload.get("patient_info", {})
        doctor_pathology = payload.get("pathology_name", None)
        use_ollama = payload.get("use_ollama", True)

        result = nlp_service.generate_clinical_narrative(
            vision_findings=vision_findings,
            patient_info=patient_info,
            doctor_pathology=doctor_pathology,
            use_ollama=use_ollama,
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi khi sinh mô tả lâm sàng: {e!s}")
```

- [ ] **Step 4: Run full test suite to verify 100% green PASS**

Run: `.venv\Scripts\python -m pytest -v`  
Expected: All tests PASS (52+ passed).

- [ ] **Step 5: Commit**

```bash
git add backend/app/routers/reviews.py tests/test_v1_endpoints.py
git commit -m "feat(api): expose use_ollama parameter in generate-narrative endpoint"
```

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-09-01-ollama-clinical-reasoning.md`. Two execution options:

1. **Subagent-Driven (recommended)** - Dispatch a fresh subagent per task, review between tasks, fast iteration.
2. **Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints.

Which approach would you like to take?
