<script lang="ts">
    import { Pane } from "paneforge";
    import Configurator from "../configurations/Configurator.svelte";
    import LogMonitor from "../log/LogMonitor.svelte";
</script>

<Pane defaultSize={50} minSize={20}>
    <div class="empty-panel">
        <p>Dashboard Widgets / Logs Go Here</p>
        <Configurator/>
        <LogMonitor/>
    </div>
</Pane>

<style>
    .empty-panel {
        width: 100%;
        height: 100%;
        background-color: #111;
        color: #555;
        display: flex;
        justify-content: center;
        align-items: center;
    }
</style>