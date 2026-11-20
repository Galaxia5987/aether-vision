<!-- Tabs for results, telemetry and logs. -->
<script lang="ts">
    import LogMonitor from '../log/LogMonitor.svelte'
    import ResultsPanel from './ResultsPanel.svelte'
    import TelemetryPanel from './TelemetryPanel.svelte'

    type Tab = 'results' | 'telemetry' | 'logs'
    const TABS: Tab[] = ['results', 'telemetry', 'logs']
    let active = $state<Tab>('results')
</script>

<div class="data-panel">
    <nav>
        {#each TABS as tab (tab)}
            <button class:active={active === tab} onclick={() => (active = tab)}>{tab}</button>
        {/each}
    </nav>
    <div class="content">
        {#if active === 'results'}
            <ResultsPanel />
        {:else if active === 'telemetry'}
            <TelemetryPanel />
        {:else}
            <LogMonitor />
        {/if}
    </div>
</div>

<style>
    .data-panel {
        display: flex;
        flex-direction: column;
        height: 100%;
        background: #141416;
        box-sizing: border-box;
        padding: 6px 10px 10px;
    }
    nav {
        display: flex;
        gap: 4px;
        margin-bottom: 6px;
    }
    button {
        background: none;
        border: none;
        border-bottom: 2px solid transparent;
        color: #888;
        padding: 4px 8px;
        cursor: pointer;
        text-transform: capitalize;
    }
    button.active {
        color: #eee;
        border-bottom-color: #aa3bff;
    }
    .content {
        flex: 1;
        min-height: 0;
    }
</style>
