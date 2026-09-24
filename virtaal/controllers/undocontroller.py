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
        # The refresh() scheduled by _schedule_cursor_restore() that
        # hasn't fired yet, if any - see _flush_pending_refresh().
        self._pending_refresh = None

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

    def push_state_change(self, unit, from_state, from_sticky, to_state):
        """Record a deliberate workflow-state pick as its own undo-able
            act - see UnitController.set_current_state()'s own
            from_user branch, the only caller. Pushing straight to
            self.model here (as this used to) skips this same
            sensitivity refresh every other push site already does -
            the menu item (and its Cmd+Z accelerator, which GTK won't
            activate on an insensitive item) stayed disabled until some
            unrelated later push happened to refresh it."""
        self.model.push({
            'kind': 'state',
            'unit': unit,
            'from_state': from_state,
            'from_sticky': from_sticky,
            'to_state': to_state,
        })
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
        redo_info = {
            'action': redo_action,
            'cursorpos': curpos,
            'targetn': undo_info['targetn'],
            'unit': undo_info['unit'],
        }
        for key in ('state_before', 'state_after'):
            if key in undo_info:
                redo_info[key] = undo_info[key]
        return redo_info

    def _perform_undo(self, undo_info, capture_redo=False):
        if undo_info.get('kind') == 'navigate':
            # capture_redo is only true from the real undo path
            # (_on_undo_activated) - undoing this act means going back
            # to where we were before it; redoing it (the other path,
            # _on_redo_activated) means going forward to where it led.
            if capture_redo:
                self._select_unit(undo_info['from_unit'])
                self._restore_navigation_cursor(undo_info)
                return dict(undo_info)
            self._select_unit(undo_info['unit'])
            return None

        if undo_info.get('kind') == 'state':
            self._select_unit(undo_info['unit'])
            if capture_redo:
                self.unit_controller.restore_state(undo_info['from_state'], undo_info['from_sticky'])
                return dict(undo_info)
            # Redoing re-applies the deliberate pick - sticky again.
            self.unit_controller.restore_state(undo_info['to_state'], True)
            return None

        self._select_unit(undo_info['unit'])

        #if 'desc' in undo_info:
        #    logging.debug('Description: %s' % (undo_info['desc']))

        self._disable_unit_signals()
        # Now that _select_unit() above has loaded the right unit - see
        # _snapshot_for_redo()'s own note.
        redo_snapshot = self._snapshot_for_redo(undo_info) if capture_redo else None
        undo_info['action'](undo_info['unit'])
        self._enable_unit_signals()

        if 'state_before' in undo_info and 'state_after' in undo_info:
            # Restore the automatic state correction this edit caused,
            # alongside the text - same undo step, not a separate one.
            restore_to = undo_info['state_before'] if capture_redo else undo_info['state_after']
            self.unit_controller.set_current_state(restore_to)

        # TODO: try to avoid full refresh
        self._schedule_cursor_restore(undo_info['unit'], undo_info['targetn'], undo_info['cursorpos'])
        return redo_snapshot

    def _select_unit(self, unit):
        """Select the given unit in the store view.
            This is to select the unit where the undo-action took place.
            @type  unit: translate.storage.base.TranslationUnit
            @param unit: The unit to select in the store view."""
        self._flush_pending_refresh()
        self.main_controller.select_unit(unit, force=True)

    def _flush_pending_refresh(self):
        """Run a refresh scheduled by _schedule_cursor_restore() right
            now, if it hasn't fired yet, before switching away from the
            unit it belongs to. GLib runs idle callbacks behind whatever
            input events are already queued - a fast enough next
            undo/redo can otherwise switch units before an earlier
            step's deferred refresh() ever runs, silently dropping
            whatever it was meant to commit (in the real app, that's
            where the edited text is actually written back to the
            underlying translation unit - see TextBox.refresh()'s own
            set_text()/'changed' chain). Safe to call unconditionally:
            a no-op once nothing is pending, and idempotent if GLib
            later runs the same callback anyway - its own scheduled-unit
            guard makes the second call a no-op."""
        pending = self._pending_refresh
        if pending is not None:
            pending()

    def _restore_navigation_cursor(self, undo_info):
        """Put the cursor back where undoing a navigate act's own
            from_unit/from_targetn/from_cursorpos says it was, instead
            of wherever _select_unit() just defaulted it to - a no-op
            if the navigate entry has none (an older redo entry from
            before this existed, or its own last-completed-entry
            lookup found nothing to record)."""
        cursorpos = undo_info.get('from_cursorpos')
        targetn = undo_info.get('from_targetn')
        if cursorpos is None or targetn is None:
            return
        self._schedule_cursor_restore(undo_info['from_unit'], targetn, cursorpos)

    def _cursor_for_entry(self, entry, use_redo_cursorpos):
        """(targetn, cursorpos) for the position an undo/redo entry (or
            a recording group's list - its last item is the one whose
            resting position matters) itself records, or None if it's a
            kind with no such position (state/navigate) or an older
            entry that predates one of these fields existing."""
        tail = entry[-1] if isinstance(entry, list) and entry else entry
        if not isinstance(tail, dict) or tail.get('kind'):
            return None
        targetn = tail.get('targetn')
        cursorpos = tail.get('redo_cursorpos', tail.get('cursorpos')) if use_redo_cursorpos else tail.get('cursorpos')
        if targetn is None or cursorpos is None:
            return None
        return targetn, cursorpos

    def _restore_drifted_cursor(self, entry, unit, is_redo):
        """After _needs_navigation_first() has just moved the display to
            an entry's own unit to resolve drift - without consuming the
            entry itself - put the cursor where that unit is actually
            currently sitting, instead of wherever _select_unit() just
            defaulted it to. Undoing arrives at a unit as it now stands
            (that entry's own post-edit resting position); redoing
            arrives at a unit as it was left by the last undo (its
            pre-edit position) - the entry itself hasn't been applied
            yet either way, only navigated towards."""
        cursor = self._cursor_for_entry(entry, use_redo_cursorpos=not is_redo)
        if cursor is None:
            return
        targetn, cursorpos = cursor
        self._schedule_cursor_restore(unit, targetn, cursorpos)

    def _schedule_cursor_restore(self, unit, targetn, cursorpos):
        """Defer landing the cursor at (targetn, cursorpos) until unit is
            actually the one on screen - the caller may have just
            triggered an async unit switch. Tracked via
            self._pending_refresh so _select_unit() can flush it early
            if it's still outstanding when the display moves on again -
            see _flush_pending_refresh()."""
        textbox = self.unit_controller.view.targets[targetn]
        def refresh():
            if self._pending_refresh is refresh:
                self._pending_refresh = None
            if self.unit_controller.current_unit is not unit:
                return
            textbox.refresh_cursor_pos = cursorpos
            self._disable_unit_signals()
            textbox.refresh(update=True)
            self._enable_unit_signals()
        self._pending_refresh = refresh
        GLib.idle_add(refresh)


    # EVENT HANDLERS #
    def _on_store_loaded_closed(self, storecontroller):
        self.model.clear()
        self._update_sensitivity()

    def _needs_navigation_first(self, entry, is_redo):
        """Whether the display must be moved to this (about-to-be-
            applied) entry's own unit before it's safe to pop and apply
            it - i.e. the display has already drifted away from the
            stack's own position via plain navigation, which (by
            design) isn't itself tracked as its own act. Reports this
            once regardless of how many untracked hops happened - there
            was only ever the one entry on top to land on, so resolving
            it always takes exactly one keypress, never a chain of them.

            Not true for a navigate-kind entry being redone: applying
            that one always just moves forward to wherever it goes,
            unconditionally - see the 'navigate' branch in
            _perform_undo()."""
        head = entry[0] if isinstance(entry, list) and entry else entry
        if is_redo and isinstance(head, dict) and head.get('kind') == 'navigate':
            return False
        target_unit = self.model.entry_unit(entry)
        return target_unit is not None and target_unit is not self.unit_controller.current_unit

    @if_enabled
    def _on_undo_activated(self, *args):
        top = self.model.peek()
        if not top:
            return
        if self._needs_navigation_first(top, is_redo=False):
            target_unit = self.model.entry_unit(top)
            self._select_unit(target_unit)
            self._restore_drifted_cursor(top, target_unit, is_redo=False)
            return

        undo_info = self.model.pop()

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
        top = self.model.peek_redo()
        if not top:
            return
        if self._needs_navigation_first(top, is_redo=True):
            target_unit = self.model.entry_unit(top)
            self._select_unit(target_unit)
            self._restore_drifted_cursor(top, target_unit, is_redo=True)
            return

        redo_info = self.model.pop_redo()

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
            # The action just applied still has its own text commit
            # pending via GLib.idle_add() (see _schedule_cursor_restore())
            # - flush it now, or this reads a stale, not-yet-restored
            # target and can silently override a state this same
            # undo/redo step just restored (including an explicit
            # bundled state_before/state_after).
            self._flush_pending_refresh()
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
        if unit.STATE:
            # May get a 'state_after' attached if this specific edit
            # triggers the automatic empty/unreviewed correction - see
            # UnitController._correct_empty_state().
            data['state_before'] = unit._current_state
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
        if unit.STATE:
            data['state_before'] = unit._current_state
        if pan_app.DEBUG:
            data['desc'] = 'ins_text="%s", offset=%d, elem=%s' % (ins_text, offset, repr(elem))
        self.model.push(data)
        self._update_sensitivity()
