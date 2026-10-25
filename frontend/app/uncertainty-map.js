const PNG_DATA_URI_PREFIX = "data:image/png;base64,";

export async function loadUncertaintyMap(dataUrl, browser = globalThis) {
  if (
    typeof dataUrl !== "string" ||
    !dataUrl.startsWith(PNG_DATA_URI_PREFIX) ||
    typeof browser?.createImageBitmap !== "function"
  )
    return null;

  let bitmap = null;
  try {
    const decodeBase64 = browser.atob || globalThis.atob;
    const BlobConstructor = browser.Blob || globalThis.Blob;
    if (typeof decodeBase64 !== "function" || typeof BlobConstructor !== "function")
      return null;
    const binary = decodeBase64(dataUrl.slice(PNG_DATA_URI_PREFIX.length));
    const bytes = new Uint8Array(binary.length);
    for (let index = 0; index < binary.length; index++)
      bytes[index] = binary.charCodeAt(index);
    bitmap = await browser.createImageBitmap(
      new BlobConstructor([bytes], { type: "image/png" }),
    );
    if (bitmap.width !== 512 || bitmap.height !== 512) {
      bitmap.close?.();
      return null;
    }
    return bitmap;
  } catch {
    bitmap?.close?.();
    return null;
  }
}
