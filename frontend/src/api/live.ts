// WebSocket connection to /api/ws with automatic reconnect, exposed as Svelte stores.

import { writable, type Readable } from 'svelte/store'
import type { LiveMessage, LogEntry, PipelineResult, TelemetryValue } from './types'

const MAX_LOG_LINES = 500
const RECONNECT_DELAY_MS = 1000

const connectedStore = writable(false)
const telemetryStore = writable<Map<string, TelemetryValue>>(new Map())
const resultStore = writable<PipelineResult | null>(null)
const logStore = writable<LogEntry[]>([])

export const connected: Readable<boolean> = connectedStore
export const telemetry: Readable<Map<string, TelemetryValue>> = telemetryStore
export const result: Readable<PipelineResult | null> = resultStore
export const logs: Readable<LogEntry[]> = logStore

function handle(message: LiveMessage): void {
  switch (message.type) {
    case 'telemetry':
      telemetryStore.set(new Map(Object.entries(message.values)))
      break
    case 'result':
      resultStore.set(message.data)
      break
    case 'logs':
      logStore.update((current) => {
        const known = current.length ? current[current.length - 1].seq : 0
        const fresh = message.entries.filter((entry) => entry.seq > known)
        return [...current, ...fresh].slice(-MAX_LOG_LINES)
      })
      break
  }
}

let socket: WebSocket | null = null
let started = false

function connect(): void {
  const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws'
  socket = new WebSocket(`${protocol}://${window.location.host}/api/ws`)
  socket.onopen = () => connectedStore.set(true)
  socket.onmessage = (event: MessageEvent<string>) => {
    try {
      handle(JSON.parse(event.data) as LiveMessage)
    } catch (error) {
      console.error('Bad live message', error)
    }
  }
  socket.onclose = () => {
    connectedStore.set(false)
    socket = null
    setTimeout(connect, RECONNECT_DELAY_MS)
  }
  socket.onerror = () => socket?.close()
}

/** Open the live connection once; safe to call from multiple components. */
export function startLive(): void {
  if (started) return
  started = true
  connect()
}
