export async function imageSourceBlob(source) {
  if (!source.startsWith("data:")) {
    const response = await fetch(source);
    if (!response.ok) throw new Error("Không tải được ảnh nguồn.");
    return response.blob();
  }

  const comma = source.indexOf(",");
  if (comma < 0) throw new Error("Định dạng ảnh nguồn không hợp lệ.");
  const metadata = source.slice(5, comma);
  const payload = source.slice(comma + 1);
  const mimeType = metadata.split(";")[0] || "application/octet-stream";
  if (!metadata.split(";").includes("base64"))
    return new Blob([decodeURIComponent(payload)], { type: mimeType });
  const binary = atob(payload);
  const bytes = Uint8Array.from(binary, (character) =>
    character.charCodeAt(0),
  );
  return new Blob([bytes], { type: mimeType });
}
