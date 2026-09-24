#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

from gi.repository import Gdk, GLib, Gtk
from translate.storage.placeables import StringElem

from virtaal.common import GObjectWrapper, pan_app
from virtaal.common.platform import platform

from .basecontroller import BaseController


class UndoController(BaseController):
    """Contains "undo" logic."""

    __gtype_name__ = 'UndoController'


    # INITIALIZERS #
    def __init__(self, main_controller):
        """Constructor.
            @type main_controller: virtaal.controllers.MainController"""
        GObjectWrapper.__init__(self)

        self.main_controller = main_controller
        self.main_controller.undo_controller = self
        self.unit_controller = self.main_controller.store_controller.unit_controller

        self.enabled = True
        from virtaal.models.undomodel import UndoModel
        self.model = UndoModel(self)

        self._setup_key_bindings()
        self._connect_undo_signals()
        self._update_sensitivity()

    def _connect_undo_signals(self):
        # First connect to the unit controller
        self.unit_controller.connect('unit-delete-text', self._on_unit_delete_text)
        self.unit_controller.connect('unit-insert-text', self._on_unit_insert_text)
        self.main_controller.store_controller.connect('store-closed', self._on_store_loaded_closed)
        self.main_controller.store_controller.connect('store-loaded', self._on_store_loaded_closed)

        mainview = self.main_controller.view
        mainview.gui.get_object('menu_edit').set_accel_group(self.accel_group)
        self.mnu_undo = mainview.gui.get_object('mnu_undo')
        self.mnu_undo.set_accel_path('<Virtaal>/Edit/Undo')
        self.mnu_undo.connect('activate', self._on_undo_activated)
        self.mnu_redo = mainview.gui.get_object('mnu_redo')
        self.mnu_redo.set_accel_path('<Virtaal>/Edit/Redo')
        self.mnu_redo.connect('activate', self._on_redo_activated)
        mainview.sync_menubar()

    def _setup_key_bindings(self):
        """Setup Gtk+ key bindings (accelerators).
            This method *may* need to be moved into a view object, but if it is,
            it will be the only functionality in such a class. Therefore, it
            is done here. At least for now."""
        Gtk.AccelMap.add_entry("<Virtaal>/Edit/Undo", Gdk.KEY_z, Gdk.ModifierType.CONTROL_MASK)
        if platform.is_mac:
            # GtkosxApplication's Ctrl->Cmd translation (every other
            # accelerator here relies on it) doesn't reach a compound
            # Ctrl+Shift accelerator - it's left showing/firing on the
            # literal Ctrl+Shift+Z instead. Cmd+Shift+Z arrives as
            # META_MASK|MOD2_MASK|SHIFT_MASK; register that directly.
            redo_mods = Gdk.ModifierType.META_MASK | Gdk.ModifierType.MOD2_MASK | Gdk.ModifierType.SHIFT_MASK
        else:
            redo_mods = Gdk.ModifierType.CONTROL_MASK | Gdk.ModifierType.SHIFT_MASK
        Gtk.AccelMap.add_entry("<Virtaal>/Edit/Redo", Gdk.KEY_z, redo_mods)

        self.accel_group = Gtk.AccelGroup()
        # Not connect_by_path() - mnu_undo's own accel_path already fires
        # its 'activate' signal (connected below) once a matching accel
        # group reaches the window; adding this too calls the handler a
        # second time per keypress (caused a double undo).
        #self.accel_group.connect_by_path("<Virtaal>/Edit/Undo", self._on_undo_activated)

        mainview = self.main_controller.view # FIXME: Is this acceptable?
        mainview.add_accel_group(self.accel_group)


    # DECORATORS #
    def if_enabled(method):
        def enabled_method(self, *args, **kwargs):
            if self.enabled:
                return method(self, *args, **kwargs)
        return enabled_method


    # METHODS #
    def disable(self):
        self.enabled = False

    def enable(self):
        self.enabled = True

    def push_current_text(self, textbox):
        """Save the current text in the given (target) text box on the undo stack."""
        current_text = textbox.elem.copy()
        unitview = self.unit_controller.view

        curpos = textbox.get_cursor_position()
        targetn = unitview.targets.index(textbox)
        def undo_set_text(unit):
            textbox.elem.sub = current_text.sub

        data = {
            'action': undo_set_text,
            'cursorpos': curpos,
            'targetn': targetn,
            'unit': unitview.unit
        }
        if pan_app.DEBUG:
            data['desc'] = 'Set target %d text to %s' % (targetn, repr(current_text)),
        self.model.push(data)
        self._update_sensitivity()

    def _update_sensitivity(self):
        has_store = self.main_controller.store_controller.store is not None
        self.mnu_undo.set_sensitive(has_store and self.model.can_undo())
        self.mnu_redo.set_sensitive(has_store and self.model.can_redo())

    def record_stop(self):
        self.model.record_stop()

    def record_start(self):
        self.model.record_start()

    def _disable_unit_signals(self):
        """Disable all signals emitted by the unit view.
            This should always be followed, as soon as possible, by
            C{self._enable_unit_signals()}."""
        self.unit_controller.view.disable_signals()

    def _enable_unit_signals(self):
        """Enable all signals emitted by the unit view.
            This should always follow, as soon as possible, after a call to
            C{self._disable_unit_signals()}."""
        self.unit_controller.view.enable_signals()

    def _snapshot_for_redo(self, undo_info):
        """Capture a target textbox's current state, wrapped the same way
            push_current_text() wraps one, so it can be replayed later by
            _perform_undo() - reused as-is for redo, since "apply this
            stored state" is the same operation in either direction. Must
            be called only once undo_info['unit'] is loaded into the view
            - targets[] is a reused widget, so calling it earlier
            captures the wrong unit's state."""
        textbox = self.unit_controller.view.targets[undo_info['targetn']]
        current_text = textbox.elem.copy()
        # Prefer the position the original edit itself recorded over a
        # live widget read: _select_unit() switching a reused widget to
        # a different unit, or a still-pending deferred refresh() from
        # an earlier chained step, can each make the widget's own
        # cursor position meaningless at this point. Not every push()
        # site records one (push_current_text() can't know it in
        # advance), hence the fallback.
        curpos = undo_info.get('redo_cursorpos')
        if curpos is None:
            curpos = textbox.get_cursor_position()
        def redo_action(unit):
            textbox.elem.sub = current_text.sub
        return {
            'action': redo_action,
            'cursorpos': curpos,
            'targetn': undo_info['targetn'],
            'unit': undo_info['unit'],
        }

    def _perform_undo(self, undo_info, capture_redo=False):
        self._select_unit(undo_info['unit'])

        #if 'desc' in undo_info:
        #    logging.debug('Description: %s' % (undo_info['desc']))

        self._disable_unit_signals()
        # Now that _select_unit() above has loaded the right unit - see
        # _snapshot_for_redo()'s own note.
        redo_snapshot = self._snapshot_for_redo(undo_info) if capture_redo else None
        undo_info['action'](undo_info['unit'])
        self._enable_unit_signals()

        textbox = self.unit_controller.view.targets[undo_info['targetn']]
        # Guard against this deferred refresh() running after a
        # different, reused unit is now loaded into the same textbox.
        scheduled_unit = undo_info['unit']
        def refresh():
            if self.unit_controller.current_unit is not scheduled_unit:
                return
            textbox.refresh_cursor_pos = undo_info['cursorpos']
            # TODO: try to avoid full refresh
            # This runs via idle_add, after _enable_unit_signals() above
            # has already re-enabled everything - textbox.refresh()'s
            # set_text() would otherwise fire the "changed" signal and
            # re-mark the document modified right after undo cleared it.
            self._disable_unit_signals()
            textbox.refresh(update=True)
            self._enable_unit_signals()

        GLib.idle_add(refresh)
        return redo_snapshot

    def _select_unit(self, unit):
        """Select the given unit in the store view.
            This is to select the unit where the undo-action took place.
            @type  unit: translate.storage.base.TranslationUnit
            @param unit: The unit to select in the store view."""
        self.main_controller.select_unit(unit, force=True)


    # EVENT HANDLERS #
    def _on_store_loaded_closed(self, storecontroller):
        self.model.clear()
        self._update_sensitivity()

    @if_enabled
    def _on_undo_activated(self, *args):
        undo_info = self.model.pop()
        if not undo_info:
            return

        undo_list = undo_info if isinstance(undo_info, list) else [undo_info]
        # Snapshot each affected target's current state right as it's
        # undone (inside _perform_undo(), once the right unit is loaded)
        # - the only place the "forward" direction is still recoverable
        # from, since undo_list's own actions only know how to reverse it.
        redo_list = []
        for ui in reversed(undo_list):
            redo_list.insert(0, self._perform_undo(ui, capture_redo=True))

        self.model.push_redo(redo_list if isinstance(undo_info, list) else redo_list[0])

        self._correct_state_after_undo_redo()

    @if_enabled
    def _on_redo_activated(self, *args):
        redo_info = self.model.pop_redo()
        if not redo_info:
            return

        for ri in (redo_info if isinstance(redo_info, list) else [redo_info]):
            self._perform_undo(ri)

        self._correct_state_after_undo_redo()

    def _correct_state_after_undo_redo(self):
        # _modified is otherwise never touched by undo/redo - set it to
        # match whether we're at the last clean (opened/saved) position,
        # in either direction.
        self.main_controller.store_controller.set_modified(not self.model.is_at_clean_position())

        # Undoing a change back to an empty target can leave the unit's
        # workflow state stuck at "Translated" otherwise.
        # _perform_undo() deliberately disables unit signals around the
        # text-reverting action (to avoid re-marking the document
        # modified), so the normal typing-triggered state timer
        # (_unit_modified -> _start_state_timer -> _state_timer_expired)
        # never runs for an undo/redo. Re-run its own EMPTY<->UNREVIEWED
        # check directly - never overrides a deliberate user pick
        # (_state_sticky).
        current_unit = self.unit_controller.current_unit
        if current_unit is not None and current_unit.STATE and not getattr(current_unit, '_state_sticky', False):
            self.unit_controller._correct_empty_state(current_unit)

        # Same reasoning as above, for anything listening for
        # 'unit-done' rather than reading the unit's state directly
        # (e.g. the nav ribbon) - undo/redo settles a unit's state
        # without ever emitting it otherwise.
        if current_unit is not None:
            self.unit_controller.emit('unit-done', current_unit, True)

        self._update_sensitivity()

    @if_enabled
    def _on_unit_delete_text(self, unit_controller, unit, deleted, parent, offset, cursor_pos, elem, target_num):
        def undo_action(unit):
            #logging.debug('(undo) %s.insert(%d, "%s")' % (repr(elem), offset, deleted))
            if parent is None:
                elem.sub = deleted.sub
                return
            if isinstance(deleted, StringElem):
                try:
                    elem.insert(offset, deleted, preferred_parent=parent)
                except TypeError:
                    # the preferred_parent parameter is not in Toolkit 1.9 or
                    # 1.10 with which we otherwise work perfectly. So work with
                    # this just to make it easier for people from checkout.
                    # TODO: remove this when we depend on newer toolkit version
                    elem.insert(offset, deleted)
                elem.prune()

        data = {
            'action': undo_action,
            'cursorpos': cursor_pos,
            # Redoing re-deletes the range - cursor lands where it starts.
            'redo_cursorpos': offset,
            'targetn': target_num,
            'unit': unit,
        }
        if pan_app.DEBUG:
            data['desc'] = 'offset=%d, deleted="%s", parent=%s, cursor_pos=%d, elem=%s' % (offset, repr(deleted), repr(parent), cursor_pos, repr(elem))
        self.model.push(data)
        self._update_sensitivity()

    @if_enabled
    def _on_unit_insert_text(self, unit_controller, unit, ins_text, offset, elem, target_num):
        #logging.debug('_on_unit_insert_text(ins_text="%r", offset=%d, elem=%s, target_n=%d)' % (ins_text, offset, repr(elem), target_num))
        len_ins_text = len(ins_text) # remember, since ins_text might change

        def undo_action(unit):
            if isinstance(ins_text, StringElem) and hasattr(ins_text, 'gui_info') and ins_text.gui_info.widgets:
                # Only for elements with representation widgets
                elem.delete_elem(ins_text)
            else:
                tree_offset = elem.gui_info.gui_to_tree_index(offset)
                #logging.debug('(undo) %s.delete_range(%d, %d)' % (repr(elem), tree_offset, tree_offset+len_ins_text))
                elem.delete_range(tree_offset, tree_offset+len_ins_text)
            elem.prune()

        data = {
            'action': undo_action,
            'unit': unit,
            'targetn': target_num,
            'cursorpos': offset,
            # Redoing re-inserts ins_text - cursor lands right after it.
            'redo_cursorpos': offset + len_ins_text,
        }
        if pan_app.DEBUG:
            data['desc'] = 'ins_text="%s", offset=%d, elem=%s' % (ins_text, offset, repr(elem))
        self.model.push(data)
        self._update_sensitivity()
