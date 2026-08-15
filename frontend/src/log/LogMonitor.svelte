<script lang="ts">
    import {Pane, Monitor} from 'svelte-tweakpane-ui';
    import {client} from "../api/api";

    let logs = "Logs are currently empty";

    function truncateLog(log: string): string {
        const lines: string[] = log.split("\n");
        return lines.slice(-50).join("\n");
    }

    export function acceptLog(currentLog: string) {
        logs = truncateLog(currentLog);
    }

    client.subscribeToLogs((msg: string[]) => {
        acceptLog(msg.join("\n"));
    })

</script>

<Pane title="Log" localStoreId="log-panel" maxWidth={innerWidth}>
    <Monitor
            value={logs}
            multiline={true}
            rows={10}
    />
</Pane>