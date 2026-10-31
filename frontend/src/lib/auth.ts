import { api } from "../api/client";

export interface User {
  id: string;
  email: string;
  full_name: string;
  role: "admin" | "staff" | "customer";
  is_active: boolean;
  customer_id: string | null;
}

export interface TokenResponse {
  access_token: string;
  user: User;
}

const KEY = "brightloop.token";

export const getToken = () => localStorage.getItem(KEY);
export const setToken = (t: string | null) =>
  t ? localStorage.setItem(KEY, t) : localStorage.removeItem(KEY);

export async function login(email: string, password: string) {
  const r = await api<TokenResponse>("/auth/login", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
  setToken(r.access_token);
  return r.user;
}

export async function register(body: {
  email: string;
  password: string;
  full_name: string;
  phone?: string;
  billing_address?: string;
}) {
  const r = await api<TokenResponse>("/auth/register", {
    method: "POST",
    body: JSON.stringify(body),
  });
  setToken(r.access_token);
  return r.user;
}

export const forgotPassword = (email: string) =>
  api<{ ok: boolean; message: string }>("/auth/forgot-password", {
    method: "POST",
    body: JSON.stringify({ email }),
  });

export const resetPassword = (token: string, new_password: string) =>
  api<{ ok: boolean }>("/auth/reset-password", {
    method: "POST",
    body: JSON.stringify({ token, new_password }),
  });

export const me = () => api<User>("/auth/me");
export const logout = () => setToken(null);
