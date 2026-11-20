// REST client for the Aether Vision backend.

import type { JsonObject, SchemaBundle, Status } from './types'

export type ControlAction = 'restart-pipeline' | 'restart-camera' | 'restart-process'

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
  fetchSchema: (): Promise<SchemaBundle> => request('/api/schema'),
  fetchStatus: (): Promise<Status> => request('/api/status'),
  fetchStreams: (): Promise<string[]> => request('/api/streams'),
  control: (action: ControlAction): Promise<{ status: string }> =>
    request(`/api/control/${action}`, { method: 'POST' }),
  streamUrl: (name: string): string => `/api/stream/${encodeURIComponent(name)}`,
}
