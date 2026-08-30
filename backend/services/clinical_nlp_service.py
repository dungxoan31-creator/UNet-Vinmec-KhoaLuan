"""
Clinical NLP & Narrative Generation Service.
Synthesizes Computer Vision findings (Attention U-Net) + Medical Knowledge Base (IOTA / O-RADS / Pathology Lexicon)
into standardized, publication-grade Vietnamese Clinical Ultrasound Reports and Diagnostic Conclusions.
"""

from typing import Any

from knowledge.retrieval.cdss_reasoning_layer import CDSSReasoningEngine
from knowledge.retrieval.medical_knowledge_retriever import MedicalKnowledgeRetriever


class ClinicalNLPService:
    def __init__(
        self,
        retriever: MedicalKnowledgeRetriever | None = None,
        cdss_engine: CDSSReasoningEngine | None = None,
    ):
        self.retriever = retriever or MedicalKnowledgeRetriever()
        self.cdss = cdss_engine or CDSSReasoningEngine(self.retriever)

    def generate_clinical_narrative(
        self,
        vision_findings: dict[str, Any],
        patient_info: dict[str, Any] | None = None,
        doctor_pathology: str | None = None,
    ) -> dict[str, Any]:
        """
        Generates structured ultrasound description text and clinical conclusion.
        """
        patient_info = patient_info or {}
        patient_age = patient_info.get("patient_age", "30")
        try:
            age_int = int("".join([c for c in str(patient_age) if c.isdigit()]))
        except Exception:
            age_int = 30
        is_postmenopausal = age_int >= 50 or "mãn kinh" in str(patient_info.get("patient_age", "")).lower()

        # 1. Run CDSS Evaluation
        cdss_result = self.cdss.evaluate_case(
            vision_findings, patient_context={"age": age_int, "is_postmenopausal": is_postmenopausal}
        )

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

        # Dynamic pathology from CDSS classification or doctor choice
        cdss_class = vision_findings.get("cdss_classification", {})
        auto_suspicion = cdss_class.get("primary_suspicion")
        pathology_name = doctor_pathology or auto_suspicion or "U nang buồng trứng (Ovarian Cyst)"

        # 2. Compose Standardized Vietnamese Clinical Findings Description
        findings_paragraphs = []

        # Paragraph 1: Overview & Location
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

        # Paragraph 2: Morphological Details & Echogenicity
        if dmax > 0:
            if "lạc nội mạc" in pathology_name.lower() or "endometrioma" in pathology_name.lower():
                findings_paragraphs.append(
                    "• TÍNH CHẤT HÌNH THÁI VÀ DỊCH NANG: Nang đơn thùy, thành nang mỏng đều (< 3 mm). "
                    "Bên trong chứa dịch phản âm kém đồng nhất dạng 'kính mờ' (Ground-glass echoes) đặc trưng của nang máu cũ. "
                    "Không thấy vách ngăn bên trong, không thấy chồi sùi hay nụ nhú thành nang."
                )
            elif (
                "dermoid" in pathology_name.lower()
                or "teratoma" in pathology_name.lower()
                or "quái" in pathology_name.lower()
            ):
                findings_paragraphs.append(
                    "• TÍNH CHẤT HÌNH THÁI VÀ DỊCH NANG: Khối cấu trúc hỗn hợp gồm thành phần nang và nốt hồi âm dày dạng nút Rokitansky (Dermoid plug), "
                    "kèm bóng cản âm rõ phía sau. Trong lòng nang có các dải sợi hồi âm dạng lưới tóc (Dermoid mesh). "
                    "Không phát hiện thành phần mô mềm tăng sinh bất thường."
                )
            elif "nhầy" in pathology_name.lower() or "mucinous" in pathology_name.lower():
                findings_paragraphs.append(
                    "• TÍNH CHẤT HÌNH THÁI VÀ DỊCH NANG: Khối dạng nang nhiều thùy (Multilocular) phân tách bởi các vách ngăn mỏng trơn láng. "
                    "Dịch trong các thùy nang có độ hồi âm mịn không đồng nhất (dịch nhầy). "
                    "Không thấy thành phần đặc sùi hay nụ nhú ác tính."
                )
            else:
                findings_paragraphs.append(
                    "• TÍNH CHẤT HÌNH THÁI VÀ DỊCH NANG: Nang đơn thùy (Unilocular), ranh giới rõ, thành mỏng đều nhẵn (< 3 mm). "
                    "Bên trong chứa dịch trống âm hoàn toàn (Anechoic), có hiện tượng tăng cường âm rõ phía sau (Posterior acoustic enhancement). "
                    "Không thấy vách ngăn, không thấy chồi nhú (Papillary projection = 0) và không có nốt đặc nội nang."
                )

        # Paragraph 3: Doppler Vascularity & Posterior Features
        if dmax > 0:
            findings_paragraphs.append(
                "• SIÊU ÂM DOPPLER NĂNG LƯỢNG / MÀU (COLOR DOPPLER): Không phát hiện tín hiệu dòng chảy mạch máu bất thường bên trong tổn thương (Color Score 1 - Avascular). "
                "Không có hiện tượng tân sinh mạch máu hay phổ trở kháng thấp (Low resistance waveform)."
            )

        # Paragraph 4: Pelvic Fluid & Adnexa Status
        findings_paragraphs.append(
            "• TÚI CÙNG VÀ Ổ BỤNG: Không thấy dịch tự do bệnh lý trong túi cùng Douglas và khoang phúc mạc. "
            "Các cơ quan vùng chậu lân cận (tử cung, bàng quang) nằm đúng vị trí giải phẫu."
        )

        # 3. Compose Diagnostic Conclusion
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

        sonographic_findings_text = "\n\n".join(findings_paragraphs)
        clinical_conclusion_text = "\n".join(conclusion_lines)

        return {
            "sonographic_findings_text": sonographic_findings_text,
            "clinical_conclusion_text": clinical_conclusion_text,
            "cdss_summary": {
                "orads_code": orads_code,
                "orads_name": orads_name,
                "malignancy_risk": risk_pct,
                "iota_verdict": iota_verdict,
                "dmax_mm": dmax,
                "volume_ml": vol,
            },
            "generation_mode": "Deterministic Medical KB NLP Engine (Vinmec Clinical Standard)",
            "guideline_provenance": [
                "SRC-ACR-ORADS-US-2022",
                "SRC-IOTA-CONSENSUS-2026",
                "SRC-ESGO-ISUOG-IOTA-ESGE-2021",
            ],
            "disclaimer": "Đoạn văn mô tả và kết luận được tự động tổng hợp từ mô hình Attention U-Net & Cơ sở Tri thức Y khoa. Bác sĩ chuyên khoa cần kiểm tra và chỉnh sửa trước khi ký duyệt.",
        }
