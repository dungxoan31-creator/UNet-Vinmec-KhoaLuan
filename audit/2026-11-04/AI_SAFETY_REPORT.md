## 7. AI và an toàn lâm sàng

**Đã chạy:** source decode ảnh synthetic 640×480; upload association L; segmentation inference; classifier whole image với ABSTAIN; calibration persistence; review saved notes/O-RADS; report original/overlay của image được lưu. RLE response 512×512 và source geometry/provenance có sẵn. Mask synthetic rỗng nên đây không phải kiểm chứng pixel alignment của contour thật. 23 unit tests gồm geometry/source-contract, report draft, patient store, voice capability/failure handling và classification UI; test source-pattern không thay thế browser/phantom evidence.

**Giới hạn model:** chỉ đọc manifest/implementation, không chạy lại benchmark hoặc huấn luyện. Không dùng validation-selection metrics như independent test. MMOTU official-split manifest tự khai image-level, patient-level independence=false, no test split và no Vinmec data; các khai báo này chỉ PARTIALLY VERIFIED trong lượt này. Không kiểm chứng license dataset hoặc upstream pathology labels. Không có accuracy/sensitivity/clinical utility claim từ ảnh synthetic.

**CDSS:** missing descriptors fail closed; O-RADS bác sĩ nhập không được gọi là AI-confirmed. Không chạy đối chiếu đầy đủ O-RADS v2022, mọi IOTA Simple Rules/ADNEX combination, coefficients, eligibility population, conflicting descriptors hoặc multi-lesion aggregation. Những hạng mục này cần reference set được chuyên gia phê duyệt. Nguồn ACR đã xác minh cho finding thuật ngữ tại [clinical-sources.md](clinical-sources.md).

**Release blockers ngoài issue count:** health/capabilities công bố clinical_production_ready=false, clinical_validation_status=BLOCKED, case_workflow=false, research_export=false, postgresql_supported=false. Clinical PDF endpoint trả 501. Đây là product limitation có chủ đích của RUO, không tính là functional defect giả để tăng số lỗi. Nó vẫn chặn sứ mệnh triển khai chăm sóc người bệnh. Không có phê duyệt ký số hay validated doctor-confirmation workflow đầy đủ được chứng minh.


See [full report](REPORT.md) and [complete issue register](ISSUE_REGISTER.md) for evidence, priorities and limitations.
