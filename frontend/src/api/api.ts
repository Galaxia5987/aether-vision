import { config as configPkg } from 'utils';
const ConfigClient = configPkg.ConfigClient;

export const client = new ConfigClient(window.location.origin);