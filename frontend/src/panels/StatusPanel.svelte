<!-- Connection/health overview and the restart button. -->
<script lang="ts">
    import { api } from '../api/api'
    import { connected, telemetry } from '../api/live'

    let restarting = $state(false)

    async function restart(): Promise<void> {
        restarting = true
        try {
            await api.restart()
        } catch (error) {
            console.error(error)
        } finally {
            setTimeout(() => (restarting = false), 3000)
        }
    }

    function text(key: string): string {
        return String($telemetry.get(key) ?? '—')
    }

    function stateClass(state: string): string {
        if (state === 'streaming' || state === 'running') return 'good'
        if (state.startsWith('error') || state === 'stopped') return 'bad'
        return 'warn'
    }

    const camera = $derived(text('camera/state'))
    const pipeline = $derived(text('pipeline/state'))
    const ntConnected = $derived($telemetry.get('networktables/connected') === true)
</script>

<section class="status">
    <header>
        <span class="title">Aether Vision</span>
        <span class="dot" class:good={$connected} class:bad={!$connected}></span>
        <span class="muted">{$connected ? 'live' : 'disconnected'} · v{text('version')}</span>
    </header>
    <div class="grid">
        <span>Camera</span>
        <span class={stateClass(camera)}>{camera}</span>
        <span class="muted">{text('camera/fps')} fps</span>

        <span>Pipeline</span>
        <span class={stateClass(pipeline)}>{pipeline}</span>
        <span class="muted">{text('pipeline/backend')} · {text('pipeline/fps')} fps</span>

        <span>NetworkTables</span>
        <span class={ntConnected ? 'good' : 'warn'}>{ntConnected ? 'connected' : 'waiting'}</span>
        <span class="muted"></span>
    </div>
    <div class="buttons">
        <button disabled={restarting} onclick={restart} title="Restarts the process; reloads code from disk">
            Restart
        </button>
    </div>
</section>

<style>
    .status {
        display: flex;
        flex-direction: column;
        gap: 8px;
        font-size: 13px;
        color: #bbb;
    }
    header {
        display: flex;
        align-items: center;
        gap: 8px;
    }
    .title {
        font-weight: bold;
        color: #eee;
        font-size: 15px;
    }
    .grid {
        display: grid;
        grid-template-columns: auto auto 1fr;
        gap: 2px 12px;
    }
    .muted {
        color: #777;
    }
    .good {
        color: #6c6;
    }
    .warn {
        color: #db4;
    }
    .bad {
        color: #e66;
    }
    .dot {
        width: 8px;
        height: 8px;
        border-radius: 50%;
        background: #e66;
    }
    .dot.good {
        background: #6c6;
    }
    .buttons {
        display: flex;
        gap: 6px;
        flex-wrap: wrap;
    }
    button {
        background: #2a2a2e;
        color: #ddd;
        border: 1px solid #444;
        border-radius: 4px;
        padding: 4px 10px;
        cursor: pointer;
        font-size: 12px;
    }
    button:hover:not(:disabled) {
        background: #3a3a40;
    }
    button:disabled {
        opacity: 0.5;
        cursor: default;
    }
</style>
