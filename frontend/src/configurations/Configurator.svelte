<script lang="ts" module>
    import { Pane, Folder, Text, Button, Slider, Checkbox, List, type ListOptions} from 'svelte-tweakpane-ui';
    import { config as configPkg } from 'utils';
    type AppConfig = configPkg.structs.AppConfig;
    const ConfigClient = configPkg.ConfigClient;

    const inputOptions: ListOptions<string> = {};
    const inputDefaults = configPkg.structs.InputConfig.Companion.getOptions().asJsReadonlyMapView();
    inputDefaults.forEach((value: configPkg.structs.InputConfig, key: string, map: ReadonlyMap<string, configPkg.structs.InputConfig>) => {
        inputOptions[key] = key
    });

    function handleSelectionChange(selection: string) {
        config.input = inputDefaults[selection]
    }

    let inputSelection: string = inputOptions[0]
    $: handleSelectionChange(inputSelection);


    const client = new ConfigClient(window.location.origin);
    let config = configPkg.structs.defaultInstance();
    try {
        config = await client.fetchConfig();
    }catch (e){
        console.error(e)
    }

    async function save(){
        await client.updateConfig(config)
    }
</script>

<Pane title="Configuration" localStoreId="config">
    <Folder title="Input">
        <List bind:value={inputSelection} label="Type" options={inputOptions} />
        {#if config.input instanceof configPkg.structs.UsbCamera}
            <Folder title="Resolution">
                <Slider bind:value={config.input.resolution.width} label="Width"/>
                <Slider bind:value={config.input.resolution.height} label="Height"/>
            </Folder>
            <Folder title="Color Stream">
                <Checkbox bind:value={config.input.colorStream.enabled} label="Enable"/>
            </Folder>
        {:else if config.input instanceof configPkg.structs.RealsenseCamera}
            <Folder title="Resolution">
                <Slider bind:value={config.input.resolution.width} label="Width"/>
                <Slider bind:value={config.input.resolution.height} label="Height"/>
            </Folder>
            <Folder title="Color Stream">
                <Checkbox bind:value={config.input.colorStream.enabled} label="Enable"/>
            </Folder>
            <Folder title="Depth Stream">
                <Checkbox bind:value={config.input.depthStream.enabled} label="Enable"/>
            </Folder>
        {/if}
    </Folder>
    <Folder title="Network Table">
        <Text bind:value={config.networkTable.server} label="Server Address" />
        <Text bind:value={config.networkTable.table} label="Table Path" />
    </Folder>
    <Button on:click={save} title="Save" />
</Pane>