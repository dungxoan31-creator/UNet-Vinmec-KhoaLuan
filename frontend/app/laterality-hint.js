const LEFT_TOKENS = new Set(["l", "left", "trai"]);
const RIGHT_TOKENS = new Set(["r", "right", "phai"]);

export function formatLaterality(side) {
  if (side === "L") return "trái";
  if (side === "R") return "phải";
  return "chưa xác định";
}

export function suggestLaterality(filename) {
  if (typeof filename !== "string" || !filename) return null;

  const basename = filename.split(/[\\/]/).pop() || "";
  const stem = basename.replace(/\.[^.]*$/, "");
  const tokens = stem
    .normalize("NFD")
    .replace(/\p{M}/gu, "")
    .toLowerCase()
    .split(/[^\p{L}\p{N}]+/u)
    .filter(Boolean);
  const hasLeft = tokens.some((token) => LEFT_TOKENS.has(token));
  const hasRight = tokens.some((token) => RIGHT_TOKENS.has(token));

  if (hasLeft === hasRight) return null;
  return hasLeft ? "L" : "R";
}

export function getLateralityHint(filename, selectedSide) {
  if (selectedSide !== "L" && selectedSide !== "R") return null;
  const suggestedSide = suggestLaterality(filename);
  if (!suggestedSide) return null;

  const mismatch = suggestedSide !== selectedSide;
  const suggestedLabel = suggestedSide === "L" ? "trái" : "phải";
  const selectedLabel = selectedSide === "L" ? "trái" : "phải";
  return {
    suggestedSide,
    mismatch,
    message: mismatch
      ? `Tên tệp gợi ý bên ${suggestedLabel}, nhưng bạn đã chọn ô bên ${selectedLabel}. Hãy kiểm tra lại; hệ thống không tự đổi bên.`
      : `Tên tệp gợi ý bên ${suggestedLabel}. Vui lòng xác nhận bên đã chọn; đây chỉ là gợi ý.`,
  };
}
