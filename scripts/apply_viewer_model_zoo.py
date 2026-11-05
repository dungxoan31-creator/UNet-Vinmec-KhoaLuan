path = r"frontend/app/viewer.js"
with open(path, "r", encoding="utf-8") as f:
    code = f.read()

target1 = '<button type="button" class="btn small" data-action="toggle-caliper-denoise" id="btnCaliperDenoise" aria-pressed="false" title="Tự động xóa thước đo Caliper và khử nhiễu đốm âm học bảo toàn ranh giới">Xóa Caliper &amp; Lọc đốm</button>'

replacement1 = '''<button type="button" class="btn small" data-action="toggle-caliper-denoise" id="btnCaliperDenoise" aria-pressed="false" title="Tự động xóa thước đo Caliper và khử nhiễu đốm âm học bảo toàn ranh giới">Xóa Caliper &amp; Lọc đốm</button>
            <select id="selectModelZoo" class="btn small" style="background:#0f172a; color:#e2e8f0; border:1px solid #475569; padding:2px 6px; border-radius:4px; font-size:11px;" title="Chọn mô hình AI từ Model Zoo">
              <option value="attention_unet">U-Net++ scSE</option>
              <option value="tinyusfm">TinyUSFM (5.5M)</option>
              <option value="csasegnet">CSA-SegNet</option>
              <option value="mednext">MedNeXt (ConvNeXt)</option>
              <option value="medsam">MedSAM (HITL)</option>
            </select>
            <button type="button" class="btn small" data-action="rerun-ai-model" id="btnRerunAI" title="Chạy suy luận lại bằng mô hình và thiết lập tiền xử lý đã chọn">Chạy lại AI</button>'''

if target1 in code:
    code = code.replace(target1, replacement1, 1)
    print("REPLACED_TOOLBAR")
else:
    print("TARGET1_NOT_FOUND")

target2 = '''    if (caliperDenoiseCheckbox) {
      caliperDenoiseCheckbox.onchange = (e) => setCaliperDenoise(e.target.checked);
    }'''

handler_code = '''    if (caliperDenoiseCheckbox) {
      caliperDenoiseCheckbox.onchange = (e) => setCaliperDenoise(e.target.checked);
    }

    const btnRerunAI = $(`[data-action="rerun-ai-model"]`);
    const selectModelZoo = $(`#selectModelZoo`);
    if (btnRerunAI) {
      btnRerunAI.onclick = async () => {
        if (!image?.image_id) return toast("Chưa chọn ảnh để chạy dự đoán.", true);
        if (state.busy) return toast("Hệ thống đang xử lý tác vụ khác, vui lòng chờ giây lát.", true);
        const modelKey = selectModelZoo?.value || "attention_unet";
        const query = `?enable_caliper_removal=${Boolean(caliperDenoise)}&denoise_method=${caliperDenoise ? "lee" : "none"}&model_key=${encodeURIComponent(modelKey)}&generate_overlay=true`;
        toast(`Đang chạy suy luận lại với mô hình [${modelKey}]…`);
        try {
          const headers = {};
          if (state.editing?.leaseToken) {
            headers["X-Case-Lease-Token"] = state.editing.leaseToken;
            headers["X-Case-Page-Instance-Id"] = state.editing.pageInstanceId;
          }
          const pred = await request(`/api/predict/${encodeURIComponent(image.image_id)}${query}`, {
            method: "POST",
            headers,
          });
          if (pred && !disposed) {
            image.prediction = pred;
            if (pred.rle_mask) {
              const decodedMask = decode(pred.rle_mask);
              image.mask = decodedMask;
              image.aiMask = decodedMask.slice();
            }
            if (pred.measurements) {
              image.measurements = pred.measurements;
              displayMeasurements(pred.measurements);
            }
            if (pred.original_image_base64) {
              const bmp = await imageSourceBitmap(pred.original_image_base64);
              sourceCtx.clearRect(0, 0, 512, 512);
              sourceCtx.drawImage(bmp, 0, 0, 512, 512);
            }
            schedule();
            toast(`Dự đoán thành công bằng mô hình ${modelKey.toUpperCase()}!`);
          }
        } catch (err) {
          toast(err.message || "Lỗi khi chạy dự đoán mô hình.", true);
        }
      };
    }'''

if target2 in code:
    code = code.replace(target2, handler_code, 1)
    print("REPLACED_HANDLER")
else:
    print("TARGET2_NOT_FOUND")

with open(path, "w", encoding="utf-8") as f:
    f.write(code)
print("SUCCESS_VIEWER_UPDATED")
