<script lang="ts">
    import { Pane, PaneGroup, PaneResizer } from "paneforge";
    import {onMount} from "svelte";
    import {client} from "../api/api"
    let streams: readonly string[] = [];
    onMount(async () => {
        streams = (await client.fetchStreamBrokers()).asJsReadonlyArrayView();
    })
</script>

<Pane defaultSize={50} minSize={20}>

    <PaneGroup direction="vertical" autoSaveId="camera-stack-split">
        {#if streams.includes("color") }
        <Pane defaultSize={50} minSize={10}>
            <div class="stream-container">
                <img src="/api/stream/color" alt="RGB feed" />
            </div>
        </Pane>
        {/if}

        <PaneResizer class="resizer" />

        {#if streams.includes("depth")}
        <Pane defaultSize={50} minSize={10}>
            <div class="stream-container">
                <img src="/api/stream/depth" alt="Depth feed" />
            </div>
        </Pane>
        {/if}

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