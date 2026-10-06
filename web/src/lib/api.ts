// Thin client for the Taki API. Every mutating call carries the header the
// server requires, and errors surface as ApiError with a readable message.

export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) { super(message); this.status = status; }
}

type Handler = () => void;
let onUnauthorised: Handler | null = null;
export function setUnauthorisedHandler(h: Handler | null) { onUnauthorised = h; }

async function parseError(res: Response): Promise<string> {
  try {
    const j = await res.json();
    if (typeof j?.detail === 'string') return j.detail;
    if (Array.isArray(j?.detail) && j.detail[0]?.msg) return j.detail[0].msg;
  } catch { /* not JSON */ }
  if (res.status === 413) return 'That request is too large.';
  if (res.status >= 500) return 'The server had a problem with that request.';
  return `Request failed (${res.status}).`;
}

async function request<T>(method: string, path: string, body?: unknown, signal?: AbortSignal): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`/api${path}`, {
      method,
      credentials: 'same-origin',
      headers: body !== undefined || method !== 'GET'
        ? { 'Content-Type': 'application/json', 'X-Requested-With': 'taki' }
        : undefined,
      body: body !== undefined ? JSON.stringify(body) : (method !== 'GET' ? '{}' : undefined),
      signal,
    });
  } catch (e: any) {
    if (e?.name === 'AbortError') throw e;
    throw new ApiError('Cannot reach the server. Check that Taki is still running.', 0);
  }
  if (res.status === 401 && !path.startsWith('/auth/')) onUnauthorised?.();
  if (!res.ok) throw new ApiError(await parseError(res), res.status);
  return res.json() as Promise<T>;
}

export const api = {
  get: <T,>(path: string, signal?: AbortSignal) => request<T>('GET', path, undefined, signal),
  post: <T,>(path: string, body?: unknown, signal?: AbortSignal) => request<T>('POST', path, body ?? {}, signal),
  put: <T,>(path: string, body?: unknown) => request<T>('PUT', path, body ?? {}),
  patch: <T,>(path: string, body?: unknown) => request<T>('PATCH', path, body ?? {}),
  del: <T,>(path: string) => request<T>('DELETE', path),

  /** POST that returns a file; triggers a browser download. */
  async download(path: string, body: unknown): Promise<void> {
    const res = await fetch(`/api${path}`, {
      method: 'POST', credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json', 'X-Requested-With': 'taki' },
      body: JSON.stringify(body ?? {}),
    });
    if (!res.ok) throw new ApiError(await parseError(res), res.status);
    const blob = await res.blob();
    const cd = res.headers.get('Content-Disposition') || '';
    const m = /filename="?([^"]+)"?/.exec(cd);
    saveBlob(blob, m ? m[1] : 'taki-download');
  },
};

export function saveBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url; a.download = filename;
  document.body.appendChild(a); a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 2000);
}

export function saveText(text: string, filename: string, type = 'text/plain') {
  saveBlob(new Blob([text], { type: `${type};charset=utf-8` }), filename);
}
