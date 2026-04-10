/**
 * FastAPI バックエンドへのリクエストを行うクライアントユーティリティ。
 * サーバーサイド（Route Handlers / Server Components）から呼び出す想定。
 * NEXT_PUBLIC_ は付けず、環境変数 API_INTERNAL_URL をサーバー専用変数として使用する。
 */

const API_BASE = process.env.API_INTERNAL_URL ?? "http://localhost:8080";

export async function apiFetch<T>(
  path: string,
  init?: RequestInit
): Promise<T> {
  const url = `${API_BASE}${path}`;
  const res = await fetch(url, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
  });

  if (!res.ok) {
    const text = await res.text();
    throw new Error(`API error ${res.status}: ${text}`);
  }

  // 204 No Content など body が無い場合は null を返す
  if (res.status === 204) return null as T;

  return res.json() as Promise<T>;
}
