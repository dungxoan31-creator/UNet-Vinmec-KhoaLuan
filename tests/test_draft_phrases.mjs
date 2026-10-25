import assert from "node:assert/strict";
import test from "node:test";

import { expandDraftPhrase } from "../frontend/app/draft-phrases.js";

test("test_expands_neutral_phrase_at_token_boundary", () => {
  const text = "Mô tả .obs";
  const result = expandDraftPhrase(text, text.length, text.length);

  assert.deepEqual(result, {
    text: "Mô tả Mô tả: ",
    selectionStart: "Mô tả Mô tả: ".length,
    expanded: true,
  });
});

test("test_replaces_selection_and_restores_caret", () => {
  const text = "A .size\n";
  const selectionStart = 2;
  const selectionEnd = selectionStart + ".size".length;
  const result = expandDraftPhrase(text, selectionStart, selectionEnd);

  assert.deepEqual(result, {
    text: "A Số đo bác sĩ xác nhận: \n",
    selectionStart: 2 + "Số đo bác sĩ xác nhận: ".length,
    expanded: true,
  });
});

test("test_does_not_expand_inside_longer_word", () => {
  const text = "abc.obs";
  assert.deepEqual(expandDraftPhrase(text, text.length, text.length), {
    text,
    selectionStart: text.length,
    expanded: false,
  });
});

test("test_unknown_token_is_unchanged", () => {
  const text = "Ghi chú .assessment";
  assert.deepEqual(expandDraftPhrase(text, text.length, text.length), {
    text,
    selectionStart: text.length,
    expanded: false,
  });
});

test("test_paste_without_trailing_delimiter_is_supported", () => {
  const text = ".note";
  assert.deepEqual(expandDraftPhrase(text, text.length, text.length), {
    text: "Nhận xét: ",
    selectionStart: "Nhận xét: ".length,
    expanded: true,
  });
});

test("test_cursor_outside_token_is_unchanged", () => {
  const text = "Ghi chú .obs";
  const cursor = text.indexOf(".obs") + 2;
  assert.deepEqual(expandDraftPhrase(text, cursor, cursor), {
    text,
    selectionStart: cursor,
    expanded: false,
  });
});

test("test_composition_or_readonly_does_not_expand", () => {
  const text = ".obs";
  for (const options of [{ isComposing: true }, { readOnly: true }])
    assert.deepEqual(
      expandDraftPhrase(text, text.length, text.length, options),
      { text, selectionStart: text.length, expanded: false },
    );
});

test("test_expands_clinical_dot_phrases", () => {
  const cases = [
    {
      token: ".bt",
      expected: "Đánh giá buồng trứng: [bác sĩ ghi nhận hình thái và nhận định].",
    },
    {
      token: ".nang1",
      expected: "Mô tả nang noãn: [bác sĩ xác nhận kích thước, hình thái và bối cảnh].",
    },
    {
      token: ".nang2",
      expected:
        "Mô tả dạng nang: [bác sĩ ghi nhận kích thước, thành, vách và dịch].",
    },
    {
      token: ".ub",
      expected:
        "Mô tả thành phần tăng âm/bóng cản: [bác sĩ ghi nhận các dấu hiệu đã quan sát].",
    },
    {
      token: ".pcos",
      expected:
        "Mô tả nang noãn và nhu mô buồng trứng: [bác sĩ ghi nhận số lượng, phân bố, kích thước và bối cảnh].",
    },
    {
      token: ".u3",
      expected:
        "Mô tả khối phần phụ: [bác sĩ ghi nhận hình thái, kích thước và Doppler khi phù hợp].",
    },
  ];

  for (const { token, expected } of cases) {
    const input = `Kết quả: ${token}`;
    const result = expandDraftPhrase(input, input.length, input.length);
    assert.doesNotMatch(result.text, /O-RADS\s*\d|lành tính|PCOS|đề nghị theo dõi|bình thường/iu,
      'A shortcut without clinical inputs must not insert a risk category, diagnosis or management.');
    assert.deepEqual(result, {
      text: `Kết quả: ${expected}`,
      selectionStart: `Kết quả: ${expected}`.length,
      expanded: true,
    });
  }
});

