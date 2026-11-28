// Helpers for rendering pydantic JSON schemas as forms.

import type { JsonObject, JsonSchema, JsonValue } from '../api/types'

export type Defs = Record<string, JsonSchema>

/** Deep copy of plain JSON data (also works on Svelte state proxies, unlike structuredClone). */
export function cloneJson<T extends JsonValue>(value: T): T {
  return JSON.parse(JSON.stringify(value)) as T
}

export function resolve(schema: JsonSchema, defs: Defs): JsonSchema {
  let current = schema
  for (let depth = 0; current.$ref && depth < 16; depth++) {
    const name = current.$ref.split('/').pop() ?? ''
    current = { ...defs[name], ...withoutRef(current) }
  }
  return current
}

function withoutRef(schema: JsonSchema): JsonSchema {
  const { $ref: _ignored, ...rest } = schema
  return rest
}

export type FieldKind =
  | { kind: 'object'; schema: JsonSchema }
  | { kind: 'union'; discriminator: string; variants: Record<string, JsonSchema> }
  | { kind: 'boolean' }
  | { kind: 'number'; integer: boolean; min?: number; max?: number; nullable: boolean }
  | { kind: 'enum'; options: JsonValue[] }
  | { kind: 'string' }
  | { kind: 'array'; item: 'number' | 'integer' | 'string' }
  | { kind: 'json' }

/** Classify a schema node into the widget that should edit it. */
export function classify(raw: JsonSchema, defs: Defs): FieldKind {
  const schema = resolve(raw, defs)
  const union = schema.oneOf ?? (schema.discriminator ? schema.anyOf : undefined)
  if (union && schema.discriminator) {
    const variants: Record<string, JsonSchema> = {}
    const key = schema.discriminator.propertyName
    for (const option of union) {
      const variant = resolve(option, defs)
      const tag = variant.properties?.[key]?.const ?? variant.properties?.[key]?.default
      if (typeof tag === 'string') variants[tag] = variant
    }
    return { kind: 'union', discriminator: key, variants }
  }
  if (schema.anyOf) {
    const nonNull = schema.anyOf.map((s) => resolve(s, defs)).filter((s) => s.type !== 'null')
    if (nonNull.length === 1) {
      const inner = classify(nonNull[0], defs)
      if (inner.kind === 'number') return { ...inner, nullable: true }
      return inner
    }
    return { kind: 'json' }
  }
  if (schema.enum) return { kind: 'enum', options: schema.enum }
  if (schema.const !== undefined) return { kind: 'enum', options: [schema.const] }
  switch (schema.type) {
    case 'object':
      return schema.properties ? { kind: 'object', schema } : { kind: 'json' }
    case 'boolean':
      return { kind: 'boolean' }
    case 'integer':
    case 'number':
      return {
        kind: 'number',
        integer: schema.type === 'integer',
        min: schema.minimum ?? schema.exclusiveMinimum,
        max: schema.maximum ?? schema.exclusiveMaximum,
        nullable: false,
      }
    case 'string':
      return { kind: 'string' }
    case 'array': {
      const item = schema.items ? resolve(schema.items, defs).type : 'string'
      if (item === 'number' || item === 'integer' || item === 'string') return { kind: 'array', item }
      return { kind: 'json' }
    }
    default:
      return { kind: 'json' }
  }
}

/** Build a complete default value from a schema (pydantic omits default_factory defaults). */
export function defaultsFor(raw: JsonSchema, defs: Defs): JsonValue {
  const schema = resolve(raw, defs)
  if (schema.default !== undefined) return cloneJson(schema.default)
  const field = classify(schema, defs)
  switch (field.kind) {
    case 'object': {
      const out: JsonObject = {}
      for (const [key, prop] of Object.entries(field.schema.properties ?? {})) {
        out[key] = defaultsFor(prop, defs)
      }
      return out
    }
    case 'union': {
      const first = Object.values(field.variants)[0]
      return first ? defaultsFor(first, defs) : null
    }
    case 'boolean':
      return false
    case 'number':
      return field.nullable ? null : (field.min ?? 0)
    case 'enum':
      return field.options[0] ?? null
    case 'string':
      return ''
    case 'array':
      return []
    case 'json':
      return {}
  }
}

export function isObject(value: JsonValue | undefined): value is JsonObject {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

/** Label from the field itself (not a referenced model's title). */
export function labelFor(key: string, schema: JsonSchema): string {
  return schema.$ref ? key.replaceAll('_', ' ') : (schema.title ?? key.replaceAll('_', ' '))
}
