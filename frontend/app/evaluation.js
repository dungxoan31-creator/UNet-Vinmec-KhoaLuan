import { request } from "./api.js";
import { binaryErrorMap } from "./evaluation-images.js";
import {
  $,
  esc,
  pageHead,
  loading,
  errorBox,
  empty,
} from "./ui.js";

export async function renderEvaluation(root) {
  root.innerHTML =
    pageHead(
      "Đánh giá mô hình",
      "Kết quả trên tập có ground truth; không phải độ tin cậy của ca đang đọc.",
    ) +
    `<div class="banner info">Kết quả lịch sử không đại diện tự động cho checkpoint đang chạy.</div><div id="evaluationData">${loading()}</div>`;
  try {
    const data = await request("/api/evaluation/metrics");
    const splits = data.splits || data,
      metrics = ["dice", "iou", "recall", "precision"],
      archiveStatus = data.archived_split_status || {
        status: "BLOCKED",
        reason: "API chưa cung cấp trạng thái provenance cho archive lịch sử.",
      },
      archiveBlocked = archiveStatus.status !== "AVAILABLE";
    const rows = ["train", "validation", "test"].map((key) => [
      key,
      ...metrics.map((m) => {
        const v =
          splits[key]?.[m + "_mean"] ??
          splits[key]?.[m] ??
          splits[key]?.metrics?.[m];
        return typeof v === "number" ? v.toFixed(4) : "Chưa có số liệu";
      }),
    ]);

    let gateBanner = "";
    if (data.evidence_status?.independent_gate_status === "BLOCKED") {
      gateBanner = `<div class="banner warning" style="margin-bottom:16px;"><strong>Cổng đánh giá độc lập: BỊ CHẶN (BLOCKED)</strong> — Chưa xác minh được tính độc lập theo bệnh nhân; không diễn giải số liệu image-level thành hiệu quả lâm sàng.</div>`;
    }

    let currentRunStatusBanner = "";
    const runStatus = data.current_run_status;
    if (runStatus && !["AVAILABLE", "NO_POINTER"].includes(runStatus.status)) {
      const runLabel = runStatus.run_id ? ` ${esc(runStatus.run_id)}` : "";
      const statusLabel = esc(runStatus.status.toLowerCase().replace(/_/g, " "));
      currentRunStatusBanner = `<div class="banner warning" style="margin-bottom:16px;">Evaluation run${runLabel}: summary artifact is ${statusLabel}; run metrics are withheld.</div>`;
    }

    let currentRunSection = "";
    if (data.current_run) {
      const cr = data.current_run;
      const fmt = (val) =>
        typeof val === "number"
          ? val.toFixed(4)
          : val?.mean != null
            ? Number(val.mean).toFixed(4)
            : "Chưa có / Không xác định";
      currentRunSection = `
        <section class="panel" style="margin-bottom:24px;">
          <div class="panel-header" style="padding:16px 20px;border-bottom:1px solid var(--border,#e2e8f0);">
            <div style="display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:8px;">
              <div>
                <h3 style="margin:0 0 4px 0;font-size:16px;font-weight:600;">${esc(cr.label || cr.run_id)}</h3>
                <p class="muted small" style="margin:0;">Trạng thái: <strong>${esc(cr.status)}</strong> · Loại: <strong>${esc(cr.run_kind)}</strong> · Cỡ tập: <strong>${esc(cr.counts?.total_samples ?? "N/A")} ảnh</strong></p>
              </div>
              ${cr.is_historical ? '<span class="badge warning historical-data-badge">Dữ liệu đối chuẩn lịch sử</span>' : '<span class="badge success">Đã xác minh</span>'}
            </div>
            <p class="small mono muted" style="margin:8px 0 0 0;">Checkpoint: ${esc(cr.checkpoint_sha256 || "N/A")}</p>
          </div>
          <div class="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Chỉ số</th>
                  <th>Giá trị trung bình (Mean)</th>
                  <th>Trung vị (Median)</th>
                  <th>Số mẫu hợp lệ</th>
                  <th>Ghi chú</th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td><strong>Dice Similarity</strong></td>
                  <td>${fmt(cr.primary?.dice)}</td>
                  <td>${typeof cr.primary?.dice?.median === "number" ? cr.primary.dice.median.toFixed(4) : "Chưa có / N/A"}</td>
                  <td>${cr.primary?.dice?.n_valid ?? cr.counts?.total_samples ?? "-"}</td>
                  <td>Độ trùng khớp phân đoạn sơ cấp</td>
                </tr>
                <tr>
                  <td><strong>IoU (Jaccard)</strong></td>
                  <td>${fmt(cr.primary?.iou)}</td>
                  <td>${typeof cr.primary?.iou?.median === "number" ? cr.primary.iou.median.toFixed(4) : "Chưa có / N/A"}</td>
                  <td>${cr.primary?.iou?.n_valid ?? cr.counts?.total_samples ?? "-"}</td>
                  <td>Giao trên hợp vùng u</td>
                </tr>
                <tr>
                  <td><strong>Độ nhạy (Recall)</strong></td>
                  <td>${fmt(cr.primary?.recall)}</td>
                  <td>${typeof cr.primary?.recall?.median === "number" ? cr.primary.recall.median.toFixed(4) : "Chưa có / N/A"}</td>
                  <td>${cr.primary?.recall?.n_valid ?? cr.counts?.total_samples ?? "-"}</td>
                  <td>Bao phủ pixel tổn thương (không phải độ nhạy ca bệnh)</td>
                </tr>
                <tr>
                  <td><strong>Độ chính xác (Precision)</strong></td>
                  <td>${fmt(cr.primary?.precision)}</td>
                  <td>${typeof cr.primary?.precision?.median === "number" ? cr.primary.precision.median.toFixed(4) : "Chưa có / N/A"}</td>
                  <td>${cr.primary?.precision?.n_valid ?? cr.counts?.total_samples ?? "-"}</td>
                  <td>Độ tin cậy pixel dương tính</td>
                </tr>
                <tr>
                  <td><strong>Độ đặc hiệu (Specificity)</strong></td>
                  <td>${fmt(cr.primary?.specificity)}</td>
                  <td>${typeof cr.primary?.specificity?.median === "number" ? cr.primary.specificity.median.toFixed(4) : "Chưa có / N/A"}</td>
                  <td>${cr.primary?.specificity?.n_valid ?? cr.counts?.total_samples ?? "-"}</td>
                  <td>Độ đặc hiệu trên nền âm tính</td>
                </tr>
                <tr>
                  <td><strong>Khoảng cách biên HD95</strong></td>
                  <td>${typeof cr.primary?.hd95_px?.mean === "number" ? cr.primary.hd95_px.mean.toFixed(2) + " px" : "Chưa có / N/A"}</td>
                  <td>${typeof cr.primary?.hd95_px?.median === "number" ? cr.primary.hd95_px.median.toFixed(2) + " px" : "Chưa có / N/A"}</td>
                  <td>${cr.primary?.hd95_px?.n_valid ?? "-"}</td>
                  <td>Sai số biên 95th percentile theo pixel gốc</td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>
      `;
    }

    const historicalSection = archiveBlocked
      ? `<section class="panel" aria-live="polite"><div class="panel-header evaluation-panel-heading"><h4 class="evaluation-section-title">Archive lịch sử: BỊ CHẶN</h4></div><div class="panel-body"><div class="banner warning"><strong>Không hiển thị metrics hoặc ảnh mẫu.</strong> ${esc(archiveStatus.reason || "Nguồn dữ liệu và liên kết manifest chưa được xác minh.")}</div></div></section>`
      : `<section class="panel"><div class="panel-header evaluation-panel-heading"><h4 class="evaluation-section-title">Tập dữ liệu lưu trữ lịch sử (Historical Splits)</h4></div><div class="table-wrap"><table><thead><tr><th>Tập dữ liệu</th>${metrics.map((m) => `<th>${{ dice: "Dice", iou: "IoU", recall: "Recall pixel", precision: "Precision pixel" }[m]}</th>`).join("")}</tr></thead><tbody>${rows.map((row) => "<tr>" + row.map((v) => `<td>${esc(v)}</td>`).join("") + "</tr>").join("")}</tbody></table></div></section><div class="filters evaluation-filters"><label class="field">Nhóm lỗi<select id="errorGroup"><option value="ALL">Tất cả</option><option value="FAILURE_CASES">Phân đoạn kém</option><option value="FALSE_NEGATIVE_DOMINANT">Bỏ sót ưu thế</option><option value="FALSE_POSITIVE_DOMINANT">Lan vùng ưu thế</option></select></label></div><section class="panel" id="evaluationSamples"></section>`;

    $("#evaluationData", root).innerHTML =
      gateBanner +
      currentRunStatusBanner +
      currentRunSection +
      historicalSection;
    if (archiveBlocked) return;

    let page = 0,
      generation = 0,
      detailGeneration = 0;
    const load = async () => {
      const target = $("#evaluationSamples", root),
        version = ++generation;
      target.innerHTML = loading();
      try {
        const result = await request(
          "/api/evaluation/samples?" +
            new URLSearchParams({
              category: $("#errorGroup", root).value,
              limit: 21,
              offset: page * 20,
            }),
        );
        if (!target.isConnected || version !== generation) return;
        const all = Array.isArray(result)
            ? result
            : result.samples || result.items || [],
          samples = all.slice(0, 20),
          hasNext = all.length > 20;
        target.innerHTML = samples.length
          ? `<div class="table-wrap"><table><thead><tr><th>Ca đánh giá</th><th>Dice</th><th>IoU</th><th>Đối chiếu</th></tr></thead><tbody>${samples.map((s) => `<tr><td>${esc(s.case_id)}</td><td>${esc(s.dice)}</td><td>${esc(s.iou)}</td><td><button class="btn" data-sample="${esc(s.case_id)}">Xem ảnh</button></td></tr>`).join("")}</tbody></table></div><div class="pagination"><span>Trang ${page + 1}</span><div class="actions"><button id="evalPrev" class="btn" ${page === 0 ? "disabled" : ""}>Trước</button><button id="evalNext" class="btn" ${!hasNext ? "disabled" : ""}>Sau</button></div></div><div id="sampleDetail"></div>`
          : empty();
        $("#evalPrev", target)?.addEventListener("click", () => {
          page--;
          load();
        });
        $("#evalNext", target)?.addEventListener("click", () => {
          page++;
          load();
        });
        target.querySelectorAll("[data-sample]").forEach(
          (b) =>
            (b.onclick = async () => {
              const panel = $("#sampleDetail", target),
                selected = ++detailGeneration;
              panel.innerHTML = loading();
              try {
                const detail = await request(
                  "/api/evaluation/samples/" +
                    encodeURIComponent(b.dataset.sample) +
                    "/workstation-bundle",
                );
                const derived =
                  detail.error_map_base64 ||
                  (await binaryErrorMap(
                    detail.ground_truth_mask_base64,
                    detail.prediction_mask_base64,
                  ));
                if (!panel.isConnected || selected !== detailGeneration) return;
                const assets = [
                  ["Gốc", detail.original_image_base64],
                  ["Nhãn chuẩn", detail.ground_truth_mask_base64],
                  ["AI", detail.prediction_mask_base64],
                  ["Bản đồ lỗi", derived],
                ];
                panel.innerHTML = `<div class="panel-body"><h3>Ca ${esc(b.dataset.sample)}</h3><div class="preview-grid">${assets.map(([label, src], index) => `<figure><figcaption>${label}</figcaption>${src ? `<img src="${esc(src)}" alt="${label}"><a class="btn small" href="${esc(src)}" download="doi-chieu-${esc(b.dataset.sample)}-${index}.png">Tải ảnh</a>` : "<p>Chưa có ảnh hoặc mask chưa đồng nhất kích thước/nhãn nhị phân.</p>"}</figure>`).join("")}</div>${derived ? '<p class="muted small">Xanh lam: vùng bỏ sót · Cam: vùng lan thêm · Xanh xám: vùng trùng. Bản đồ từ hai mask đã cung cấp, không phải heatmap bất định.</p>' : ""}<p class="small mono">Checkpoint: ${esc(detail.provenance?.checkpoint_sha256 || "Chưa được cung cấp")}</p></div>`;
              } catch (e) {
                if (panel.isConnected && selected === detailGeneration) {
                  panel.innerHTML = errorBox(e.message);
                  $("[data-action=retry]", panel).onclick = () => b.click();
                }
              }
            }),
        );
      } catch (e) {
        if (target.isConnected && version === generation) {
          target.innerHTML = errorBox(e.message);
          $("[data-action=retry]", target).onclick = load;
        }
      }
    };
    $("#errorGroup", root).onchange = () => {
      page = 0;
      load();
    };
    await load();
  } catch (e) {
    const target = $("#evaluationData", root);
    if (target) {
      target.innerHTML = errorBox(e.message);
      $("[data-action=retry]", target).onclick = () => renderEvaluation(root);
    }
  }
}
