<script lang="ts" module>
    import { Pane, Folder, Text, Button, Slider, Checkbox} from 'svelte-tweakpane-ui';
    import { config as configPkg } from 'utils';
    type AppConfig = configPkg.structs.AppConfig;
    const ConfigClient = configPkg.ConfigClient;

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