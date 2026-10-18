// Derive a visualization only when both supplied masks are binary and aligned.
export async function binaryErrorMap(groundTruth, prediction) {
  if (!groundTruth || !prediction) return null;
  const images = await Promise.all(
    [groundTruth, prediction].map(async (src) =>
      createImageBitmap(await (await fetch(src)).blob()),
    ),
  );
  try {
    if (
      images[0].width !== images[1].width ||
      images[0].height !== images[1].height
    )
      return null;
    const c = document.createElement("canvas");
    c.width = images[0].width;
    c.height = images[0].height;
    const g = c.getContext("2d");
    const masks = images.map((bitmap) => {
      g.clearRect(0, 0, c.width, c.height);
      g.drawImage(bitmap, 0, 0);
      return g.getImageData(0, 0, c.width, c.height).data;
    });
    const result = g.createImageData(c.width, c.height);
    for (let n = 0; n < result.data.length; n += 4) {
      if (
        masks.some(
          (m) =>
            m[n] !== m[n + 1] ||
            m[n] !== m[n + 2] ||
            ![0, 1, 255].includes(m[n]),
        )
      )
        return null;
      const truth = masks[0][n] > 0,
        pred = masks[1][n] > 0;
      result.data.set(
        truth && pred
          ? [120, 164, 142, 255]
          : truth
            ? [75, 159, 230, 255]
            : pred
              ? [228, 164, 76, 255]
              : [32, 38, 44, 255],
        n,
      );
    }
    g.putImageData(result, 0, 0);
    return c.toDataURL("image/png");
  } finally {
    images.forEach((i) => i.close());
  }
}
