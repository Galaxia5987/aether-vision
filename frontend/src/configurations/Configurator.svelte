<script lang="ts">
    import { Pane, Folder, Slider, Checkbox } from 'svelte-tweakpane-ui';

    // State variables for the vision system
    let exposure = 0.8;
    let threshold = 50;
    let debugMode = false;

    // React to changes in state to send updates to the backend
    $: {
        if (exposure !== undefined) {
            console.log('Update backend with new exposure:', exposure);
        }
    }
</script>


<Pane title="Vision Controller" localStoreId="config">
    <Folder title="Camera Hardware" expanded={true}>
        <Slider bind:value={exposure} min={0} max={1} label="Exposure" />
    </Folder>

    <Folder title="Detection Config">
        <Slider bind:value={threshold} min={0} max={100} step={1} label="Threshold" />
        <Checkbox bind:value={debugMode} label="Debug Mode" />
    </Folder>
</Pane>