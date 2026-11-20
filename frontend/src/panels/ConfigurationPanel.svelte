<script lang="ts">
    import { Pane } from 'paneforge'
    import Configurator from '../configurations/Configurator.svelte'
    import StatusPanel from './StatusPanel.svelte'
</script>

<Pane defaultSize={30} minSize={20}>
    <div class="side">
        <StatusPanel />
        <Configurator />
    </div>
</Pane>

<style>
    .side {
        width: 100%;
        height: 100%;
        overflow-y: auto;
        box-sizing: border-box;
        padding: 10px;
        background-color: #111;
        display: flex;
        flex-direction: column;
        gap: 12px;
    }
</style>
