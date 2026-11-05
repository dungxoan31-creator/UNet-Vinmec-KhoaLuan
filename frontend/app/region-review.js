import { esc } from "./ui.js";

const MAX_COMPONENTS = 128;

export function buildRegionAssignments(components, previousIds, selectedByComponent, retiredIds) {
  if (!Array.isArray(components) || components.length > MAX_COMPONENTS ||
      !Array.isArray(previousIds) || !Array.isArray(retiredIds))
    throw new TypeError("Danh sách vùng không hợp lệ.");
  const allowed = new Set(previousIds);
  const assignments = components.map((component) => {
    const selected = selectedByComponent.get(component.component_index) || "";
    if (selected && !allowed.has(selected)) throw new TypeError("ID vùng cũ không còn hợp lệ.");
    return {
      component_index: component.component_index,
      ...(selected ? { previous_region_id: selected } : {}),
    };
  });
  const selectedIds = assignments.map((row) => row.previous_region_id).filter(Boolean);
  if (new Set(selectedIds).size !== selectedIds.length)
    throw new TypeError("Mỗi ID vùng cũ chỉ được liên kết với một vùng mới.");
  if (new Set(retiredIds).size !== retiredIds.length ||
      retiredIds.some((id) => !allowed.has(id)))
    throw new TypeError("Danh sách vùng kết thúc liên kết không hợp lệ.");
  const unmatched = [...allowed].filter((id) => !selectedIds.includes(id));
  if (unmatched.some((id) => !retiredIds.includes(id)) ||
      retiredIds.some((id) => selectedIds.includes(id)))
    throw new TypeError("Hãy chọn mỗi vùng cũ để liên kết hoặc xác nhận kết thúc liên kết.");
  return { assignments, retired_region_ids: [...retiredIds].sort() };
}

function componentHint(index, proposals) {
  if (!proposals) return "Chưa có gợi ý đối chiếu.";
  const match = proposals.unambiguous?.find((item) => item.component_index === index);
  if (match) return `Có thể cùng vùng ${match.previous_id.slice(0, 8)} · bác sĩ cần quyết định`;
  const ambiguous = proposals.ambiguous?.find((item) => item.component_index === index);
  if (ambiguous) return `Liên kết mơ hồ · ${ambiguous.previous_ids.map((id) => id.slice(0, 8)).join(", ")}`;
  if (proposals.new_components?.includes(index)) return "Vùng mới hoặc chưa có liên kết hình học.";
  return "Chưa có liên kết hình học.";
}

