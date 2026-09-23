const apiBase = import.meta.env.VITE_API_BASE_URL ?? "/api";

export type PlatformUser = {
  id: string;
  email: string;
  full_name: string;
  role: string;
  is_active: boolean;
  tenant?: { id: string; name: string };
};

type ApiError = { error?: { message?: string }; detail?: string };

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const token = localStorage.getItem("hcap_token");
  const response = await fetch(`${apiBase}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Token ${token}` } : {}),
      ...init.headers,
    },
  });
  if (!response.ok) {
    const payload = (await response.json().catch(() => ({}))) as ApiError;
    throw new Error(payload.error?.message ?? payload.detail ?? "Request failed");
  }
  return response.json() as Promise<T>;
}

export const api = {
  async login(email: string, password: string) {
    const result = await request<{ user: PlatformUser; token: string }>("/auth/login/", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    });
    localStorage.setItem("hcap_token", result.token);
    return result.user;
  },
  me: () => request<PlatformUser>("/me/"),
  users: () => request<PlatformUser[] | { results: PlatformUser[] }>("/users/"),
  createUser: (payload: Pick<PlatformUser, "email" | "full_name" | "role"> & { password: string }) =>
    request<PlatformUser>("/users/", { method: "POST", body: JSON.stringify(payload) }),
  clearToken: () => localStorage.removeItem("hcap_token"),
};
