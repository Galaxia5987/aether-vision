<script lang="ts">
    import {Pane, Monitor} from 'svelte-tweakpane-ui';

    let logs = "Logs are currently empty";

    function truncateLog(log: string): string {
        const lines: string[] = log.split("\n");
        return lines.slice(-50).join("\n");
    }

    export function acceptLog(currentLog: string) {
        logs = truncateLog(currentLog);
    }

</script>

<Pane title="Log" localStoreId="log-panel">
    <Monitor
            value={logs}
            multiline={true}
            rows={10}
    />
</Pane>