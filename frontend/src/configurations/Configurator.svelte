<!-- Configuration editor generated from the backend's JSON schemas. -->
<script lang="ts">
    import { onMount } from 'svelte'
    import { Button, Folder, List, Pane } from 'svelte-tweakpane-ui'
    import SchemaForm from './SchemaForm.svelte'
    import { api } from '../api/api'
    import type { JsonObject, SchemaBundle } from '../api/types'
    import { cloneJson, isObject, labelFor, mergeDefaults, resolve, type Defs } from './schema'

    let schema = $state.raw<SchemaBundle | null>(null)
    let config = $state<JsonObject | null>(null)
    let pipelineName = $state('')
    let pipelineSettings = $state<JsonObject>({})
    let message = $state('')
    let saving = $state(false)

    const appDefs: Defs = $derived(schema?.app.$defs ?? {})
    const sections = $derived(
        Object.entries(resolve(schema?.app ?? {}, appDefs).properties ?? {}).filter(([key]) => key !== 'pipeline'),
    )
    const pipelineInfo = $derived(schema?.pipelines[pipelineName])

    function applyConfig(next: JsonObject): void {
        config = next
        const selection = isObject(next.pipeline) ? next.pipeline : {}
        pipelineName = String(selection.name ?? '')
        const info = schema?.pipelines[pipelineName]
        const settings = isObject(selection.settings) ? selection.settings : {}
        pipelineSettings = info ? (mergeDefaults(info.defaults, settings) as JsonObject) : settings
    }

    async function load(): Promise<void> {
        try {
            schema = await api.fetchSchema()
            applyConfig(await api.fetchConfig())
            message = ''
        } catch (error) {
            message = `Failed to load: ${String(error)}`
        }
    }

    function selectPipeline(name: string): void {
        if (name === pipelineName) return
        pipelineName = name
        const info = schema?.pipelines[name]
        pipelineSettings = info ? cloneJson(info.defaults) : {}
    }

    async function save(): Promise<void> {
        if (!config) return
        saving = true
        try {
            const payload: JsonObject = {
                ...plain(config),
                pipeline: { name: pipelineName, settings: plain(pipelineSettings) },
            }
            applyConfig(await api.saveConfig(payload))
            message = 'Saved'
            setTimeout(() => (message = message === 'Saved' ? '' : message), 2000)
        } catch (error) {
            message = error instanceof Error ? error.message : String(error)
        } finally {
            saving = false
        }
    }

    /** Plain (non-proxied) copy of reactive state, typed explicitly to avoid deep type expansion. */
    function plain(value: JsonObject): JsonObject {
        const copy: unknown = $state.snapshot(value as unknown)
        return copy as JsonObject
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
            <Folder title="Pipeline">
                <List
                    label="pipeline"
                    options={Object.keys(schema.pipelines)}
                    bind:value={() => pipelineName, selectPipeline}
                />
                {#if pipelineInfo}
                    {#key pipelineName}
                        <SchemaForm
                            schema={pipelineInfo.schema}
                            defs={pipelineInfo.schema.$defs ?? {}}
                            value={pipelineSettings}
                        />
                    {/key}
                {/if}
            </Folder>
            {#each sections as [key, prop] (key)}
                <Folder title={labelFor(key, prop)} expanded={false}>
                    <SchemaForm schema={prop} defs={appDefs} value={section(key)} />
                </Folder>
            {/each}
            <Button title={saving ? 'Saving…' : 'Save'} disabled={saving} on:click={save} />
            <Button title="Reload" on:click={load} />
        </Pane>
        <p class="hint">⟳ marks settings that restart the pipeline or process when changed.</p>
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
