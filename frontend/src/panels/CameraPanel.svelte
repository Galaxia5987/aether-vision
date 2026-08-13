<script lang="ts">
    import { Pane, PaneGroup, PaneResizer } from "paneforge";
</script>

<Pane defaultSize={50} minSize={20}>

    <PaneGroup direction="vertical" autoSaveId="camera-stack-split">

        <Pane defaultSize={50} minSize={10}>
            <div class="stream-container">
                <img src="http://localhost:8080/stream1" alt="RGB feed" />
            </div>
        </Pane>

        <PaneResizer class="resizer" />

        <Pane defaultSize={50} minSize={10}>
            <div class="stream-container">
                <img src="http://localhost:8080/stream2" alt="Depth feed" />
            </div>
        </Pane>

    </PaneGroup>
</Pane>

<style>
    .stream-container {
        width: 100%;
        height: 100%;
        display: flex;
        justify-content: center;
        align-items: center;
        background-color: #1a1a1a;
    }

    .stream-container img {
        width: 100%;
        height: 100%;
        object-fit: contain;
    }
</style>