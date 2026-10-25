export function letterbox(width, height, size = 512) {
  const scale = Math.min(size / width, size / height);
  const w = Math.floor(width * scale),
    h = Math.floor(height * scale);
  return {
    scale,
    width: w,
    height: h,
    left: Math.floor((size - w) / 2),
    top: Math.floor((size - h) / 2),
    sourceWidth: width,
    sourceHeight: height,
  };
}
export const screenToModel = (x, y, rect, view) => ({
  x: (x - rect.left - view.x) / view.scale,
  y: (y - rect.top - view.y) / view.scale,
});
export const modelToScreen = (x, y, view) => ({
  x: x * view.scale + view.x,
  y: y * view.scale + view.y,
});
export const modelToSource = (x, y, b) => ({
  x: ((x - b.left) * b.sourceWidth) / b.width,
  y: ((y - b.top) * b.sourceHeight) / b.height,
});
export const sourceToModel = (x, y, b) => ({
  x: (x * b.width) / b.sourceWidth + b.left,
  y: (y * b.height) / b.sourceHeight + b.top,
});
export function encode(mask) {
  const counts = [];
  let current = mask[0] ? 1 : 0,
    run = 0;
  const first = current;
  for (const v of mask) {
    const n = v ? 1 : 0;
    if (n === current) run++;
    else {
      counts.push(run);
      run = 1;
      current = n;
    }
  }
  counts.push(run);
  return {
    shape: [512, 512],
    counts,
    first_val: first,
    encoding: "standard_rle",
  };
}
export function decode(rle) {
  if (
    !rle ||
    rle.shape?.[0] !== 512 ||
    rle.shape?.[1] !== 512 ||
    ![0, 1].includes(rle.first_val) ||
    !Array.isArray(rle.counts)
  )
    throw Error("Mask RLE không hợp lệ.");
  const out = new Uint8Array(512 * 512);
  let offset = 0,
    value = rle.first_val;
  for (const n of rle.counts) {
    if (!Number.isSafeInteger(n) || n < 1 || offset + n > out.length)
      throw Error("Độ dài RLE không hợp lệ.");
    if (value) out.fill(1, offset, offset + n);
    offset += n;
    value = 1 - value;
  }
  if (offset !== out.length) throw Error("RLE thiếu pixel.");
  return out;
}
