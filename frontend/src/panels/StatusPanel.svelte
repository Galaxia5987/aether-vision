<!-- Connection/health overview and restart controls. -->
<script lang="ts">
    import { api, type ControlAction } from '../api/api'
    import { connected, status } from '../api/live'

    let pending = $state<ControlAction | null>(null)

    async function run(action: ControlAction): Promise<void> {
        pending = action
        try {
            await api.control(action)
        } catch (error) {
            console.error(error)
        } finally {
            setTimeout(() => (pending = null), 1000)
        }
    }

    function stateClass(state: string | undefined): string {
        if (state === 'streaming' || state === 'running') return 'good'
        if (state === 'error' || state === 'stopped') return 'bad'
        return 'warn'
    }

    function formatUptime(seconds: number): string {
        const s = Math.floor(seconds)
        return `${Math.floor(s / 3600)}h ${Math.floor((s % 3600) / 60)}m ${s % 60}s`
    }
</script>

<section class="status">
    <header>
        <span class="title">Aether Vision</span>
        <span class="dot" class:good={$connected} class:bad={!$connected}></span>
        <span class="muted">{$connected ? 'live' : 'disconnected'}</span>
        {#if $status}<span class="muted">v{$status.version} · up {formatUptime($status.uptime_s)}</span>{/if}
    </header>
    {#if $status}
        <div class="grid">
            <span>Camera</span>
            <span class={stateClass($status.camera.state)}>{$status.camera.state}</span>
            <span class="muted">{$status.camera.source} · {$status.camera.fps.toFixed(1)} fps</span>

            <span>Pipeline</span>
            <span class={stateClass($status.pipeline.state)}>{$status.pipeline.state}</span>
            <span class="muted">{$status.pipeline.name} · {$status.pipeline.fps.toFixed(1)} fps</span>

            <span>NetworkTables</span>
            <span class={$status.network_tables.connected ? 'good' : 'warn'}>
                {$status.network_tables.enabled ? ($status.network_tables.connected ? 'connected' : 'waiting') : 'disabled'}
            </span>
            <span class="muted">{$status.supervised ? 'supervised' : 'unsupervised'}</span>
        </div>
        {#if $status.camera.last_error && $status.camera.state !== 'streaming'}
            <p class="error">Camera: {$status.camera.last_error}</p>
        {/if}
        {#if $status.pipeline.last_error}
            <p class="error">Pipeline: {$status.pipeline.last_error}</p>
        {/if}
        {#if $status.restart_pending}
            <p class="warn-box">Some saved settings take effect after a process restart.</p>
        {/if}
    {/if}
    <div class="buttons">
        <button disabled={pending !== null} onclick={() => run('restart-pipeline')}>Restart pipeline</button>
        <button disabled={pending !== null} onclick={() => run('restart-camera')}>Restart camera</button>
        <button disabled={pending !== null} onclick={() => run('restart-process')} title="Reloads code from disk">
            Restart process
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
    .error,
    .warn-box {
        margin: 0;
        padding: 4px 6px;
        border-radius: 4px;
        font-size: 12px;
    }
    .error {
        background: #2a1616;
        color: #f99;
    }
    .warn-box {
        background: #2a2516;
        color: #ec6;
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
