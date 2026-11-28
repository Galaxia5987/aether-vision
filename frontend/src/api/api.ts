// REST client for the Aether Vision backend.

import type { JsonObject, JsonSchema } from './types'

export class ApiError extends Error {
  constructor(
    readonly status: number,
    message: string,
  ) {
    super(message)
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, init)
  if (!response.ok) {
    let detail = response.statusText
    try {
      const body: unknown = await response.json()
      if (body && typeof body === 'object' && 'detail' in body) {
        detail = String((body as { detail: unknown }).detail)
      }
    } catch {
      // body was not JSON; keep statusText
    }
    throw new ApiError(response.status, detail)
  }
  return (await response.json()) as T
}

export const api = {
  fetchConfig: (): Promise<JsonObject> => request('/api/config'),
  saveConfig: (config: JsonObject): Promise<JsonObject> =>
    request('/api/config', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(config),
    }),
  fetchSchema: (): Promise<JsonSchema> => request('/api/schema'),
  fetchStreams: (): Promise<string[]> => request('/api/streams'),
  /** Restarts the process (also picks up code changes). */
  restart: (): Promise<{ status: string }> => request('/api/restart', { method: 'POST' }),
  streamUrl: (name: string): string => `/api/stream/${encodeURIComponent(name)}`,
}
