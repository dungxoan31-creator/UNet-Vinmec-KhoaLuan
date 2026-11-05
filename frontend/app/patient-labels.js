export function patientRecordLabel(record) {
  const name = String(record?.patient_name || "").trim();
  if (name) return `Hồ sơ tại cơ sở: ${name}`;
  const researchId = String(record?.patient_id || "").trim();
  return researchId ? `Mã nghiên cứu (giả danh): ${researchId}` : "Không gắn hồ sơ bệnh nhân";
}

export function researchIdentifierLabel(researchId) {
  return researchId
    ? `Mã nghiên cứu (giả danh): ${researchId}`
    : "Chưa cấp mã nghiên cứu";
}
