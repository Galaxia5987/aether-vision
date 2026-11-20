<!-- Streaming text log with level filtering and auto-scroll. -->
<script lang="ts">
    import { tick } from 'svelte'
    import { logs } from '../api/live'

    const LEVELS = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']

    let minLevel = $state('INFO')
    let follow = $state(true)
    let container: HTMLDivElement | undefined = $state()

    const visible = $derived($logs.filter((entry) => LEVELS.indexOf(entry.level) >= LEVELS.indexOf(minLevel)))

    $effect(() => {
        void visible.length
        if (follow && container) {
            void tick().then(() => container?.scrollTo({ top: container.scrollHeight }))
        }
    })

    function time(timestamp: number): string {
        return new Date(timestamp * 1000).toLocaleTimeString([], { hour12: false })
    }
</script>

<div class="panel">
    <div class="toolbar">
        <select bind:value={minLevel}>
            {#each LEVELS as level (level)}<option value={level}>{level}</option>{/each}
        </select>
        <label><input type="checkbox" bind:checked={follow} /> follow</label>
    </div>
    <div class="lines" bind:this={container}>
        {#each visible as entry (entry.seq)}
            <div class="line {entry.level.toLowerCase()}">
                <span class="time">{time(entry.timestamp)}</span>
                <span class="level">{entry.level}</span>
                <span class="logger">{entry.logger}</span>
                <span class="message">{entry.message}</span>
            </div>
        {/each}
    </div>
</div>

<style>
    .panel {
        display: flex;
        flex-direction: column;
        height: 100%;
        gap: 6px;
    }
    .toolbar {
        display: flex;
        gap: 10px;
        align-items: center;
        font-size: 12px;
        color: #aaa;
    }
    select {
        background: #1d1d20;
        color: #ddd;
        border: 1px solid #333;
    }
    .lines {
        flex: 1;
        overflow: auto;
        font-family: var(--mono);
        font-size: 12px;
        line-height: 1.4;
    }
    .line {
        white-space: pre-wrap;
        color: #ccc;
    }
    .time,
    .logger {
        color: #667;
        margin-right: 6px;
    }
    .level {
        display: inline-block;
        width: 64px;
    }
    .warning .level,
    .warning .message {
        color: #ec6;
    }
    .error .level,
    .error .message,
    .critical .level,
    .critical .message {
        color: #f77;
    }
    .debug .message {
        color: #888;
    }
</style>
