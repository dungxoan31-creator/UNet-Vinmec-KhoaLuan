import { state } from "./state.js";

const DEFAULT_REQUEST_TIMEOUT_MS = 45_000;
const UPLOAD_REQUEST_TIMEOUT_MS = 10 * 60 * 1000;

export class ApiError extends Error {
  constructor(message, status) {
    super(message);
    this.status = status;
  }
}

async function withTimeout(signal, timeoutMs, operation) {
  const controller = new AbortController();
  const abortFromCaller = () => controller.abort(signal.reason);
  if (signal?.aborted) abortFromCaller();
  else signal?.addEventListener("abort", abortFromCaller, { once: true });

  const timeout = Number.isFinite(timeoutMs) && timeoutMs > 0
    ? timeoutMs
    : DEFAULT_REQUEST_TIMEOUT_MS;
  const timer = setTimeout(() => controller.abort("timeout"), timeout);
  try {
    const result = await operation(controller.signal);
    if (signal?.aborted) throw new DOMException("Request aborted", "AbortError");
    if (controller.signal.aborted) {
      throw new ApiError("Máy chủ phản hồi quá lâu. Vui lòng thử lại.", 408);
    }
    return result;
  } catch (error) {
    if (!signal?.aborted && controller.signal.aborted) {
      throw new ApiError("Máy chủ phản hồi quá lâu. Vui lòng thử lại.", 408);
    }
    throw error;
  } finally {
    clearTimeout(timer);
    signal?.removeEventListener("abort", abortFromCaller);
  }
}

export async function request(
  path,
  {
    method = "GET",
    body,
    signal = state.routeController?.signal,
    timeoutMs = DEFAULT_REQUEST_TIMEOUT_MS,
    headers: requestHeaders = {},
    ...fetchOptions
  } = {},
) {
  if (!navigator.onLine)
    throw new ApiError("Mất kết nối. Bản nháp vẫn được giữ trên thiết bị.", 0);
  const identity = state.user?.id;
  const token = state.token;
  const sessionChanged = () => identity !== state.user?.id || token !== state.token;
  const headers = {
    ...requestHeaders,
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  };
  if (body && !(body instanceof FormData))
    headers["Content-Type"] = "application/json";

  return withTimeout(signal, timeoutMs, async (requestSignal) => {
    const r = await fetch(path, {
      method,
      headers,
      body:
        body instanceof FormData ? body : body ? JSON.stringify(body) : undefined,
      signal: requestSignal,
      ...fetchOptions,
    });
    if (sessionChanged())
      throw new DOMException("Đã đổi phiên", "AbortError");
    if (r.status === 401) {
      if (path !== "/api/auth/login" && path !== "/api/auth/register") {
        window.dispatchEvent(new CustomEvent("ova:expired"));
      }
      throw new ApiError(
        path === "/api/auth/login"
          ? "Tên đăng nhập hoặc mật khẩu chưa đúng."
          : "Phiên đăng nhập hết hạn. Đăng nhập lại để tiếp tục.",
        401,
      );
    }
    let data;
    try {
      data = r.status === 204 ? {} : await r.json();
    } catch (error) {
      if (error.name === "AbortError") throw error;
      if (r.ok)
        throw new ApiError("Phản hồi JSON của máy chủ không hợp lệ.", r.status);
      data = {};
    }
    if (requestSignal.aborted || sessionChanged())
      throw new DOMException("Đã hủy hoặc đổi phiên", "AbortError");
    if (r.status === 429) {
      const error = new ApiError(
        "Quá nhiều lần thử. Máy chủ tạm khóa yêu cầu.",
        429,
      );
      error.retryAfter = r.headers.get("Retry-After");
      throw error;
    }
    if (!r.ok)
      throw new ApiError(
        [404, 405, 501].includes(r.status)
          ? "Chức năng này chưa khả dụng trên máy chủ. Vui lòng liên hệ quản trị viên."
          : typeof data.detail === "string"
            ? data.detail
            : `Yêu cầu thất bại (${r.status}).`,
        r.status,
      );
    return data;
  });
}

