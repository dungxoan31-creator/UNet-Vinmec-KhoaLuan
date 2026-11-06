const LABELS = {
  chocolate_cyst: "Nang lạc nội mạc tử cung",
  serous_cystadenoma: "U nang tuyến thanh dịch",
  teratoma: "U quái",
  theca_cell_tumor: "U tế bào vỏ",
  simple_cyst: "Nang đơn giản",
  normal_ovary: "Buồng trứng bình thường",
  mucinous_cystadenoma: "U nang tuyến nhầy",
  high_grade_serous_cystadenocarcinoma: "Ung thư biểu mô tuyến thanh dịch độ cao",
};

export function classificationText(result) {
  if (!result) return "Ảnh chưa có kết quả phân loại. Chạy phân tích AI để cập nhật.";
  if (!['PREDICTED', 'ABSTAIN'].includes(result.status))
    return "Mô hình phân loại hiện không khả dụng. Kết quả phân đoạn vẫn được giữ.";
  const ranked = Object.entries(result.probabilities || {})
    .filter(([key, value]) => LABELS[key] && Number.isFinite(value) && value >= 0 && value <= 1)
    .sort((a, b) => b[1] - a[1]);
  if (!ranked.length) return "Kết quả phân loại không hợp lệ; cần chạy lại.";
  const labelVi = result.suggested_label_vi || LABELS[result.suggested_label] || 'Chưa xác định';
  const categoryStr = result.pathology_category ? ` · ${result.pathology_category}` : '';
  const header = result.status === 'ABSTAIN'
    ? `Chưa đủ tin cậy để đề xuất nhãn${result.abstain_reason ? ` (${result.abstain_reason})` : ''}.`
    : `Nhãn ảnh được đề xuất: ${labelVi}${categoryStr}.`;
  return `${header}\nBa nhóm có điểm cao nhất: ${ranked.slice(0, 3).map(([key, value]) => `${LABELS[key]}: ${(value * 100).toFixed(1)}%`).join('; ')}.\nĐiểm AI chưa hiệu chuẩn, không phải xác suất mắc bệnh. Bác sĩ cần đối chiếu ảnh và xác nhận kết quả.`;
}

// A deliberate reviewer action adds provenance without replacing their findings.
export function classificationNote(result, existing = "") {
  const label = LABELS[result?.suggested_label];
  if (result?.status !== 'PREDICTED' || !label) return null;
  const line = `Gợi ý AI (RUO, chưa xác nhận): ${label}.`;
  if (existing.includes(line)) return existing;
  return existing.trim() ? `${existing}\n${line}` : line;
}
