<script lang="ts">
    import CameraPanel from "./panels/CameraPanel.svelte";
    import { PaneGroup, PaneResizer } from "paneforge";
    import ConfigurationPanel from "./panels/ConfigurationPanel.svelte";
</script>

<div class="dashboard-container">
    <PaneGroup direction="horizontal" autoSaveId="main-screen-split">
        <ConfigurationPanel/>

        <PaneResizer class="resizer" />

        <CameraPanel/>

    </PaneGroup>
</div>
<style>
    .dashboard-container {
        width: 100vw;
        height: 100vh;
    }

    :global(.resizer) {
        background-color: #333;
        transition: background-color 0.2s ease;
    }

    :global(.resizer[data-direction="horizontal"]) {
        width: 6px;
        cursor: col-resize;
    }

    :global(.resizer[data-direction="vertical"]) {
        height: 6px;
        cursor: row-resize;
    }

    :global(.resizer:hover),
    :global(.resizer[data-state="dragging"]) {
        background-color: #666;
    }
</style>