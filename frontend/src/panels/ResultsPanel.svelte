<!-- Latest pipeline result. -->
<script lang="ts">
    import { result } from '../api/live'

    function vec(values: [number, number, number] | null): string {
        return values ? values.map((v) => v.toFixed(2)).join(', ') : '—'
    }
</script>

<div class="panel">
    {#if $result}
        <p class="summary">
            {$result.pipeline} · frame {$result.frame_number} · {$result.latency_ms.toFixed(1)} ms ·
            {$result.targets.length} target(s)
        </p>
        <div class="scroll">
            <table>
                <thead>
                    <tr><th>#</th><th>class</th><th>conf</th><th>robot xyz (m)</th><th>dist (m)</th><th>points</th></tr>
                </thead>
                <tbody>
                    {#each $result.targets as target, index (index)}
                        <tr>
                            <td>{index}</td>
                            <td>{target.class_name}</td>
                            <td>{target.confidence.toFixed(2)}</td>
                            <td>{vec(target.position_robot)}</td>
                            <td>{target.distance_m === null ? '—' : target.distance_m.toFixed(2)}</td>
                            <td>{target.point_count}</td>
                        </tr>
                    {/each}
                </tbody>
            </table>
        </div>
    {:else}
        <p class="summary">No results yet.</p>
    {/if}
</div>

<style>
    .panel {
        display: flex;
        flex-direction: column;
        height: 100%;
    }
    .summary {
        margin: 0 0 6px;
        color: #aaa;
        font-size: 13px;
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
        color: #ddd;
    }
    th {
        text-align: left;
        color: #9ab;
        font-weight: normal;
        border-bottom: 1px solid #333;
        padding: 2px 6px;
    }
    td {
        padding: 1px 6px;
        border-bottom: 1px solid #222;
    }
</style>
