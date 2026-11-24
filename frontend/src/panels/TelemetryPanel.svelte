<!-- Live key/value telemetry with a filter. -->
<script lang="ts">
    import { telemetry } from '../api/live'
    import type { TelemetryValue } from '../api/types'

    let filter = $state('')

    const rows = $derived(
        [...$telemetry.entries()]
            .filter(([key]) => key.toLowerCase().includes(filter.toLowerCase()))
            .sort(([a], [b]) => a.localeCompare(b)),
    )

    function format(value: TelemetryValue): string {
        if (typeof value === 'number') return Number.isInteger(value) ? String(value) : value.toFixed(3)
        if (Array.isArray(value)) return `[${value.map((v) => (typeof v === 'number' ? +v.toFixed(3) : v)).join(', ')}]`
        return String(value)
    }
</script>

<div class="panel">
    <input placeholder="Filter keys…" bind:value={filter} />
    <div class="scroll">
        <table>
            <tbody>
                {#each rows as [key, value] (key)}
                    <tr>
                        <td class="key">{key}</td>
                        <td class="value">{format(value)}</td>
                    </tr>
                {/each}
            </tbody>
        </table>
    </div>
</div>

<style>
    .panel {
        display: flex;
        flex-direction: column;
        height: 100%;
        gap: 6px;
    }
    input {
        background: #1d1d20;
        border: 1px solid #333;
        color: #ddd;
        padding: 4px 6px;
        border-radius: 4px;
    }
    .scroll {
        overflow: auto;
        flex: 1;
    }
    table {
        width: 100%;
        border-collapse: collapse;
        font-family: var(--mono);
        font-size: 12px;
    }
    td {
        padding: 1px 6px;
        border-bottom: 1px solid #222;
    }
    .key {
        color: #9ab;
        white-space: nowrap;
    }
    .value {
        color: #ddd;
        word-break: break-all;
    }
</style>
