<!-- Renders any pydantic JSON schema object as tweakpane controls, editing `value` in place. -->
<script lang="ts">
    import { Checkbox, Folder, List, Slider, Text } from 'svelte-tweakpane-ui'
    import SchemaForm from './SchemaForm.svelte'
    import type { JsonObject, JsonSchema, JsonValue } from '../api/types'
    import { classify, defaultsFor, isObject, labelFor, resolve, type Defs } from './schema'

    let {
        schema,
        defs,
        value,
        omit = [],
    }: { schema: JsonSchema; defs: Defs; value: JsonObject; omit?: string[] } = $props()

    const properties = $derived(
        Object.entries(resolve(schema, defs).properties ?? {}).filter(([key]) => !omit.includes(key)),
    )

    const SLIDER_MAX_RANGE = 10000

    function asObject(key: string): JsonObject {
        const current = value[key]
        if (isObject(current)) return current
        const fresh: JsonObject = {}
        value[key] = fresh
        return value[key] as JsonObject
    }

    function parseList(text: string, item: 'number' | 'integer' | 'string'): JsonValue[] {
        const parts = text.split(',').map((part) => part.trim()).filter((part) => part.length > 0)
        if (item === 'string') return parts
        return parts.map(Number).filter((n) => Number.isFinite(n)).map((n) => (item === 'integer' ? Math.trunc(n) : n))
    }

    function parseJson(text: string, fallback: JsonValue): JsonValue {
        try {
            return JSON.parse(text) as JsonValue
        } catch {
            return fallback
        }
    }

    function selectVariant(key: string, tag: string, variants: Record<string, JsonSchema>): void {
        const variant = variants[tag]
        if (variant) value[key] = defaultsFor(variant, defs)
    }

    function variantTag(key: string, discriminator: string): string {
        const current = value[key]
        return isObject(current) ? String(current[discriminator] ?? '') : ''
    }

    function enumOptions(options: JsonValue[]): Record<string, string | number | boolean> {
        const out: Record<string, string | number | boolean> = {}
        for (const option of options) {
            if (typeof option === 'string' || typeof option === 'number' || typeof option === 'boolean') {
                out[String(option)] = option
            }
        }
        return out
    }
</script>

{#each properties as [key, prop] (key)}
    {@const field = classify(prop, defs)}
    {@const label = labelFor(key, prop)}
    {#if field.kind === 'object'}
        <Folder title={label} expanded={false}>
            <SchemaForm schema={field.schema} {defs} value={asObject(key)} />
        </Folder>
    {:else if field.kind === 'union'}
        {@const tag = variantTag(key, field.discriminator)}
        <Folder title={label} expanded={false}>
            <List
                label={field.discriminator}
                options={Object.keys(field.variants)}
                bind:value={() => tag, (next: string) => selectVariant(key, next, field.variants)}
            />
            {#if field.variants[tag]}
                {#key tag}
                    <SchemaForm
                        schema={field.variants[tag]}
                        {defs}
                        value={asObject(key)}
                        omit={[field.discriminator]}
                    />
                {/key}
            {/if}
        </Folder>
    {:else if field.kind === 'boolean'}
        <Checkbox {label} bind:value={() => value[key] === true, (next: boolean) => (value[key] = next)} />
    {:else if field.kind === 'number' && field.nullable}
        <Text
            {label}
            bind:value={
                () => (value[key] === null || value[key] === undefined ? '' : String(value[key])),
                (next: string) => {
                    const parsed = Number(next)
                    value[key] = next.trim() === '' || !Number.isFinite(parsed) ? null : parsed
                }
            }
        />
    {:else if field.kind === 'number'}
        {@const sliderable =
            field.min !== undefined && field.max !== undefined && field.max - field.min <= SLIDER_MAX_RANGE}
        <Slider
            {label}
            min={sliderable ? field.min : undefined}
            max={sliderable ? field.max : undefined}
            step={field.integer ? 1 : undefined}
            bind:value={
                () => (typeof value[key] === 'number' ? (value[key] as number) : 0),
                (next: number) => (value[key] = field.integer ? Math.round(next) : next)
            }
        />
    {:else if field.kind === 'enum'}
        <List
            {label}
            options={enumOptions(field.options)}
            bind:value={
                () => value[key] as string | number | boolean,
                (next: string | number | boolean) => (value[key] = next)
            }
        />
    {:else if field.kind === 'string'}
        <Text {label} bind:value={() => String(value[key] ?? ''), (next: string) => (value[key] = next)} />
    {:else if field.kind === 'array'}
        <Text
            {label}
            bind:value={
                () => (Array.isArray(value[key]) ? (value[key] as JsonValue[]).join(', ') : ''),
                (next: string) => (value[key] = parseList(next, field.item))
            }
        />
    {:else}
        <Text
            {label}
            bind:value={
                () => JSON.stringify(value[key] ?? null),
                (next: string) => (value[key] = parseJson(next, value[key] ?? null))
            }
        />
    {/if}
{/each}
