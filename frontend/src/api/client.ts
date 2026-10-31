const BASE = import.meta.env.VITE_API_BASE_URL ?? "/api/v1";

export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
    public details?: Record<string, unknown>,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const token = localStorage.getItem("brightloop.token");
  const res = await fetch(`${BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(init?.headers ?? {}),
    },
  });

  if (res.status === 401 && token) {
    localStorage.removeItem("brightloop.token");
    if (!location.pathname.startsWith("/login")) location.assign("/login");
  }

  if (!res.ok) {
    let code = "ERROR";
    let message = res.statusText;
    let details: Record<string, unknown> | undefined;
    try {
      const body = await res.json();
      code = body?.error?.code ?? code;
      message = body?.error?.message ?? message;
      details = body?.error?.details;
    } catch {
      // non-JSON error body — keep defaults
    }
    throw new ApiError(res.status, code, message, details);
  }
  return res.json() as Promise<T>;
}

/** Build a `?a=1&b=2` query string, dropping empty/undefined params. */
export function qs(
  params: Record<string, string | number | boolean | null | undefined>,
): string {
  const p = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null && value !== "") {
      p.set(key, String(value));
    }
  }
  const s = p.toString();
  return s ? `?${s}` : "";
}
