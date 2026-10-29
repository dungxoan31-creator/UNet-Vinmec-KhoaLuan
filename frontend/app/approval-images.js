import { state } from "./state.js";
import { protectedImage } from "./api.js";
import { letterbox } from "./coordinates.js";
import { esc } from "./ui.js";

async function loadBitmap(source) {
  const image = new Image();
  image.decoding = "async";
  image.src = source;
  await image.decode();
  return createImageBitmap(image);
}

export async function approvalImages(image) {
  let source = image.source;
  let sourceIsModel = image.sourceIsModel;
  let temporarySourceUrl = null;
  if (!source || sourceIsModel) {
    temporarySourceUrl = await protectedImage(
      "/api/images/" + encodeURIComponent(image.image_id) + "/source.png",
    );
    source = temporarySourceUrl;
    sourceIsModel = false;
  }
  let bitmap;
  try {
    bitmap = await loadBitmap(source);
    const canvas = document.createElement("canvas");
    canvas.width = canvas.height = 512;
    const ctx = canvas.getContext("2d");
    const box = letterbox(
      image.width || bitmap.width,
      image.height || bitmap.height,
    );
    const original = () => {
      ctx.fillStyle = "#20262c";
      ctx.fillRect(0, 0, 512, 512);
      ctx.drawImage(
        bitmap,
        sourceIsModel ? 0 : box.left,
        sourceIsModel ? 0 : box.top,
        sourceIsModel ? 512 : box.width,
        sourceIsModel ? 512 : box.height,
      );
    };
    original();
    const assets = [canvas.toDataURL()];
    for (const mask of [image.mask, image.aiMask]) {
      original();
      const overlay = document.createElement("canvas");
      overlay.width = overlay.height = 512;
      const g = overlay.getContext("2d"),
        data = g.createImageData(512, 512);
      for (let y = 0; y < 512; y++)
        for (let x = 0; x < 512; x++) {
          const n = y * 512 + x;
          if (
            mask?.[n] &&
            (x === 0 ||
              x === 511 ||
              y === 0 ||
              y === 511 ||
              !mask[n - 1] ||
              !mask[n + 1] ||
              !mask[n - 512] ||
              !mask[n + 512])
          )
            data.data.set([98, 233, 224, 255], n * 4);
        }
      g.putImageData(data, 0, 0);
      ctx.drawImage(overlay, 0, 0);
      assets.push(canvas.toDataURL());
    }
    return assets
      .map(
        (src, n) =>
          `<figure><img src="${src}" alt="${["Ảnh gốc", "Đường biên bác sĩ", "Đường biên AI"][n]}"><figcaption>${esc(["Ảnh gốc", "Mask bác sĩ", "Mask AI gốc"][n])}</figcaption></figure>`,
      )
      .join("");
  } finally {
    bitmap?.close?.();
    if (temporarySourceUrl) URL.revokeObjectURL(temporarySourceUrl);
  }
}
