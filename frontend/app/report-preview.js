import { state } from "./state.js";
import { openCase } from "./cases.js";
import { protectedImage, request } from "./api.js";

import { letterbox } from "./coordinates.js";
import { $, esc, pageHead, button, loading, errorBox, toast } from "./ui.js";
async function reportImages(i) {
  const url = await protectedImage("/api/images/" + i.image_id + "/source.png");
  const bitmap = await createImageBitmap(await (await fetch(url)).blob());
  const c = document.createElement("canvas");
  c.width = bitmap.width;
  c.height = bitmap.height;
  const g = c.getContext("2d");
  g.drawImage(bitmap, 0, 0);
  const original = c.toDataURL();
  const mask = document.createElement("canvas");
  mask.width = mask.height = 512;
  const mg = mask.getContext("2d"),
    pixels = mg.createImageData(512, 512);
  for (let n = 0; n < i.mask.length; n++)
    if (i.mask[n]) pixels.data.set([98, 233, 224, 255], n * 4);
  mg.putImageData(pixels, 0, 0);
  const box = letterbox(bitmap.width, bitmap.height);
  g.fillStyle = "#20262c";
  g.fillRect(0, 0, c.width, c.height);
  g.drawImage(
    mask,
    box.left,
    box.top,
    box.width,
    box.height,
    0,
    0,
    c.width,
    c.height,
  );
  const binary = c.toDataURL();
  g.drawImage(bitmap, 0, 0);
  g.globalAlpha = 0.35;
  g.drawImage(
    mask,
    box.left,
    box.top,
    box.width,
    box.height,
    0,
    0,
    c.width,
    c.height,
  );
  g.globalAlpha = 1;
  const m = i.measurements;
  const primaryLesion = m?.lesions?.[0];
  const dmaxPoints = m?.caliper_dmax_points || primaryLesion?.caliper_dmax_points;
  const dorthPoints = m?.caliper_dorth_points || primaryLesion?.caliper_dorth_points;
  for (const points of [dmaxPoints, dorthPoints])
    if (points?.length === 2) {
      g.strokeStyle = "#fff";
      g.lineWidth = 2;
      g.beginPath();
      g.moveTo(...points[0]);
      g.lineTo(...points[1]);
      g.stroke();
    }
  const overlay = c.toDataURL();
  bitmap.close();
  {
    URL.revokeObjectURL(url);
  }
  return [original, binary, overlay];
}
export async function renderReport(root, id) {
  root.innerHTML =
    pageHead(
      "Phiếu kết quả",
      "In hoặc lưu PDF bằng hộp thoại của trình duyệt.",
      button("Tải hồ sơ kết quả", "export-research", "small") +
        " " +
        button("In / Lưu PDF", "print", "primary"),
    ) + `<div id="reportData">${loading()}</div>`;
  const target = root.querySelector("#reportData"),
    identity = state.user?.id;
  const active = () => root.isConnected && identity === state.user?.id;
  const printBtn = root.querySelector("[data-action=print]");
  const exportBtn = root.querySelector("[data-action=export-research]");
  printBtn.disabled = true;
  if (exportBtn) exportBtn.disabled = true;
  try {
    const c = await openCase(id);
    if (exportBtn) {
      exportBtn.disabled = false;
      exportBtn.onclick = async () => {
        const revIds = c.images.map((i) => i.review?.review_id).filter(Boolean);
        if (state.dirty || revIds.length !== c.images.length) {
          return toast("Cần hoàn tất lưu rà soát trước khi tải kết quả.", true);
        }
        try {
          const token = sessionStorage.getItem("ova.token");
          const headers = { "Content-Type": "application/json" };
          if (token) headers.Authorization = "Bearer " + token;
          toast("Đang tải kết quả...");
          const resp = await fetch(
            `/api/cases/${encodeURIComponent(c.study_id)}/research-export`,
            {
              method: "POST",
              headers,
              body: JSON.stringify({
                review_ids: revIds,
                expected_revision: c.review_revision ?? 0,
              }),
            },
          );
          if (!resp.ok) {
            const err = await resp
              .json()
              .catch(() => ({ detail: "Lỗi tải kết quả." }));
            return toast(err.detail || "Không thể tải kết quả.", true);
          }
          const blob = await resp.blob();
          if (blob.size === 0) return toast("File rỗng.", true);
          const url = URL.createObjectURL(blob);
          const a = document.createElement("a");
          a.href = url;
          a.download = `study_${c.study_code || c.study_id}_research_export.zip`;
          document.body.appendChild(a);
          a.click();
          a.remove();
          setTimeout(() => URL.revokeObjectURL(url), 1000);
          toast("Đã tải tệp ZIP kết quả.");
        } catch (err) {
          toast(err.message || "Lỗi tải tệp ZIP.", true);
        }
      };
    }
    if (c.images.length !== 2 || !c.images.every((i) => i.review))
      throw Error("Cần lưu rà soát đủ hai bên trước khi xuất phiếu.");
    if (state.dirty)
      throw Error(
        "Có bản nháp chưa được lưu. Hãy hoàn tất rà soát trước khi xuất phiếu.",
      );
    {
      for (const i of c.images) {
        if (i.review && (i.review.max_diameter_mm != null || i.review.total_area_cm2 != null)) {
          const prevM = i.measurements || i.prediction?.measurements || {};
          i.measurements = {
            ...prevM,
            calibrated: i.review.max_diameter_mm != null,
            max_diameter_mm: i.review.max_diameter_mm,
            ortho_diameter_mm: i.review.ortho_diameter_mm,
            total_area_cm2: i.review.total_area_cm2,
            calibration_source: i.review.max_diameter_mm != null ? "Đã hiệu chuẩn" : "Chưa hiệu chuẩn",
          };
        } else if (i.review) {
          const liveM = await request(
            "/api/images/" + i.image_id + "/measurements",
            { method: "POST", body: { rle_mask: i.review.verified_mask_rle } },
          );
          i.measurements = {
            ...liveM,
            calibrated: false,
            max_diameter_mm: null,
            ortho_diameter_mm: null,
            total_area_cm2: null,
          };
        }
      }
    }
    const assets = await Promise.all(c.images.map(reportImages));
    if (!active()) return;
    target.innerHTML = `<article class="report"><header class="report-header"><div><img class="vinmec-logo" src="/static/assets/brand/vinmec-logo.png" alt="Vinmec" width="100" height="62"><p class="eyebrow">HỖ TRỢ PHÂN ĐOẠN SIÊU ÂM</p><h1>Phiếu rà soát phân đoạn siêu âm</h1><p>Khảo sát buồng trứng hai bên</p></div><div class="mono">${esc(c.study_code || c.study_id)}</div></header><p class="report-notice">Hỗ trợ phân đoạn siêu âm · Bác sĩ xác nhận kết quả</p><div class="grid-2"><p>PID: <strong>${esc(c.patient_id)}</strong></p><p>Ngày khảo sát: ${esc(c.study_date)}</p></div>${c.images
      .map((i, index) => {
        const m = i.measurements || {},
          cal = m.calibrated;
        const orads = i.review?.orads_score || i.review?.orads || i.orads || "Chưa phân loại";
        const morphDesc = i.review?.morphology_description || i.morphologyDesc || i.morphology || i.review?.lesion_type || "Chưa ghi nhận";
        const notes = i.review?.clinical_notes || i.notes || "Chưa ghi nhận";
        return `<section><h2>Buồng trứng ${i.laterality === "L" ? "trái" : "phải"}</h2><div class="report-images">${assets[index].map((url, n) => `<figure><img src="${url}" alt="${["Ảnh gốc", "Mask rà soát", "Lớp phủ và thước đo"][n]}"><figcaption>${["Ảnh gốc", "Mask rà soát", "Lớp phủ; caliper nếu có"][n]}</figcaption></figure>`).join("")}</div><table><thead><tr><th>d₁ × d₂</th><th>Diện tích</th><th>Hiệu chuẩn</th></tr></thead><tbody><tr><td>${fmt(cal ? m.max_diameter_mm : m.max_diameter_px)} × ${fmt(cal ? m.ortho_diameter_mm : m.ortho_diameter_px)} ${cal ? "mm" : "px"}</td><td>${fmt(cal ? m.total_area_cm2 : m.total_area_px)} ${cal ? "cm²" : "px²"}</td><td>${cal ? esc(m.calibration_source || "Đã hiệu chuẩn") : "Chưa hiệu chuẩn"}</td></tr></tbody></table><p>Phân loại O-RADS: <strong>${esc(orads)}</strong><br>Mô tả hình thái: ${esc(morphDesc)}<br>Ghi chú lâm sàng: ${esc(notes)}</p><p class="small">Mô hình: ${esc(i.prediction?.provenance?.architecture || i.prediction?.provenance?.model_name || i.prediction?.model_version || "Chưa có")}<br>SHA-256: <span class="mono">${esc(i.prediction?.provenance?.checkpoint_sha256 || i.prediction?.provenance?.model_checksum || "Bản ghi chưa cung cấp")}</span></p></section>`;
      })
      .join(
        "",
      )}<footer>Người rà soát: ${esc(c.images[0].review?.doctor_id || state.user.username)} · Mã ca ${esc(c.study_id)}<br>Chưa có chữ ký số xác thực. </footer></article>`;
    printBtn.disabled = false;
    printBtn.onclick = async () => {
      try {
        if (state.capabilities?.case_workflow === true) {
          try {
            await request(
              "/api/workspace/cases/" + c.study_id + "/report-export",
              { method: "POST", body: { version: c.version } },
            );
          } catch (exportErr) {
            console.warn("Report export audit notification notice:", exportErr);
          }
        }
        document.getElementById("printRoot")?.remove();
        const print = document.createElement("div");
        print.id = "printRoot";
        print.hidden = true;
        if (!active()) return;
        print.append(target.querySelector(".report").cloneNode(true));
        document.body.append(print);
        await Promise.all(
          [...print.querySelectorAll("img")].map((i) => i.decode()),
        );
        window.print();
      } catch (e) {
        toast(e.message, true);
      }
    };
  } catch (e) {
    if (!active()) return;
    target.innerHTML = errorBox(e.message);
    target.querySelector("[data-action=retry]").onclick = () =>
      renderReport(root, id);
  }
}
