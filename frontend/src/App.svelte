<script lang="ts">
    import { onMount } from 'svelte'
    import { Pane, PaneGroup, PaneResizer } from 'paneforge'
    import { startLive } from './api/live'
    import CameraPanel from './panels/CameraPanel.svelte'
    import ConfigurationPanel from './panels/ConfigurationPanel.svelte'
    import DataPanel from './panels/DataPanel.svelte'

    onMount(startLive)
</script>

<div class="dashboard-container">
    <PaneGroup direction="horizontal" autoSaveId="main-screen-split">
        <ConfigurationPanel />
        <PaneResizer class="resizer" />
        <Pane defaultSize={70} minSize={30}>
            <PaneGroup direction="vertical" autoSaveId="right-split">
                <Pane defaultSize={65} minSize={20}>
                    <CameraPanel />
                </Pane>
                <PaneResizer class="resizer" />
                <Pane defaultSize={35} minSize={10}>
                    <DataPanel />
                </Pane>
            </PaneGroup>
        </Pane>
    </PaneGroup>
</div>

<style>
    .dashboard-container {
        width: 100vw;
        height: 100vh;
        background: #111;
    }

    :global(.resizer) {
        background-color: #333;
        transition: background-color 0.2s ease;
    }

    :global(.resizer[data-direction='horizontal']) {
        width: 6px;
        cursor: col-resize;
    }

    :global(.resizer[data-direction='vertical']) {
        height: 6px;
        cursor: row-resize;
    }

    :global(.resizer:hover),
    :global(.resizer[data-state='dragging']) {
        background-color: #666;
    }
</style>
