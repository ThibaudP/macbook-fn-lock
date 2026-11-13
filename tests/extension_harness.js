// Simulate Shell widgets and the proxy, while using real GJS and GLib variants.
const RealGio = imports.gi.Gio;
const GLib = imports.gi.GLib;
const root = ARGV[0];
let checks = 0;
function assert(condition, message) {
    checks++;
    if (!condition)
        throw new Error(message);
}
class Signals {
    constructor() { this.signals = new Map(); this.nextId = 1; }
    connect(name, callback) { const id = this.nextId++; this.signals.set(id, [name, callback]); return id; }
    disconnect(id) { this.signals.delete(id); }
    emit(name, ...args) {
        for (const [signal, callback] of this.signals.values()) {
            if (name === signal) callback(this, ...args);
        }
    }
}
class Widget extends Signals {
    constructor(properties = {}) { super(); Object.assign(this, properties); this.children = []; }
    add_child(child) { this.children.push(child); }
    destroy() { this.destroyed = true; }
}
class Item extends Widget {
    constructor(text) { super(); this.label = {text}; }
}
class Switch extends Item {
    setToggleState(state) { this.state = state; }
}
class Button extends Widget {
    constructor() {
        super();
        this.menu = {items: [], addMenuItem(item) { this.items.push(item); }};
    }
}
const queue = [];
let lastProxy;
class Proxy extends Signals {
    constructor(_bus, _name, _path, callback, cancellable) {
        super(); this.g_name_owner = null;
        lastProxy = this;
        queue.push(() => callback(this, null));
        this.cancellable = cancellable;
    }
    call(method, parameters, _flags, _timeout, _cancel, callback) {
        this.lastCall = [method, parameters.deep_unpack()];
        queue.push(() => callback(this, {}));
    }
    call_finish() { return new GLib.Variant('()', []); }
}
const Gio = {
    Cancellable: RealGio.Cancellable,
    FileIcon: class {},
    DBus: {system: {}},
    DBusProxy: {},
    DBusProxyFlags: {DO_NOT_AUTO_START: 4},
    DBusCallFlags: {NONE: 0},
};
// Preserve the host's real API shape; do not invent a deprecated helper.
const proxyFactoryOwner = typeof RealGio.DBusProxy.makeProxyWrapper === 'function'
    ? 'DBusProxy' : 'DBus';
assert(typeof RealGio[proxyFactoryOwner].makeProxyWrapper === 'function', 'Real GJS proxy factory exists');
Gio[proxyFactoryOwner].makeProxyWrapper = () => Proxy;
const St = {Label: Widget, Icon: Widget, BoxLayout: Widget};
const Clutter = {ActorAlign: {CENTER: 0}};
const Main = {panel: {addToStatusArea() {}}, notify() {}};
const PanelMenu = {Button};
const PopupMenu = {PopupSwitchMenuItem: Switch, PopupMenuItem: Item, PopupSeparatorMenuItem: Item};
class Extension {
    constructor() {
        this.uuid = 'apple-fn-lock@thibaudp.github.io';
        this.dir = {get_child() { return RealGio.File.new_for_path(`${root}/data/interface.xml`); }};
    }
}
const source = RealGio.File.new_for_path(`${root}/extension/extension.js`).load_contents(null)[1];
const body = new TextDecoder().decode(source)
    .replace(/^import .*;\n/gm, '')
    .replace('export default class', 'class');
const ExtensionClass = new Function('Clutter', 'Gio', 'GLib', 'St', 'Extension', 'Main', 'PanelMenu', 'PopupMenu',
    `${body}\nreturn AppleFnLockExtension;`)(Clutter, Gio, GLib, St, Extension, Main, PanelMenu, PopupMenu);

const extension = new ExtensionClass();
extension.enable();
assert(extension._icon.style_class.includes('unavailable'), 'Offline indicator');
assert(extension._button.children.length === 1 && extension._button.children[0] === extension._icon,
    'Panel contains one compact icon');
assert(!extension._switch.sensitive, 'Offline switch disabled');
queue.shift()();
lastProxy.g_name_owner = ':1.10';
lastProxy.Available = true;
lastProxy.KeyboardConnected = true;
lastProxy.Locked = false;
lastProxy.Mode = 3;
lastProxy.emit('g-properties-changed');
assert(extension._icon.style_class === 'system-status-icon apple-fn-lock-icon', 'Media mode uses neutral icon');
assert(extension._switch.sensitive, 'Online switch enabled');
lastProxy.Mode = 2;
lastProxy.Locked = true;
lastProxy.emit('g-properties-changed');
assert(extension._icon.style_class.includes('enabled'), 'Locked icon receives accent color');
assert(extension._switch.state, 'Switch follows external double-tap');
extension._switch.emit('toggled', false);
assert(lastProxy.lastCall[0] === 'SetLocked' && lastProxy.lastCall[1][0] === false, 'Narrow D-Bus write');
assert(!extension._switch.sensitive, 'No concurrent writes while pending');
queue.shift()();
assert(extension._switch.sensitive, 'Switch reenabled after completion');
lastProxy.KeyboardConnected = false;
lastProxy.emit('g-properties-changed');
assert(extension._status.label.text.includes('non détecté'), 'Missing keyboard status');
lastProxy.g_name_owner = null;
lastProxy.emit('notify::g-name-owner');
assert(extension._icon.style_class.includes('unavailable'), 'Service disappearance reflected');
const button = extension._button;
extension.disable();
assert(button.destroyed && lastProxy.signals.size === 0, 'Disable removes widgets and proxy handlers');

// Initialization and write callbacks may finish after extension disable.
extension.enable();
extension.disable();
queue.shift()();
assert(extension._proxy === null, 'Late initialization does not revive disabled extension');
extension.enable();
queue.shift()();
lastProxy.g_name_owner = ':1.11';
lastProxy.Available = true;
lastProxy.Locked = false;
extension._setLocked(true);
extension.disable();
queue.shift()();
assert(extension._button === null, 'Late write completion is harmless');
print(`Extension lifecycle: ${checks} checks passed`);
