with open("frontend/app/viewer.js", "r", encoding="utf-8") as f:
    content = f.read()

target = """    const caliperDenoiseButton = $(`[data-action="toggle-caliper-denoise"]`);
    const caliperDenoiseCheckbox = $(`#caliperDenoiseToggle`);
    const setCaliperDenoise = (activeState) => {
      caliperDenoise = Boolean(activeState);
      if (caliperDenoiseButton) {
        caliperDenoiseButton.setAttribute("aria-pressed", String(caliperDenoise));
        caliperDenoiseButton.classList.toggle("primary", caliperDenoise);
      }
      if (caliperDenoiseCheckbox) {
        caliperDenoiseCheckbox.checked = caliperDenoise;
      }
      toast(
        caliperDenoise
          ? "Đã bật: Tự động xóa Caliper & Khử nhiễu đốm âm học (Edge-Preserving)"
          : "Đã tắt chế độ xóa caliper & lọc đốm"
      );
      schedule();
    };

    if (caliperDenoiseButton) {
      caliperDenoiseButton.onclick = () => setCaliperDenoise(!caliperDenoise);
    }
    if (caliperDenoiseCheckbox) {
      caliperDenoiseCheckbox.onchange = (e) => setCaliperDenoise(e.target.checked);
    }

    $("[data-action=image-reset]").onclick = () => {
      brightness = contrast = 100;
      $("#brightness").value = $("#contrast").value = 100;
      if (caliperDenoise) {
        caliperDenoise = false;
        if (caliperDenoiseButton) {
          caliperDenoiseButton.setAttribute("aria-pressed", "false");
          caliperDenoiseButton.classList.remove("primary");
        }
        if (caliperDenoiseCheckbox) caliperDenoiseCheckbox.checked = false;
      }
      schedule();
    };"""

replacement = """    const caliperDenoiseButton = $(`[data-action="toggle-caliper-denoise"]`);
    const caliperDenoiseCheckbox = $(`#caliperDenoiseToggle`);
    const setCaliperDenoise = (activeState) => {
      caliperDenoise = Boolean(activeState);
      if (caliperDenoiseButton) {
        caliperDenoiseButton.setAttribute("aria-pressed", String(caliperDenoise));
        caliperDenoiseButton.classList.toggle("primary", caliperDenoise);
      }
      if (caliperDenoiseCheckbox) {
        caliperDenoiseCheckbox.checked = caliperDenoise;
      }
      toast(
        caliperDenoise
          ? "Đang xử lý: Tự động xóa Caliper và lọc đốm âm học…"
          : "Đã khôi phục ảnh siêu âm gốc"
      );

      // Live Backend Integration: Fetch enhanced / original image from API
      if (image?.image_id) {
        const query = caliperDenoise
          ? "?enable_caliper_removal=true&denoise_method=lee"
          : "?enable_caliper_removal=false&denoise_method=none";
        request(`/api/images/${encodeURIComponent(image.image_id)}/viewer-source${query}`)
          .then(async (res) => {
            if (res?.original_image_base64 && !disposed) {
              const enhancedBitmap = await imageSourceBitmap(res.original_image_base64);
              sourceCtx.clearRect(0, 0, 512, 512);
              sourceCtx.drawImage(enhancedBitmap, 0, 0, 512, 512);
              schedule();
              if (caliperDenoise) {
                toast("Đã áp dụng: Xóa Caliper và lọc đốm thành công.");
              }
            }
          })
          .catch((err) => {
            console.warn("Lỗi cập nhật ảnh tiền xử lý:", err);
            schedule();
          });
      } else {
        schedule();
      }
    };

    if (caliperDenoiseButton) {
      caliperDenoiseButton.onclick = () => setCaliperDenoise(!caliperDenoise);
    }
    if (caliperDenoiseCheckbox) {
      caliperDenoiseCheckbox.onchange = (e) => setCaliperDenoise(e.target.checked);
    }

    $("[data-action=image-reset]").onclick = () => {
      brightness = contrast = 100;
      $("#brightness").value = $("#contrast").value = 100;
      if (caliperDenoise) {
        caliperDenoise = false;
        if (caliperDenoiseButton) {
          caliperDenoiseButton.setAttribute("aria-pressed", "false");
          caliperDenoiseButton.classList.remove("primary");
        }
        if (caliperDenoiseCheckbox) caliperDenoiseCheckbox.checked = false;
        if (image?.image_id) {
          request(`/api/images/${encodeURIComponent(image.image_id)}/viewer-source?enable_caliper_removal=false&denoise_method=none`)
            .then(async (res) => {
              if (res?.original_image_base64 && !disposed) {
                const rawBitmap = await imageSourceBitmap(res.original_image_base64);
                sourceCtx.clearRect(0, 0, 512, 512);
                sourceCtx.drawImage(rawBitmap, 0, 0, 512, 512);
                schedule();
              }
            })
            .catch(() => schedule());
        }
      }
      schedule();
    };"""

# Normalize newlines
content_norm = content.replace("\r\n", "\n")
target_norm = target.replace("\r\n", "\n")
replacement_norm = replacement.replace("\r\n", "\n")

if target_norm in content_norm:
    content_norm = content_norm.replace(target_norm, replacement_norm)
    with open("frontend/app/viewer.js", "w", encoding="utf-8") as f:
        f.write(content_norm)
    print("SUCCESS: viewer.js updated with live caliper denoise integration!")
else:
    print("ERROR: Target block not found in viewer.js")
