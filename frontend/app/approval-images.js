import { state } from "./state.js";
import { request } from "./api.js";
import { letterbox } from "./coordinates.js";
import { esc } from "./ui.js";

export async function approvalImages(image) {
  let source = image.source;
  if (!source) {
    const data = await request(
      "/api/images/" + encodeURIComponent(image.image_id) + "/viewer-source",
    );
    source = data.original_image_base64;
    image.source = source;
    image.sourceIsModel = true;
  }
  const bitmap = await createImageBitmap(await (await fetch(source)).blob());
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
      image.sourceIsModel ? 0 : box.left,
      image.sourceIsModel ? 0 : box.top,
      image.sourceIsModel ? 512 : box.width,
      image.sourceIsModel ? 512 : box.height,
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
  bitmap.close();
  return assets
    .map(
      (src, n) =>
        `<figure><img src="${src}" alt="${["Ảnh gốc", "Đường biên bác sĩ", "Đường biên AI"][n]}"><figcaption>${esc(["Ảnh gốc", "Mask bác sĩ", "Mask AI gốc"][n])}</figcaption></figure>`,
    )
    .join("");
}
