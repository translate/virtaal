#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

from .basemodel import BaseModel


class UndoModel(BaseModel):
    """Simple model representing an undo history."""

    # INITIALIZERS #
    def __init__(self, controller):
        self.controller = controller

        super().__init__()
        self.index = -1
        self.recording = False
        self.undo_stack = []
        self.redo_stack = []
        # Undo-stack position at the last "file is unmodified" point
        # (open/save) - see mark_clean()/is_at_clean_position().
        self.clean_index = -1
        # The unit push() last recorded an act for - lets push() detect
        # a navigation between two pushed acts and record it as its own
        # undo-able step. See _maybe_insert_navigation().
        self._last_pushed_unit = None


    # METHODS #
    def can_undo(self):
        return 0 <= self.index < len(self.undo_stack)

    def can_redo(self):
        return bool(self.redo_stack)

    def clear(self):
        """Clear the undo stack and reset the index pointer."""
        self.undo_stack = []
        self.redo_stack = []
        self.index = -1
        self.clean_index = -1
        self._last_pushed_unit = None

    def mark_clean(self):
        """Record the current undo-stack position as "the file is
            unmodified" - call this right after a file is opened or
            saved."""
        self.clean_index = self.index

    def is_at_clean_position(self):
        """Whether the undo stack is currently at the position last marked
            clean by mark_clean() - i.e. whatever's changed since then has
            all been undone."""
        return self.index == self.clean_index

    def pop(self, permanent=False):
        if not self.undo_stack or not (0 <= self.index < len(self.undo_stack)):
            return None

        if not permanent:
            self.index -= 1
            return self.undo_stack[self.index+1]

        # self.index does not necessarily point to the last element in the list, so we have
        # to throw away the rest of the list first.
        self.undo_stack = self.undo_stack[:self.index]
        item = self.undo_stack.pop()
        self.index = len(self.undo_stack) - 1
        return item

    def push(self, undo_dict):
        """Push an undo-action onto the undo stack.
            @type  undo_dict: dict
            @param undo_dict: A dictionary containing undo information with the
                following keys:
                 - "action": Value is a callable that is called (with the "unit"
                   value, to effect the undo).
                 - "unit": Value is the unit on which the undo-action is applicable.
                 - "targetn": The index of the target on which the undo is applicable.
                 - "cursorpos": The position of the cursor after the undo.

            A dict with a "kind" key (e.g. a navigation or state-change
            act) is a different, self-describing family and skips the
            checks above - see UndoController._perform_undo()."""
        if 'kind' not in undo_dict:
            for key in ('action', 'unit', 'targetn', 'cursorpos'):
                if not key in undo_dict:
                    raise ValueError('Invalid undo dictionary!')

        unit = undo_dict['unit']
        if self.recording:
            group = self.undo_stack[-1]
            if not group and self._navigated_to(unit):
                # First push into this group - the navigation entry
                # belongs before the (already-appended) group, not in it.
                self.undo_stack.insert(-1, self._navigation_entry(unit))
            self.undo_stack[-1].append(undo_dict)
        else:
            if self.index < 0:
                self.undo_stack = []
            if self.index != len(self.undo_stack) - 1:
                self.undo_stack = self.undo_stack[:self.index+1]
            self.redo_stack = []
            self._resync_last_pushed_unit()
            if self._navigated_to(unit):
                self.undo_stack.append(self._navigation_entry(unit))
            self.undo_stack.append(undo_dict)
        self.index = len(self.undo_stack) - 1
        self._last_pushed_unit = unit

    def _navigated_to(self, unit):
        return self._last_pushed_unit is not None and unit is not self._last_pushed_unit

    def _resync_last_pushed_unit(self):
        """Recompute _last_pushed_unit from whatever's actually on top of
            the stack now - must run right after truncating it (a fresh
            push/record_start after undoing something discards whatever
            redo history followed). Otherwise a stale value surviving
            from a since-discarded future push can make the very next
            push think it's crossing a unit boundary that, on the
            current stack, doesn't actually lead anywhere - and insert a
            navigation entry for it regardless."""
        self._last_pushed_unit = self.entry_unit(self.undo_stack[-1]) if self.undo_stack else None

    def _navigation_entry(self, unit):
        entry = {'kind': 'navigate', 'unit': unit, 'from_unit': self._last_pushed_unit}
        # Where to put the cursor back on undo - the unit we're leaving
        # has just had its own edit pushed (that's how this navigation
        # got inferred in the first place). Its *redo* cursorpos is the
        # position after that edit - where the user was actually
        # sitting when they navigated away; 'cursorpos' is instead
        # where undoing that one edit lands, one character earlier.
        last = self._last_completed_entry()
        if isinstance(last, dict) and not last.get('kind'):
            entry['from_cursorpos'] = last.get('redo_cursorpos', last['cursorpos'])
            entry['from_targetn'] = last['targetn']
        return entry

    def _last_completed_entry(self):
        """The most recently pushed entry, ignoring the current
            recording group while it's still empty (record_start()
            already appended it before this push() call runs)."""
        stack = self.undo_stack
        if self.recording and stack and isinstance(stack[-1], list) and not stack[-1]:
            stack = stack[:-1]
        if not stack:
            return None
        top = stack[-1]
        return top[-1] if isinstance(top, list) and top else top

    def attach_state_after(self, unit, state_after):
        """Record what an automatic state correction changed a unit's
            state to, onto the text-change entry currently on top of
            the stack for that unit - so undoing the text also
            restores the state that came with it. A no-op unless that
            entry is still exactly where it was pushed (nothing
            undone/redone/pushed since) and opted in via 'state_before'
            (see UndoController._on_unit_insert_text/_delete_text)."""
        if self.index < 0 or self.index != len(self.undo_stack) - 1:
            return
        top = self.undo_stack[-1]
        entry = top[-1] if isinstance(top, list) and top else top
        if not isinstance(entry, dict) or entry.get('kind'):
            return
        if entry.get('unit') is not unit or 'state_before' not in entry:
            return
        entry['state_after'] = state_after

    def record_start(self):
        if self.recording:
            raise Exception('Undo already recording.')

        if self.index < 0:
            self.undo_stack = []
        if self.index != len(self.undo_stack) - 1:
            self.undo_stack = self.undo_stack[:self.index+1]

        self.redo_stack = []
        self._resync_last_pushed_unit()
        self.undo_stack.append([])
        self.index = len(self.undo_stack) - 1
        self.recording = True

    def push_redo(self, redo_dict):
        """Push a redo-action onto the redo stack - see pop().
            @type  redo_dict: dict
            @param redo_dict: Same shape as an undo dictionary passed to
                push(); built by the caller from whatever state undoing
                is about to overwrite."""
        self.redo_stack.append(redo_dict)

    def pop_redo(self):
        """Pop and return the most recently undone action, re-advancing
            C{index} so a following undo lands back on the same entry."""
        if not self.redo_stack:
            return None
        self.index += 1
        return self.redo_stack.pop()

    def record_stop(self):
        if not self.recording:
            raise Exception("Undo can't stop recording if it was not recording in the first place.")

        # In some cases we can get rid of an unnecessary list containing
        # nothing or a single dictionary. That saves 32 bytes on 32 bit python
        # per entry.
        last_entry_len = len(self.undo_stack[-1])
        if last_entry_len == 0:
            # this can happen with something like Ctrl+C
            del self.undo_stack[-1]
        elif last_entry_len == 1:
            self.undo_stack[-1] = self.undo_stack[-1][0]
        self.recording = False
