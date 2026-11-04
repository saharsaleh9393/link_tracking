"use client";
import { useEffect, useState } from "react";
export type Params = Record<
  string,
  string | number | boolean | string[] | null | undefined
>;
export class ApiError extends Error {
  constructor(public code: string) {
    super(code);
  }
}
export function queryString(params: Params = {}) {
  const q = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== null && value !== undefined) {
      if (Array.isArray(value)) value.forEach((v) => q.append(key, v));
      else q.set(key, String(value));
    }
  });
  return q.toString();
}
export async function request<T>(
  path: string,
  {
    method = "GET",
    body,
    signal,
  }: { method?: string; body?: unknown; signal?: AbortSignal } = {},
): Promise<T> {
  let response;
  try {
    response = await fetch("/api/tracker/" + path, {
      method,
      body: body === undefined ? undefined : JSON.stringify(body),
      headers: { "Content-Type": "application/json" },
      signal,
      cache: "no-store",
    });
  } catch (error) {
    if (error instanceof Error && error.name === "AbortError") throw error;
    throw new ApiError("UNAVAILABLE");
  }
  if (!response.ok) {
    const data = await response.json().catch(() => ({ code: "GENERIC" }));
    throw new ApiError(data.code || "GENERIC");
  }
  return response.status === 204 ? (undefined as T) : response.json();
}
export function useResource<T>(path: string, params: Params = {}, version = 0) {
  const endpoint = path + "?" + queryString(params);
  const key = endpoint + "#" + version;
  const [state, setState] = useState<{ key: string; data?: T; error?: string }>(
    { key: "" },
  );
  useEffect(() => {
    const controller = new AbortController();
    request<T>(endpoint, { signal: controller.signal })
      .then((data) => setState({ key, data }))
      .catch((error) => {
        if (!controller.signal.aborted)
          setState({
            key,
            error: error instanceof ApiError ? error.code : "GENERIC",
          });
      });
    return () => controller.abort();
  }, [endpoint, key]);
  return {
    data: state.key === key ? state.data : undefined,
    error: state.key === key ? state.error : undefined,
    loading: state.key !== key,
  };
}
