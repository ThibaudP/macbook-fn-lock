// Run from Looking Glass: await (await import('file:///.../scripts/reload-in-shell.js')).reload()
// This helper is for local development; it does not change Shell's unsafe-mode setting.
import Gio from 'gi://Gio';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';
import {ExtensionState, ExtensionType} from 'resource:///org/gnome/shell/misc/extensionUtils.js';

export async function reload() {
    const uuid = 'apple-fn-lock@thibaudp.github.io';
    const manager = Main.extensionManager;
    const previous = manager.lookup(uuid);
    const dir = previous?.dir ?? Gio.File.new_for_path(`${global.userdatadir}/extensions/${uuid}`);
    const [, data] = dir.get_child('metadata.json').load_contents(null);
    const metadata = JSON.parse(new TextDecoder().decode(data));

    // A failed enable may already have allocated panel widgets.
    previous?.stateObj?.disable();
    if (previous)
        await manager.unloadExtension(previous);

    const current = manager.createExtensionObject(uuid, dir, ExtensionType.PER_USER);
    const module = await import(`${dir.get_child('extension.js').get_uri()}?reload=${Date.now()}`);
    current.stateObj = new module.default({...metadata, dir, path: dir.get_path()});
    current.isImported = true;
    manager._changeExtensionState(current, ExtensionState.INACTIVE);
    manager.enableExtension(uuid);
    await manager._callExtensionEnable(uuid);
    return current.state === ExtensionState.ACTIVE ? 'MacBook Fn Lock actif' : current.error;
}
