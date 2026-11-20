// Types mirroring the Python backend's JSON payloads.

export type JsonValue = string | number | boolean | null | JsonValue[] | { [key: string]: JsonValue }
export type JsonObject = { [key: string]: JsonValue }

export interface ComponentStatus {
  state: string
  fps: number
  last_error: string
}

export interface Status {
  version: string
  uptime_s: number
  supervised: boolean
  restart_pending: boolean
  camera: ComponentStatus & { source: string }
  pipeline: ComponentStatus & { name: string }
  network_tables: { enabled: boolean; connected: boolean }
}

export type TelemetryValue = string | number | boolean | null | (string | number | boolean | null)[]

export interface Target {
  class_id: number
  class_name: string
  confidence: number
  box: [number, number, number, number]
  position_camera: [number, number, number] | null
  position_robot: [number, number, number] | null
  extent_m: [number, number, number] | null
  distance_m: number | null
  point_count: number
}

export interface PipelineResult {
  pipeline: string
  frame_number: number
  latency_ms: number
  targets: Target[]
}

export interface LogEntry {
  seq: number
  timestamp: number
  level: string
  logger: string
  thread: string
  message: string
}

/** Subset of JSON Schema produced by pydantic that the form renderer understands. */
export interface JsonSchema {
  type?: string | string[]
  title?: string
  description?: string
  default?: JsonValue
  enum?: JsonValue[]
  const?: JsonValue
  minimum?: number
  maximum?: number
  exclusiveMinimum?: number
  exclusiveMaximum?: number
  properties?: Record<string, JsonSchema>
  additionalProperties?: boolean | JsonSchema
  items?: JsonSchema
  prefixItems?: JsonSchema[]
  anyOf?: JsonSchema[]
  oneOf?: JsonSchema[]
  discriminator?: { propertyName: string; mapping?: Record<string, string> }
  $ref?: string
  $defs?: Record<string, JsonSchema>
  'x-restart'?: boolean
}

export interface PipelineInfo {
  description: string
  required_streams: string[]
  schema: JsonSchema
  defaults: JsonObject
}

export interface SchemaBundle {
  app: JsonSchema
  pipelines: Record<string, PipelineInfo>
}

export type LiveMessage =
  | { type: 'status'; data: Status }
  | { type: 'telemetry'; full: boolean; values: Record<string, TelemetryValue>; removed: string[] }
  | { type: 'result'; data: PipelineResult }
  | { type: 'logs'; entries: LogEntry[] }