export async function protectedImage(path, timeoutMs = DEFAULT_REQUEST_TIMEOUT_MS) {
  const token = state.token;
  return withTimeout(
    state.routeController?.signal,
    timeoutMs,
    async (signal) => {
      const r = await fetch(path, {
        signal,
        headers: { Authorization: `Bearer ${token}` },
      });
      if (token !== state.token)
        throw new DOMException("Đã đổi phiên", "AbortError");
      if (r.status === 401) {
        window.dispatchEvent(new CustomEvent("ova:expired"));
        throw new ApiError("Phiên đăng nhập hết hạn. Đăng nhập lại để tiếp tục.", 401);
      }
      if (r.status === 429) {
        const error = new ApiError(
          "Quá nhiều lần thử. Máy chủ tạm khóa yêu cầu.",
          429,
        );
        error.retryAfter = r.headers.get("Retry-After");
        throw error;
      }
      if (!r.ok) throw new ApiError("Không tải được ảnh.", r.status);
      const imageUrl = URL.createObjectURL(await r.blob());
      if (signal.aborted || token !== state.token) {
        URL.revokeObjectURL(imageUrl);
        throw new DOMException("Đã hủy hoặc đổi phiên", "AbortError");
      }
      return imageUrl;
    },
  );
}

export function uploadFile(
  file,
  studyId,
  side,
  onProgress,
  signal,
  inspection = null,
  leaseHeaders = {},
  idempotencyKey,
) {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    let settled = false;
    let abortListener;
    const settle = (complete, value) => {
      if (settled) return;
      settled = true;
      if (abortListener) signal?.removeEventListener("abort", abortListener);
      complete(value);
    };
    xhr.open("POST", "/api/upload");
    xhr.timeout = UPLOAD_REQUEST_TIMEOUT_MS;
    xhr.setRequestHeader("Authorization", `Bearer ${state.token}`);
    if (idempotencyKey) xhr.setRequestHeader("Idempotency-Key", idempotencyKey);
    for (const [name, value] of Object.entries(leaseHeaders)) {
      if (value) xhr.setRequestHeader(name, value);
    }
    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable)
        onProgress(Math.round((e.loaded / e.total) * 100));
    };
    xhr.onerror = () => settle(reject, new ApiError("Mất kết nối khi tải ảnh.", 0));
    xhr.onabort = () => settle(reject, new DOMException("Đã hủy", "AbortError"));
    xhr.ontimeout = () => settle(
      reject,
      new ApiError("Tải ảnh quá thời gian chờ 10 phút. Có thể thử lại; ảnh đã ghi nhận sẽ được phát lại an toàn.", 408),
    );
    xhr.onload = () => {
      let data;
      try {
        data = JSON.parse(xhr.responseText);
      } catch {
        return settle(reject,
          new ApiError("Phản hồi tải ảnh không hợp lệ.", xhr.status),
        );
      }
      if (xhr.status === 401)
        window.dispatchEvent(new CustomEvent("ova:expired"));
      xhr.status >= 200 && xhr.status < 300
        ? settle(resolve, data)
        : settle(
            reject,
            new ApiError(
              typeof data.detail === "string"
                ? data.detail
                : "Không tải được ảnh.",
              xhr.status,
            ),
          );
    };
    const form = new FormData();
    form.append("file", file);
    form.append("study_id", studyId);
    form.append("laterality", side);
    if (inspection?.upload_id) {
      form.append("inspected_upload_id", inspection.upload_id);
      form.append("frame_index", inspection.frame);
    }
    if (signal?.aborted)
      return settle(reject, new DOMException("Đã hủy", "AbortError"));
    abortListener = () => xhr.abort();
    signal?.addEventListener("abort", abortListener, { once: true });
    xhr.send(form);
  });
}
