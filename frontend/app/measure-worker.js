function cross(o, a, b) {
  return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0]);
}
function hull(points) {
  points.sort((a, b) => a[0] - b[0] || a[1] - b[1]);
  const lo = [],
    hi = [];
  for (const p of points) {
    while (lo.length > 1 && cross(lo.at(-2), lo.at(-1), p) <= 0) lo.pop();
    lo.push(p);
  }
  for (let i = points.length - 1; i >= 0; i--) {
    const p = points[i];
    while (hi.length > 1 && cross(hi.at(-2), hi.at(-1), p) <= 0) hi.pop();
    hi.push(p);
  }
  lo.pop();
  hi.pop();
  return lo.concat(hi);
}
function diameter(h) {
  if (h.length < 2) return { d1: 0, d2: 0, points: [] };
  let j = 1,
    best = 0,
    a = h[0],
    b = h[1];
  const dist = (p, q) => (p[0] - q[0]) ** 2 + (p[1] - q[1]) ** 2;
  for (let i = 0; i < h.length; i++) {
    const ni = (i + 1) % h.length;
    while (
      Math.abs(cross(h[i], h[ni], h[(j + 1) % h.length])) >
      Math.abs(cross(h[i], h[ni], h[j]))
    )
      j = (j + 1) % h.length;
    for (const p of [h[i], h[ni]])
      if (dist(p, h[j]) > best) {
        best = dist(p, h[j]);
        a = p;
        b = h[j];
      }
  }
  const d1 = Math.sqrt(best),
    nx = -(b[1] - a[1]) / (d1 || 1),
    ny = (b[0] - a[0]) / (d1 || 1);
  const projections = h.map((p) => p[0] * nx + p[1] * ny);
  return {
    d1,
    d2: Math.max(...projections) - Math.min(...projections),
    points: [a, b],
  };
}
self.onmessage = ({ data }) => {
  const { mask, box, serial } = data;
  let count = 0,
    touches = false;
  const points = [];
  for (let y = 0; y < 512; y++)
    for (let x = 0; x < 512; x++) {
      const idx = y * 512 + x;
      if (!mask[idx]) continue;
      if (
        x < box.left ||
        x >= box.left + box.width ||
        y < box.top ||
        y >= box.top + box.height
      )
        continue;
      count++;
      if (
        x === box.left ||
        y === box.top ||
        x === box.left + box.width - 1 ||
        y === box.top + box.height - 1
      )
        touches = true;
      if (
        !x ||
        !y ||
        x === 511 ||
        y === 511 ||
        !mask[idx - 1] ||
        !mask[idx + 1] ||
        !mask[idx - 512] ||
        !mask[idx + 512]
      )
        points.push([
          ((x - box.left) * box.sourceWidth) / box.width,
          ((y - box.top) * box.sourceHeight) / box.height,
        ]);
    }
  const result = diameter(hull(points));
  self.postMessage({
    serial,
    ...result,
    area:
      (((count * box.sourceWidth) / box.width) * box.sourceHeight) / box.height,
    touches,
  });
};
