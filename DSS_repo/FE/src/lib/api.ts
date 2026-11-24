export class ApiError extends Error {
  constructor(message: string, readonly status: number) { super(message); }
}

/** Calls the NestJS API through the Next.js /api proxy; the session cookie travels automatically. */
export async function api<T>(path: string, body?: unknown, method?: 'GET' | 'POST' | 'PUT' | 'DELETE'): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`/api/${path}`, {
      method: method || (body === undefined ? 'GET' : 'POST'), credentials: 'same-origin',
      headers: body === undefined ? undefined : { 'Content-Type': 'application/json' },
      body: body === undefined ? undefined : JSON.stringify(body), signal: AbortSignal.timeout(20000),
    });
  } catch {
    throw new ApiError('Không kết nối được máy chủ. Kiểm tra API (cổng 4000) đã chạy chưa.', 0);
  }
  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    const message = Array.isArray(data.message) ? data.message.join(' ') : data.message;
    throw new ApiError(message || (response.status >= 500 ? 'Máy chủ đang gặp sự cố. Thử lại sau ít phút.' : `Yêu cầu không thành công (${response.status}).`), response.status);
  }
  return response.json();
}
