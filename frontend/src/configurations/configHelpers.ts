export function getDropdownOptions(companion: any) {
    const options: Record<string, string> = {};
    const defaults = companion.getOptions().asJsReadonlyMapView();

    defaults.forEach((_: any, key: string) => {
        options[key] = key;
    });

    return { options, defaults };
}

export function handleSelection(selection: string, defaultsMap: any, updateFn: (selected: any) => void) {
    if (!selection) return;

    const selectedValue = defaultsMap.get(selection);
    if (selectedValue) {
        updateFn(selectedValue);
    }
}