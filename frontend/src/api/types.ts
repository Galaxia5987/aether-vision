// Types mirroring the Python backend's JSON payloads.

export type JsonValue = string | number | boolean | null | JsonValue[] | { [key: string]: JsonValue }
export type JsonObject = { [key: string]: JsonValue }

export type TelemetryValue = string | number | boolean

export interface Target {
  class_id: number
  class_name: string
  confidence: number
  box: [number, number, number, number]
  /** Robot frame (WPILib: x forward, y left, z up), meters. */
  position: [number, number, number] | null
  distance_m: number | null
}

export interface PipelineResult {
  latency_ms: number
  targets: Target[]
}

export interface LogEntry {
  seq: number
  timestamp: number
  level: string
  logger: string
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
}

export type LiveMessage =
  | { type: 'telemetry'; values: Record<string, TelemetryValue> }
  | { type: 'result'; data: PipelineResult }
  | { type: 'logs'; entries: LogEntry[] }
