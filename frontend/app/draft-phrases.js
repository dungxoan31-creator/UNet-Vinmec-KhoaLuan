const phrases = Object.freeze({
  ".obs": "Mô tả: ",
  ".size": "Số đo bác sĩ xác nhận: ",
  ".note": "Nhận xét: ",
  ".bt": "Đánh giá buồng trứng: [bác sĩ ghi nhận hình thái và nhận định].",
  ".nang1": "Mô tả nang noãn: [bác sĩ xác nhận kích thước, hình thái và bối cảnh].",
  ".nang2": "Mô tả dạng nang: [bác sĩ ghi nhận kích thước, thành, vách và dịch].",
  ".ub": "Mô tả thành phần tăng âm/bóng cản: [bác sĩ ghi nhận các dấu hiệu đã quan sát].",
  ".pcos": "Mô tả nang noãn và nhu mô buồng trứng: [bác sĩ ghi nhận số lượng, phân bố, kích thước và bối cảnh].",
  ".u3": "Mô tả khối phần phụ: [bác sĩ ghi nhận hình thái, kích thước và Doppler khi phù hợp].",
});

const wordCharacter = /[\p{L}\p{N}_]/u;
const tokenBoundary = /[\s.,;:!?()[\]{}]/u;

function unchanged(text, selectionStart) {
  return { text, selectionStart, expanded: false };
}

export function expandDraftPhrase(
  text,
  selectionStart,
  selectionEnd,
  { isComposing = false, readOnly = false } = {},
) {
  if (
    typeof text !== "string" ||
    !Number.isInteger(selectionStart) ||
    !Number.isInteger(selectionEnd) ||
    selectionStart < 0 ||
    selectionEnd < selectionStart ||
    selectionEnd > text.length ||
    isComposing ||
    readOnly
  )
    return unchanged(text, selectionStart);

  let tokenStart = selectionStart;
  let tokenEnd = selectionEnd;
  let trailingBoundaryLength = 0;
  let replacement;

  if (selectionStart === selectionEnd) {
    if (
      tokenEnd > 0 &&
      tokenBoundary.test(text[tokenEnd - 1]) &&
      text[tokenEnd - 1] !== "."
    ) {
      tokenEnd--;
      trailingBoundaryLength = 1;
    }
    const match = Object.entries(phrases).find(([token]) =>
      text.slice(tokenEnd - token.length, tokenEnd) === token,
    );
    if (!match) return unchanged(text, selectionStart);
    replacement = match[1];
    tokenStart = tokenEnd - match[0].length;
  } else {
    replacement = phrases[text.slice(tokenStart, tokenEnd)];
  }

  if (typeof replacement !== "string")
    return unchanged(text, selectionStart);

  const before = text[tokenStart - 1];
  const after = text[tokenEnd];
  if (
    (before && wordCharacter.test(before)) ||
    (after && !tokenBoundary.test(after))
  )
    return unchanged(text, selectionStart);

  return {
    text: text.slice(0, tokenStart) + replacement + text.slice(tokenEnd),
    selectionStart: tokenStart + replacement.length + trailingBoundaryLength,
    expanded: true,
  };
}
