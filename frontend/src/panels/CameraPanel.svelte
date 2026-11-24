<!-- MJPEG debug streams; each view picks a stream. -->
<script lang="ts">
    import { onDestroy, onMount } from 'svelte'
    import { api } from '../api/api'
    import { connected } from '../api/live'

    const PREFERRED = ['annotated', 'depth', 'color']
    const STORAGE_KEY = 'aether-vision.views'

    let streams = $state<string[]>([])
    let views = $state<string[]>(loadViews())
    let generation = $state(0) // bumps on reconnect so <img> elements re-request the stream
    let timer: ReturnType<typeof setInterval> | undefined

    function loadViews(): string[] {
        try {
            const raw = localStorage.getItem(STORAGE_KEY)
            const parsed: unknown = raw ? JSON.parse(raw) : null
            if (Array.isArray(parsed) && parsed.every((v) => typeof v === 'string')) return parsed
        } catch {
            // storage unavailable
        }
        return []
    }

    function saveViews(): void {
        try {
            localStorage.setItem(STORAGE_KEY, JSON.stringify(views))
        } catch {
            // storage unavailable
        }
    }

    async function refresh(): Promise<void> {
        try {
            streams = await api.fetchStreams()
        } catch {
            return
        }
        if (views.length === 0 && streams.length > 0) {
            views = PREFERRED.filter((name) => streams.includes(name)).slice(0, 2)
            if (views.length === 0) views = [streams[0]]
        }
    }

    function setView(index: number, name: string): void {
        views[index] = name
        saveViews()
    }

    function addView(): void {
        views.push(streams[0] ?? 'color')
        saveViews()
    }

    function removeView(index: number): void {
        views.splice(index, 1)
        saveViews()
    }

    let wasConnected = false
    const unsubscribe = connected.subscribe((value) => {
        if (value && !wasConnected) {
            generation++
            void refresh()
        }
        wasConnected = value
    })

    onMount(() => {
        void refresh()
        timer = setInterval(refresh, 3000)
    })
    onDestroy(() => {
        clearInterval(timer)
        unsubscribe()
    })
</script>

<div class="camera-panel">
    <div class="views">
        {#each views as view, index (index)}
            <div class="view">
                <div class="view-bar">
                    <select value={view} onchange={(event) => setView(index, event.currentTarget.value)}>
                        {#each streams.includes(view) ? streams : [view, ...streams] as name (name)}
                            <option value={name}>{name}</option>
                        {/each}
                    </select>
                    <button onclick={() => removeView(index)} title="Close view">✕</button>
                </div>
                {#key `${view}-${generation}`}
                    <img src={`${api.streamUrl(view)}?g=${generation}`} alt={view} />
                {/key}
            </div>
        {/each}
    </div>
    <button class="add" onclick={addView}>+ view</button>
</div>

<style>
    .camera-panel {
        position: relative;
        width: 100%;
        height: 100%;
        background: #111;
    }
    .views {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
        gap: 4px;
        height: 100%;
    }
    .view {
        position: relative;
        display: flex;
        flex-direction: column;
        min-height: 0;
        background: #1a1a1a;
    }
    .view-bar {
        position: absolute;
        top: 4px;
        left: 4px;
        display: flex;
        gap: 4px;
        z-index: 1;
    }
    img {
        width: 100%;
        height: 100%;
        object-fit: contain;
        min-height: 0;
    }
    select,
    button {
        background: rgba(20, 20, 24, 0.8);
        color: #ddd;
        border: 1px solid #444;
        border-radius: 4px;
        font-size: 12px;
    }
    .add {
        position: absolute;
        bottom: 6px;
        right: 6px;
        padding: 2px 8px;
        cursor: pointer;
    }
</style>
