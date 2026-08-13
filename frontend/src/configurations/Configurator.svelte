<script lang="ts" module>
    import { Pane, Folder, Text, Button } from 'svelte-tweakpane-ui';
    import { config as configPkg } from 'utils';
    type AppConfig = configPkg.structs.AppConfig;
    const ConfigClient = configPkg.ConfigClient;

    const client = new ConfigClient(window.location.origin);
    let config: AppConfig = await client.fetchConfig();

    async function save(){
        await client.updateConfig(config)
    }

</script>

<Pane title="Configuration" localStoreId="config">
    <Folder title="Network Table">
        <Text bind:value={config.networkTable.server} label="Server Address" />
        <Text bind:value={config.networkTable.table} label="Table Path" />
    </Folder>
    <Button on:click={save} title="Save" />
</Pane>