export function bindRegionReview(root, { request, getContext, onSaved, onCandidates, onHighlight, onSelectRegion, signal } = {}) {
  const mount = root?.querySelector?.("#regionReviewMount");
  if (!mount || typeof request !== "function" || typeof getContext !== "function")
    return { setContext() {}, destroy() {} };
  let context = null;
  let generation = 0;
  let controller = null;
  let snapshot = null;
  let proposals = null;
  let latest = null;
  let loading = false;
  let submitting = false;
  let error = "";
  let reloadRequired = false;
  let accepted = false;
  let pendingPayload = null;
  let selectedByComponent = new Map();
  let retiredRegionIds = new Set();
  let selectedRegionId = null;

  const isCurrent = (version) => version === generation && !controller?.signal.aborted;
  const render = () => {
    if (!context?.reviewId || !context.maskMatchesReview) {
      mount.innerHTML = `<p class="muted small">${context?.reviewId ? "Mask nháp khác với review đã lưu. Lưu review hoặc tải lại ảnh trước khi tiếp tục đối chiếu vùng." : "Lưu kết quả đánh giá của ảnh trước khi kiểm tra các vùng đã xác nhận."}</p>`;
      return;
    }
    const hasEditLease = Boolean(context.canEdit && context.leaseToken && context.pageInstanceId);
    const currentAssignment = latest?.assignment;
    const currentIds = new Map((currentAssignment?.assignments || []).map((row) => [row.component_index, row.region_id]));
    const previousIds = [
      ...(proposals?.unambiguous || []).map((row) => row.previous_id),
      ...(proposals?.ambiguous || []).flatMap((row) => row.previous_ids || []),
      ...(proposals?.missing_previous_ids || []),
    ];
    const uniquePreviousIds = [...new Set(previousIds)].sort();
    const components = snapshot?.components || [];
    const alreadyConfirmed = Boolean(context.maskMatchesReview && currentAssignment && !latest?.stale && currentAssignment.review_id === context.reviewId);
    mount.innerHTML = `<section class="region-review" aria-labelledby="regionReviewHeading">
      <h3 id="regionReviewHeading">Đối chiếu vùng tổn thương</h3>
      <p class="muted small">Định danh hình học trong một ảnh; không xác định loại tổn thương, không phải CDSS. Gợi ý không được áp dụng tự động. Rê chuột hoặc chuyển tiêu điểm đến vùng để tô sáng mask trên ảnh.</p>
      ${snapshot && currentAssignment && !latest?.stale ? `<p class="small">Snapshot đã lưu · revision ${esc(currentAssignment.review_revision)}</p>` : ""}
      ${latest?.stale ? `<p class="banner warning small" role="status">Có review mới hơn snapshot đã xác nhận. Kiểm tra từng ID trước khi tiếp tục.</p>` : ""}
      ${error ? `<p class="banner danger small" role="alert">${esc(error)}</p>${reloadRequired ? `<button class="btn small" type="button" data-region-reload>Tải lại trạng thái từ máy chủ</button>` : ""}` : ""}
      ${!snapshot ? `<button class="btn small" type="button" data-region-load ${loading ? "disabled" : ""}>${loading ? "Đang đọc review đã lưu…" : "Tải các vùng đã lưu"}</button>` : `
        <p class="muted small">${components.length} vùng · mask ${esc(snapshot.mask_sha256.slice(0, 12))}… · ${esc(snapshot.algorithm)}</p>
        ${components.length ? `<div class="region-component-list">${components.map((component) => `
          <div class="region-component" data-region-component="${component.component_index}">
            <strong>Vùng ${component.component_index} · ${component.pixel_count} px</strong>
            <span class="muted small">Hộp x=${component.bounding_box_xywh[0]}, y=${component.bounding_box_xywh[1]}, ${component.bounding_box_xywh[2]}×${component.bounding_box_xywh[3]} px · seed ${component.seed_xy.join(", ")}</span>
            <span class="muted small">${esc(componentHint(component.component_index, proposals))}</span>
            ${currentIds.has(component.component_index) && !latest?.stale ? `<span class="small">ID đã lưu: ${esc(currentIds.get(component.component_index))}</span>` : ""}
            ${alreadyConfirmed && latest?.assignment?.assignment_request_id ? `<button class="btn small" type="button" data-region-select="${esc(currentIds.get(component.component_index) || "")}" data-component-index="${component.component_index}" aria-pressed="${selectedRegionId === currentIds.get(component.component_index)}">${selectedRegionId === currentIds.get(component.component_index) ? "Đang chọn vùng này" : "Chọn vùng cho caliper và CDSS"}</button>` : ""}
            ${!alreadyConfirmed ? `<label class="field small">Liên kết hình học
              <select data-region-choice="${component.component_index}" ${!hasEditLease || submitting ? "disabled" : ""}>
                <option value="" ${!selectedByComponent.get(component.component_index) ? "selected" : ""}>Vùng mới / chưa liên kết</option>
                ${uniquePreviousIds.map((id) => `<option value="${esc(id)}" ${selectedByComponent.get(component.component_index) === id ? "selected" : ""}>Giữ ID ${esc(id.slice(0, 8))}</option>`).join("")}
              </select>
            </label>` : ""}
          </div>`).join("")}</div>` : `<p class="muted small">Mask review này không có component. Số 0 chỉ mô tả mask rỗng, không phải kết luận lâm sàng.</p>`}
        ${uniquePreviousIds.length && !alreadyConfirmed ? `<fieldset class="region-retired" ${!hasEditLease || submitting ? "disabled" : ""}>
          <legend>Vùng cũ không được liên kết</legend>
          ${uniquePreviousIds.map((id) => `<label class="check-row"><input type="checkbox" data-region-retire="${esc(id)}" ${retiredRegionIds.has(id) ? "checked" : ""}> Kết thúc liên kết hình học với ${esc(id)}</label>`).join("")}
        </fieldset>` : ""}
        ${alreadyConfirmed ? `<p class="banner info small" role="status">Các vùng của review hiện tại đã được xác nhận.</p>` : `
        <label class="check-row region-confirm"><input type="checkbox" data-region-accepted ${accepted ? "checked" : ""} ${!hasEditLease || submitting ? "disabled" : ""}> Tôi đã đối chiếu từng vùng; đây chỉ là liên kết hình học trong ảnh.</label>
        <button class="btn small primary" type="button" data-region-submit ${!hasEditLease || submitting || !accepted ? "disabled" : ""}>${submitting ? "Đang lưu…" : "Xác nhận quyết định vùng"}</button>`}
        ${!hasEditLease ? `<p class="muted small">Cần quyền bác sĩ và lease chỉnh sửa đang hoạt động để lưu.</p>` : ""}`}
    </section>`;
    mount.querySelector("[data-region-load]")?.addEventListener("click", load);
    mount.querySelector("[data-region-reload]")?.addEventListener("click", load);
    mount.querySelectorAll("[data-region-choice]").forEach((select) => {
      select.addEventListener("change", () => {
        selectedByComponent.set(Number(select.dataset.regionChoice), select.value);
        pendingPayload = null;
        accepted = false;
        error = "";
        render();
      });
    });
    mount.querySelectorAll("[data-region-component]").forEach((row) => {
      const highlight = () => onHighlight?.(Number(row.dataset.regionComponent));
      const clear = () => onHighlight?.(null);
      row.addEventListener("mouseenter", highlight);
      row.addEventListener("mouseleave", clear);
      row.addEventListener("focusin", highlight);
      row.addEventListener("focusout", clear);
    });
    mount.querySelectorAll("[data-region-select]").forEach((button) => {
      button.addEventListener("click", () => {
        const regionId = button.dataset.regionSelect;
        const componentIndex = Number(button.dataset.componentIndex);
        const currentAssignment = latest?.assignment;
        if (!alreadyConfirmed || !regionId || !currentAssignment?.assignment_request_id || latest?.stale) {
          error = "Snapshot vùng đã cũ hoặc thiếu ID lưu máy chủ; tải lại trước khi chọn.";
          render();
          return;
        }
        selectedRegionId = regionId;
        onHighlight?.(componentIndex);
        onSelectRegion?.({
          studyId: context.studyId,
          imageId: context.imageId,
          reviewId: currentAssignment.review_id,
          reviewRevision: currentAssignment.review_revision,
          maskSha256: currentAssignment.mask_sha256,
          assignmentRequestId: currentAssignment.assignment_request_id,
          regionId,
          componentIndex,
        });
        render();
      });
    });
    mount.querySelectorAll("[data-region-retire]").forEach((input) => {
      input.addEventListener("change", () => {
        if (input.checked) retiredRegionIds.add(input.dataset.regionRetire);
        else retiredRegionIds.delete(input.dataset.regionRetire);
        pendingPayload = null;
        accepted = false;
        error = "";
        render();
      });
    });
    mount.querySelector("[data-region-accepted]")?.addEventListener("change", (event) => {
      accepted = event.target.checked;
      mount.querySelector("[data-region-submit]")?.toggleAttribute("disabled", !accepted || submitting || !hasEditLease);
    });
    mount.querySelector("[data-region-submit]")?.addEventListener("click", submit);
  };

  const load = async () => {
    const current = getContext();
    if (!current?.reviewId || !current.maskMatchesReview) {
      error = "Lưu review hiện tại trước; mask nháp khác với mask review trên máy chủ.";
      render();
      return;
    }
    context = current;
    generation += 1;
    controller?.abort();
    controller = new AbortController();
    const version = generation;
    loading = true;
    error = "";
    reloadRequired = false;
    snapshot = null;
    proposals = null;
    latest = null;
    render();
    const base = `/api/cases/${encodeURIComponent(current.studyId)}/images/${encodeURIComponent(current.imageId)}`;
    const reviewBase = `${base}/reviews/${encodeURIComponent(current.reviewId)}`;
    try {
      const [candidates, assignmentState, links] = await Promise.all([
        request(`${reviewBase}/region-candidates`, { signal: controller.signal }),
        request(`${base}/region-assignments`, { signal: controller.signal }),
        request(`${reviewBase}/region-proposals`, { signal: controller.signal }),
      ]);
      if (!isCurrent(version)) return;
      if (candidates.mask_sha256 !== links.mask_sha256 || candidates.review_id !== current.reviewId ||
          links.review_id !== current.reviewId || candidates.algorithm !== links.algorithm)
        throw new Error("Dữ liệu component và đề xuất không cùng một review/mask.");
      if (onCandidates?.(candidates) === false)
        throw new Error("Không thể đồng nhất vị trí component API với mask review trên canvas.");
      snapshot = candidates;
      latest = assignmentState;
      proposals = links;
      selectedByComponent = new Map();
      retiredRegionIds = new Set();
      accepted = false;
      loading = false;
      pendingPayload = null;
      render();
    } catch (loadError) {
      if (!isCurrent(version) || loadError?.name === "AbortError") return;
      loading = false;
      error = loadError?.message || "Không thể tải đối chiếu vùng.";
      reloadRequired = loadError?.status === 409;
      render();
    }
  };

  const submit = async () => {
    if (!accepted || submitting || !snapshot || !context?.canEdit) return;
    const choices = new Map([...mount.querySelectorAll("[data-region-choice]")]
      .map((select) => [Number(select.dataset.regionChoice), select.value]));
    const retired = [...mount.querySelectorAll("[data-region-retire]:checked")].map((input) => input.dataset.regionRetire);
    const previousIds = [
      ...(proposals?.unambiguous || []).map((row) => row.previous_id),
      ...(proposals?.ambiguous || []).flatMap((row) => row.previous_ids || []),
      ...(proposals?.missing_previous_ids || []),
    ];
    const uniquePreviousIds = [...new Set(previousIds)].sort();
    let decisions;
    try {
      decisions = buildRegionAssignments(snapshot.components, uniquePreviousIds, choices, retired);
    } catch (validationError) {
      error = validationError.message;
      render();
      return;
    }
    const previousContext = context;
    const current = getContext();
    if (!current?.canEdit || current.studyId !== previousContext?.studyId ||
        current.imageId !== previousContext?.imageId || current.reviewId !== previousContext?.reviewId ||
        current.maskMatchesReview !== true) {
      error = "Ca, ảnh, review hoặc quyền chỉnh sửa đã thay đổi; tải lại trước khi lưu.";
      pendingPayload = null;
      context = current;
      render();
      return;
    }
    context = current;
    const payloadContent = {
      expected_revision: current.reviewRevision,
      mask_sha256: snapshot.mask_sha256,
      confirmed: true,
      ...decisions,
    };
    const signature = JSON.stringify(payloadContent);
    if (!pendingPayload || pendingPayload.signature !== signature) {
      pendingPayload = { signature, request_id: crypto.randomUUID(), ...payloadContent };
    }
    const payload = {
      ...pendingPayload,
      lease_token: current.leaseToken,
      page_instance_id: current.pageInstanceId,
    };
    const version = generation;
    submitting = true;
    error = "";
    render();
    try {
      const base = `/api/cases/${encodeURIComponent(current.studyId)}/images/${encodeURIComponent(current.imageId)}`;
      const result = await request(`${base}/reviews/${encodeURIComponent(current.reviewId)}/region-assignments`, {
        method: "POST", body: payload, signal: controller?.signal,
      });
      if (!isCurrent(version)) return;
      context.reviewRevision = result.review_revision;
      pendingPayload = null;
      accepted = false;
      onSaved?.(result);
      await load();
    } catch (submitError) {
      if (!isCurrent(version) || submitError?.name === "AbortError") return;
      error = submitError?.message || "Không lưu được quyết định vùng.";
      if (submitError?.status === 409) {
        pendingPayload = null;
        accepted = false;
        reloadRequired = true;
      }
    } finally {
      if (isCurrent(version)) {
        submitting = false;
        render();
      }
    }
  };

  const setContext = (next) => {
    generation += 1;
    controller?.abort();
    controller = new AbortController();
    context = next || null;
    snapshot = null;
    proposals = null;
    latest = null;
    loading = false;
    submitting = false;
    error = "";
    reloadRequired = false;
    accepted = false;
    pendingPayload = null;
    selectedByComponent = new Map();
    retiredRegionIds = new Set();
    selectedRegionId = null;
    onHighlight?.(null);
    onCandidates?.(null);
    render();
  };
  const setEditable = (enabled) => {
    if (!context) return;
    const canEdit = Boolean(enabled);
    if (context.canEdit === canEdit) return;
    context = { ...context, canEdit };
    render();
  };
  const onLeaseLost = () => {
    if (!context) return;
    context = { ...context, ...getContext() };
    render();
  };
  const onReviewSaved = (event) => {
    if (!context || event.detail?.studyId !== context.studyId ||
        !event.detail?.imageIds?.includes(context.imageId)) return;
    setContext(getContext());
  };
  window.addEventListener("ova:lease-lost", onLeaseLost);
  window.addEventListener("ova:review-saved", onReviewSaved);
  signal?.addEventListener("abort", () => controller?.abort(), { once: true });
  render();
  return {
    setContext,
    setEditable,
    destroy() {
      generation += 1;
      controller?.abort();
      window.removeEventListener("ova:lease-lost", onLeaseLost);
      window.removeEventListener("ova:review-saved", onReviewSaved);
      mount.replaceChildren();
    },
  };
}
