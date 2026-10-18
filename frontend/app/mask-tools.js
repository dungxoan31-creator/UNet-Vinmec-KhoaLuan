export function components(mask) {
  const visited = new Uint8Array(mask.length),
    groups = [];
  for (let i = 0; i < mask.length; i++) {
    if (!mask[i] || visited[i]) continue;
    const q = [i];
    visited[i] = 1;
    for (let n = 0; n < q.length; n++) {
      const p = q[n],
        x = p % 512,
        y = Math.floor(p / 512);
      for (const v of [
        x > 0 ? p - 1 : -1,
        x < 511 ? p + 1 : -1,
        y > 0 ? p - 512 : -1,
        y < 511 ? p + 512 : -1,
      ])
        if (v >= 0 && mask[v] && !visited[v]) {
          visited[v] = 1;
          q.push(v);
        }
    }
    groups.push(q);
  }
  return groups;
}
export function cleanMask(mask, action) {
  const out = mask.slice();
  if (action === "small") {
    for (const group of components(mask))
      if (group.length < 50) for (const p of group) out[p] = 0;
  } else if (action === "smooth") {
    for (let y = 1; y < 511; y++)
      for (let x = 1; x < 511; x++) {
        let n = 0;
        for (let dy = -1; dy <= 1; dy++)
          for (let dx = -1; dx <= 1; dx++) n += mask[(y + dy) * 512 + x + dx];
        out[y * 512 + x] = n >= 5 ? 1 : 0;
      }
  } else if (action === "fill") {
    const exterior = new Uint8Array(mask.length),
      q = [];
    for (let i = 0; i < 512; i++)
      for (const p of [i, 511 * 512 + i, i * 512, i * 512 + 511])
        if (!mask[p] && !exterior[p]) {
          exterior[p] = 1;
          q.push(p);
        }
    for (let n = 0; n < q.length; n++) {
      const p = q[n],
        x = p % 512,
        y = Math.floor(p / 512);
      for (const v of [
        x > 0 ? p - 1 : -1,
        x < 511 ? p + 1 : -1,
        y > 0 ? p - 512 : -1,
        y < 511 ? p + 512 : -1,
      ])
        if (v >= 0 && !mask[v] && !exterior[v]) {
          exterior[v] = 1;
          q.push(v);
        }
    }
    for (let i = 0; i < out.length; i++)
      if (!mask[i] && !exterior[i]) out[i] = 1;
  }
  return out;
}
