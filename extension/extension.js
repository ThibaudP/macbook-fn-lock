import Gio from 'gi://Gio';
import GLib from 'gi://GLib';
import St from 'gi://St';

import {Extension} from 'resource:///org/gnome/shell/extensions/extension.js';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';
import * as PanelMenu from 'resource:///org/gnome/shell/ui/panelMenu.js';
import * as PopupMenu from 'resource:///org/gnome/shell/ui/popupMenu.js';

const NAME = 'org.gnome.Shell.Extensions.AppleFnLock';
const OBJECT_PATH = '/org/gnome/Shell/Extensions/AppleFnLock';

export default class AppleFnLockExtension extends Extension {
    enable() {
        this._cancellable = new Gio.Cancellable();
        this._pending = false;
        this._proxy = null;
        this._button = new PanelMenu.Button(0.0, 'MacBook Fn Lock');
        this._button.style_class = 'panel-button apple-fn-lock-button';
        // Changing the switch should leave the menu open, including with Enter.
        this._button.menu.itemActivated = () => {};
        this._icon = new St.Icon({
            gicon: new Gio.FileIcon({file: this.dir.get_child('fn-key-symbolic.svg')}),
            style_class: 'system-status-icon apple-fn-lock-icon',
        });
        this._button.add_child(this._icon);

        this._switch = new PopupMenu.PopupSwitchMenuItem('Fn Lock', false);
        this._switch.connect('toggled', (_item, locked) => this._setLocked(locked));
        this._button.menu.addMenuItem(this._switch);
        this._mode = new PopupMenu.PopupMenuItem('Mode multimédia', {reactive: false, can_focus: false});
        this._button.menu.addMenuItem(this._mode);
        this._status = new PopupMenu.PopupMenuItem('Connexion au service…', {reactive: false, can_focus: false});
        this._button.menu.addMenuItem(this._status);
        this._button.menu.addMenuItem(new PopupMenu.PopupSeparatorMenuItem());
        this._button.menu.addMenuItem(new PopupMenu.PopupMenuItem('Double appui sur Fn pour changer de mode', {reactive: false, can_focus: false}));
        Main.panel.addToStatusArea(this.uuid, this._button);
        this._sync();

        const [ok, contents] = this.dir.get_child('interface.xml').load_contents(null);
        if (!ok)
            throw new Error('Cannot read Apple Fn Lock D-Bus interface');
        const makeProxyWrapper = Gio.DBusProxy.makeProxyWrapper ?? Gio.DBus.makeProxyWrapper;
        const Proxy = makeProxyWrapper(new TextDecoder().decode(contents));
        const cancellable = this._cancellable;
        this._proxy = new Proxy(Gio.DBus.system, NAME, OBJECT_PATH, (proxy, error) => {
            if (cancellable.is_cancelled())
                return;
            if (error) {
                console.error(`Apple Fn Lock: ${error.message}`);
                this._status.label.text = 'Service inaccessible';
                return;
            }
            this._proxy = proxy;
            this._propertySignal = proxy.connect('g-properties-changed', () => this._sync());
            this._ownerSignal = proxy.connect('notify::g-name-owner', () => this._sync());
            this._sync();
        }, cancellable, Gio.DBusProxyFlags.DO_NOT_AUTO_START);
    }

    _sync() {
        const online = Boolean(this._proxy?.g_name_owner);
        const available = online && Boolean(this._proxy.Available);
        const locked = available && Boolean(this._proxy.Locked);
        this._mode.label.text = locked ? 'Mode F1-F12' : 'Mode multimédia';
        this._mode.visible = available;
        this._switch.setToggleState(locked);
        this._switch.sensitive = available && !this._pending;
        this._status.visible = !available || !this._proxy.KeyboardConnected ||
            this._proxy.Mode === 0 || this._proxy.Mode === 4;
        this._icon.style_class = 'system-status-icon apple-fn-lock-icon' +
            (available ? (locked ? ' apple-fn-lock-enabled' : '') : ' apple-fn-lock-unavailable');
        if (!online)
            this._status.label.text = 'Service Fn Lock arrêté';
        else if (!available)
            this._status.label.text = 'Pilote Apple indisponible';
        else if (!this._proxy.KeyboardConnected)
            this._status.label.text = 'Double appui indisponible : clavier non détecté';
        else if (this._proxy.Mode === 0)
            this._status.label.text = 'Fn désactivée dans le pilote';
        else if (this._proxy.Mode === 4)
            this._status.label.text = 'Touches multimédias uniquement';
        this._button.accessible_name = available
            ? (locked ? 'Fn Lock activé : F1 à F12' : 'Fn Lock désactivé : multimédia')
            : 'Fn Lock indisponible';
    }

    _setLocked(locked) {
        if (!this._proxy?.g_name_owner || !this._proxy.Available || this._pending) {
            this._sync();
            return;
        }
        this._pending = true;
        this._switch.sensitive = false;
        const proxy = this._proxy;
        const cancellable = this._cancellable;
        proxy.call('SetLocked', new GLib.Variant('(b)', [locked]),
            Gio.DBusCallFlags.NONE, 5000, cancellable, (source, result) => {
                try {
                    source.call_finish(result);
                } catch (error) {
                    if (!cancellable.is_cancelled())
                        Main.notify('MacBook Fn Lock', error.message);
                }
                if (cancellable.is_cancelled())
                    return;
                this._pending = false;
                this._sync();
            });
    }

    disable() {
        this._cancellable?.cancel();
        if (this._proxy) {
            if (this._propertySignal)
                this._proxy.disconnect(this._propertySignal);
            if (this._ownerSignal)
                this._proxy.disconnect(this._ownerSignal);
        }
        this._propertySignal = 0;
        this._ownerSignal = 0;
        this._proxy = null;
        this._button?.destroy();
        this._button = null;
        this._switch = null;
        this._mode = null;
        this._status = null;
        this._icon = null;
        this._cancellable = null;
        this._pending = false;
    }
}
