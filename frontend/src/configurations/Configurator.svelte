<script lang="ts">
    import { onMount } from 'svelte';
    import { Pane, Folder, Text, Button, Slider, Checkbox, List } from 'svelte-tweakpane-ui';
    import { config as configPkg } from 'utils';
    import { client } from '../api/api';
    import { getDropdownOptions, handleSelection } from './configHelpers';

    let config = configPkg.structs.defaultInstance();
    let inputSelection: string;
    let pipelineSelection: string;

    const { options: inputOptions, defaults: inputDefaults } = getDropdownOptions(configPkg.structs.InputConfig.Companion);
    const { options: pipelineOptions, defaults: pipelineDefaults } = getDropdownOptions(configPkg.structs.pipeline.PipelineConfig.Companion);

    onMount(async () => {
        try {
            config = await client.fetchConfig();
        } catch (e) {
            console.error(e);
        }

        if (config.input instanceof configPkg.structs.UsbCameraConfig) {
            inputSelection = "UsbCamera";
        } else if (config.input instanceof configPkg.structs.RealsenseCameraConfig) {
            inputSelection = "RealsenseCamera";
        }

        if (config.pipeline instanceof configPkg.structs.pipeline.EmptyPipelineConfig) {
            pipelineSelection = "EmptyPipeline";
        }
    });

    let saveTitle = "Save";

    async function save() {
        await client.updateConfig(config);
        saveTitle = "Saved!";
        setTimeout(()=> {
            saveTitle = "Save";
        }, 2000);
    }

    $: handleSelection(inputSelection, inputDefaults, (selected) => { config.input = selected; });
    $: handleSelection(pipelineSelection, pipelineDefaults, (selected) => { config.pipeline = selected; });
</script>

<Pane title="Configuration" localStoreId="config">
    <Folder title="Input">
        <List bind:value={inputSelection} label="Type" options={inputOptions} />
        {#if config.input instanceof configPkg.structs.UsbCameraConfig}
            <Folder title="Resolution">
                <Slider bind:value={config.input.resolution.width} label="Width" />
                <Slider bind:value={config.input.resolution.height} label="Height" />
            </Folder>
            <Folder title="Color Stream">
                <Checkbox bind:value={config.input.colorStream.enabled} label="Enable" />
            </Folder>
        {:else if config.input instanceof configPkg.structs.RealsenseCameraConfig}
            <Folder title="Resolution">
                <Slider bind:value={config.input.resolution.width} label="Width" />
                <Slider bind:value={config.input.resolution.height} label="Height" />
            </Folder>
            <Slider bind:value={config.input.fps} label="FPS"/>
            <Folder title="Color Stream">
                <Checkbox bind:value={config.input.colorStream.enabled} label="Enable" />
            </Folder>
            <Folder title="Depth Stream">
                <Checkbox bind:value={config.input.depthStream.enabled} label="Enable" />
            </Folder>
        {/if}
    </Folder>
    <Folder title="Pipeline">
        <List bind:value={pipelineSelection} label="Type" options={pipelineOptions} />
    </Folder>
    <Folder title="Network Table">
        <Text bind:value={config.networkTable.server} label="Server Address" />
        <Text bind:value={config.networkTable.table} label="Table Path" />
    </Folder>
    <Button on:click={save} title={saveTitle} />
</Pane>