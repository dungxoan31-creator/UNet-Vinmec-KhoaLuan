const LANGUAGE = "vi-VN";
const LOCAL_ONLY = { langs: [LANGUAGE], processLocally: true };

export function bindLocalDictation({
  browser = globalThis,
  input,
  recordButton,
  status,
  preview,
  insertButton,
  discardButton,
  compact = false,
}) {
  let generation = 0;
  let recognition = null;
  let starting = false;
  let disposed = false;
  let pending = "";
  const setRecording = (recording) => {
    const label = recording ? 'Dừng nhập giọng nói' : 'Nhập bằng giọng nói';
    if (!compact) { recordButton.textContent = recording ? 'Dừng đọc chính tả' : 'Đọc chính tả cục bộ'; return; }
    recordButton.innerHTML = '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true"><rect x="9" y="2" width="6" height="12" rx="3"/><path d="M5 10v2a7 7 0 0 0 14 0v-2M12 19v3M8 22h8"/></svg>';
    recordButton.setAttribute('aria-label', label);
    recordButton.setAttribute('aria-pressed', String(recording));
    recordButton.title = label;
  };
  if (compact) setRecording(false);

  const showPreview = (transcript) => {
    pending = transcript;
    preview.textContent = transcript;
    preview.hidden = !transcript;
    insertButton.disabled = !transcript || input.disabled;
    discardButton.disabled = !transcript;
    if (compact) {
      insertButton.hidden = !transcript;
      discardButton.hidden = !transcript;
    }
  };
  const clearPreview = () => showPreview("");
  if (compact) clearPreview();
  const setStatus = (message) => {
    status.textContent = message;
    if (compact) status.hidden = !message;
  };

  const cancel = () => {
    const hadWork = Boolean(recognition || starting || pending);
    generation++;
    starting = false;
    const activeRecognition = recognition;
    recognition = null;
    clearPreview();
    setRecording(false);
    if (activeRecognition) {
      try {
        activeRecognition.abort();
      } catch {
        // A recognizer may already have stopped; discard it either way.
      }
    }
    setStatus(compact && !hadWork ? '' : "Đã hủy; bản chép chờ đã được xóa.");
  };

  const start = async () => {
    if (disposed || starting) return;
    if (recognition) {
      cancel();
      return;
    }

    const session = ++generation;
    starting = true;
    clearPreview();
    setStatus("Đang kiểm tra khả năng nhận dạng tiếng Việt trên thiết bị…");

    const SpeechRecognition =
      browser?.SpeechRecognition || browser?.webkitSpeechRecognition;
    if (
      !SpeechRecognition ||
      typeof SpeechRecognition.available !== "function" ||
      !SpeechRecognition.prototype ||
      !("processLocally" in SpeechRecognition.prototype)
    ) {
      starting = false;
      setStatus("Đọc chính tả ngoại tuyến không khả dụng trong trình duyệt này.");
      return;
    }

    try {
      const availability = await SpeechRecognition.available(LOCAL_ONLY);
      if (disposed || session !== generation) return;
      if (availability !== "available") {
        starting = false;
        setStatus("Không có tiếng Việt ngoại tuyến trên thiết bị; không gửi giọng nói qua mạng.");
        return;
      }

      const nextRecognition = new SpeechRecognition();
      if (!("processLocally" in nextRecognition)) {
        starting = false;
        setStatus("Trình duyệt chưa xác nhận xử lý giọng nói trên thiết bị.");
        return;
      }
      nextRecognition.lang = LANGUAGE;
      nextRecognition.processLocally = true;
      if (nextRecognition.processLocally !== true) {
        starting = false;
        setStatus("Không bật được xử lý trên thiết bị; giọng nói chưa được ghi lại.");
        return;
      }
      nextRecognition.continuous = false;
      nextRecognition.interimResults = true;
      recognition = nextRecognition;

      nextRecognition.onresult = (event) => {
        if (disposed || session !== generation || recognition !== nextRecognition)
          return;
        const transcript = Array.from(event.results || [])
          .map((result) => result?.[0]?.transcript || "")
          .filter(Boolean)
          .join(" ")
          .trim();
        showPreview(transcript);
        setStatus(
          transcript
            ? "Bản chép đang ở chế độ xem trước. Hãy kiểm tra trước khi chèn vào ghi chú."
            : "Đang nghe tiếng Việt trên thiết bị…",
        );
      };
      nextRecognition.onerror = (event) => {
        if (disposed || session !== generation || recognition !== nextRecognition)
          return;
        const message =
          event?.error === "not-allowed" || event?.error === "service-not-allowed"
            ? "Quyền micro: cấp quyền trên thiết bị. Bản chép đã được xóa; âm thanh chỉ xử lý cục bộ."
            : "Nhận dạng cục bộ tạm dừng. Bản chép đã được xóa; âm thanh chỉ xử lý trên thiết bị.";
        cancel();
        setStatus(message);
      };
      nextRecognition.onend = () => {
        if (disposed || session !== generation || recognition !== nextRecognition)
          return;
        recognition = null;
        setRecording(false);
        setStatus(
          pending
            ? "Đã dừng. Hãy kiểm tra bản chép xem trước trước khi chèn."
            : "Bản chép đang trống. Chọn Đọc chính tả để thử lại.",
        );
      };

      nextRecognition.start();
      setRecording(true);
      setStatus("Đang nghe tiếng Việt trên thiết bị…");
    } catch (error) {
      if (!disposed && session === generation) {
        recognition = null;
        clearPreview();
        setRecording(false);
        setStatus(
          error?.name === "NotAllowedError"
            ? "Quyền micro: cấp quyền trong cài đặt thiết bị."
            : "Nhận dạng cục bộ đang tạm dừng; âm thanh chỉ xử lý trên thiết bị.",
        );
      }
    } finally {
      if (session === generation) starting = false;
    }
  };

  const insert = () => {
    if (!pending || disposed || input.disabled) return;
    const current = input.value || "";
    const separator = current && !/\s$/.test(current) ? " " : "";
    input.value = current + separator + pending;
    const EventConstructor = browser?.Event || globalThis.Event;
    if (EventConstructor)
      input.dispatchEvent(new EventConstructor("input", { bubbles: true }));
    clearPreview();
    setStatus("Bản chép đã được chèn vào ghi chú; vui lòng rà soát trước khi lưu.");
  };
  const discard = () => {
    clearPreview();
    setStatus("Đã bỏ bản chép xem trước; ghi chú chưa thay đổi.");
  };

  recordButton.addEventListener("click", start);
  insertButton.addEventListener("click", insert);
  discardButton.addEventListener("click", discard);

  return {
    cancel,
    dispose() {
      if (disposed) return;
      cancel();
      disposed = true;
      recordButton.removeEventListener("click", start);
      insertButton.removeEventListener("click", insert);
      discardButton.removeEventListener("click", discard);
    },
  };
}
