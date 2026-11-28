<!-- Configuration editor generated from the backend's JSON schemas. -->
<script lang="ts">
    import { onMount } from 'svelte'
    import { Button, Folder, Pane } from 'svelte-tweakpane-ui'
    import SchemaForm from './SchemaForm.svelte'
    import { api } from '../api/api'
    import type { JsonObject, JsonSchema } from '../api/types'
    import { isObject, labelFor, resolve, type Defs } from './schema'

    let schema = $state.raw<JsonSchema | null>(null)
    let config = $state<JsonObject | null>(null)
    let message = $state('')
    let saving = $state(false)

    const defs: Defs = $derived(schema?.$defs ?? {})
    const sections = $derived(Object.entries(resolve(schema ?? {}, defs).properties ?? {}))

    async function load(): Promise<void> {
        try {
            schema = await api.fetchSchema()
            config = await api.fetchConfig()
            message = ''
        } catch (error) {
            message = `Failed to load: ${String(error)}`
        }
    }

    async function save(): Promise<void> {
        if (!config) return
        saving = true
        try {
            const payload: unknown = $state.snapshot(config as unknown)
            config = await api.saveConfig(payload as JsonObject)
            message = 'Saved'
            setTimeout(() => (message = message === 'Saved' ? '' : message), 2000)
        } catch (error) {
            message = error instanceof Error ? error.message : String(error)
        } finally {
            saving = false
        }
    }

    function section(key: string): JsonObject {
        const current = config?.[key]
        return isObject(current) ? current : {}
    }

    onMount(load)
</script>

<div class="configurator">
    {#if schema && config}
        <Pane position="inline" title="Configuration">
            {#each sections as [key, prop] (key)}
                <Folder title={labelFor(key, prop)} expanded={false}>
                    <SchemaForm schema={prop} {defs} value={section(key)} />
                </Folder>
            {/each}
            <Button title={saving ? 'Saving…' : 'Save'} disabled={saving} on:click={save} />
            <Button title="Reload" on:click={load} />
        </Pane>
        <p class="hint">Changes apply live; network and web settings restart the process.</p>
    {:else}
        <p class="hint">Loading configuration…</p>
    {/if}
    {#if message}
        <pre class="message" class:ok={message === 'Saved'}>{message}</pre>
    {/if}
</div>

<style>
    .configurator {
        display: flex;
        flex-direction: column;
        gap: 6px;
    }
    .hint {
        margin: 0;
        font-size: 12px;
        color: #777;
    }
    .message {
        margin: 0;
        padding: 6px 8px;
        font-size: 12px;
        white-space: pre-wrap;
        color: #ff8080;
        background: #2a1616;
        border-radius: 4px;
    }
    .message.ok {
        color: #8f8;
        background: #142a16;
    }
</style>
