# REMIND: should_reset_target_column should be implemented as state in the view, which is set to
# true until the first time next-line and prev-line are called (assuming we can trap that). That way
# we don't do it after each command but only just before we issue a next/prev line command.

import re, sys
import functools as fu
import sublime, sublime_plugin
from copy import copy


# Handling the different imports in Sublime
if sublime.version() < '3000':
    # we are on ST2 and Python 2.X
    _ST3 = False
    import paragraph
    import sbp_layout as ll
else:
    _ST3 = True
    import Default.paragraph as paragraph
    from . import sbp_layout as ll


JOVE_STATUS = "jove"

default_sbp_sexpr_separators = "./\\()\"'-:,.;<>~!@#$%^&*|+=[]{}`~?";
default_sbp_word_separators = "./\\()\"'-_:,.;<>~!@#$%^&*|+=[]{}`~?";

# ensure_visible commands
ensure_visible_cmds = set(['move', 'move_to'])

# initialized at the end of this file after all commands are defined
kill_cmds = set()

# repeatable commands
repeatable_cmds = set(['move', 'left_delete', 'right_delete', 'undo', 'redo'])

class SettingsManager:
    def get(key, default = None):
        global_settings = sublime.load_settings('sublemacspro.sublime-settings')
        settings  = sublime.active_window().active_view().settings()
        return settings.get(key, global_settings.get(key, default))

#
# Classic emacs kill ring except this supports multiple cursors.
#
class KillRing:
    KILL_RING_SIZE = 64

    class Kill(object):
        """A single kill (maybe with multiple cursors)"""
        def __init__(self, regions):
            self.regions = regions
            self.n_regions = len(regions)

        # Joins a set of regions with our existing set, if possible. We must have
        # the same number of regions.
        def join_if_possible(self, regions, forward):
            if len(regions) != self.n_regions:
                return False
            for i, c in enumerate(regions):
                if forward:
                    self.regions[i] += regions[i]
                else:
                    self.regions[i] = regions[i] + self.regions[i]
            return True

        def set_clipboard(self):
            sublime.set_clipboard(self.regions[0])

        def same_as(self, regions):
            if len(regions) != self.n_regions:
                return False
            for me, him in zip(regions, self.regions):
                if me != him:
                    return False
            return True

    def __init__(self):
        self.entries = [None] * self.KILL_RING_SIZE
        self.index = 0
        self.pop_index = None

    #
    # Add some text to the kill ring. 'forward' indicates whether the editing command that produced
    # this data was in the forward or reverse direction. It only matters if 'join' is true, because
    # it tells us how to add this data to the most recent kill ring entry rather than creating a new
    # entry.
    #
    def add(self, regions, forward, join):
        total_bytes = sum((len(c) for c in regions))

        if total_bytes == 0:
            return
        index = self.index
        try:
            if not join:
                # if the current item is the same as what we're trying to kill, don't bother
                if self.entries[index] and self.entries[index].same_as(regions):
                    return
            else:
                # try to join
                if self.entries[index] and self.entries[index].join_if_possible(regions, forward):
                    return

            # create the new entry
            index = (index + 1) % self.KILL_RING_SIZE
            self.entries[index] = KillRing.Kill(regions)
        finally:
            self.index = index
            self.entries[index].set_clipboard()

    #
    # Returns the current entry in the kill ring for the purposes of yanking. If pop is
    # non-zero, we move backwards or forwards once in the kill ring and return that data
    # instead. We need to match the specified number of regions or else we cannot return
    # anything with a different number of regions nor can we pop the ring in either
    # direction if the number of regions does not match.
    #
    def get_current(self, n_regions, pop):
        entries = self.entries

        clipboard = result = None
        if pop == 0:
            index = self.index
            entry = entries[index]

            # First check to see whether we bring in the clipboard. We do that if the
            # specified number of regions is 1.
            if n_regions == 1:
                # check the clipboard
                clipboard = sublime.get_clipboard()
            if clipboard and (entry is None or entry.n_regions != 1 or entry.regions[0] != clipboard):
                # We switched to another app and cut or copied something there, so add the clipboard
                # to our kill ring.
                result = [clipboard]
                self.add(result, True, False)
            elif entries[index]:
                result = entries[index].regions
            self.pop_index = None
        else:
            if self.pop_index is None:
                self.pop_index = self.index

            incr = -1 if pop > 0 else 1
            index = (self.pop_index + incr) % self.KILL_RING_SIZE
            while entries[index] is None:
                if index == self.pop_index:
                    return None
                index = (index + incr) % self.KILL_RING_SIZE

            # don't do it unless the number of regions matches
            self.pop_index = index
            result = entries[index].regions
            entries[index].set_clipboard()

        # make sure we have enough data for the specified number of regions
        while len(result) < n_regions:
            result *= 2
        return result[0:n_regions]

# kill ring shared across all buffers
kill_ring = KillRing()

#
# Classic emacs mark ring with multi-cursor support. Each entry in the ring is implemented
# with a named view region with an index, so that the marks are adjusted automatically by
# Sublime. The special region called "jove_mark" is used to display the current mark. It's
# a copy of the current mark with gutter display properties turned on.
#
# Each entry is an array of 1 or more regions.
#
class MarkRing:
    MARK_RING_SIZE = 16

    def __init__(self, view):
        self.view = view
        self.index = 0

        # in case any left over from before
        self.view.erase_regions("jove_mark")
        for i in range(self.MARK_RING_SIZE):
            self.view.erase_regions(self.get_key(i))

    def get_key(self, index):
        return "jove_mark:" + str(index)

    def clear(self):
        self.view.erase_regions("jove_mark")

    def has_visible_mark(self):
        return self.view.get_regions("jove_mark") != None and len(self.view.get_regions("jove_mark")) > 0

    #
    # Update the display to show the current mark.
    #
    def display(self):
        # display the mark's dot
        regions = self.get()
        if regions is not None:
            self.view.add_regions("jove_mark", regions, "mark", "dot", sublime.HIDDEN)

    #
    # Get the current mark(s).
    #
    def get(self):
        return self.view.get_regions(self.get_key(self.index))

    #
    # Set the mark to pos. If index is supplied we overwrite that mark, otherwise we push to the
    # next location.
    #
    def set(self, regions, reuse_index=False):
        if self.get() == regions:
            # don't set another mark in the same place
            return
        if not reuse_index:
            self.index = (self.index + 1) % self.MARK_RING_SIZE
        self.view.add_regions(self.get_key(self.index), regions, "mark", "", sublime.HIDDEN)
        self.display()

    #
    # Exchange the current mark with the specified pos, and return the current mark.
    #
    def exchange(self, regions):
        current = self.get()
        if current is not None:
            self.set(regions, True)
            return current

    #
    # Pops the current mark from the ring and returns it. The caller sets point to that value. The
    # new mark is the previous mark on the ring.
    #
    def pop(self):
        regions = self.get()

        # find a non-None mark in the ring
        start = self.index
        while True:
            self.index -= 1
            if self.index < 0:
                self.index = self.MARK_RING_SIZE - 1
            if self.get() or self.index == start:
                break
        self.display()
        return regions

isearch_info = dict()
def isearch_info_for(view):
    if isinstance(view, sublime.Window):
        window = view
    else:
        window = view.window()
    if window:
        return isearch_info.get(window.id(), None)
    return None
def set_isearch_info_for(view, info):
    window = view.window()
    isearch_info[window.id()] = info
    return info
def clear_isearch_info_for(view):
    window = view.window()
    del(isearch_info[window.id()])

#
# We store state about each view.
#
class ViewState():
    # per view state
    view_state_dict = dict()

    # currently active view
    current = None

    def __init__(self, view):
        self.view = view
        self.active_mark = False

        # a mark ring per view (should be per buffer)
        self.mark_ring = MarkRing(view)
        self.reset()

    @classmethod
    def on_view_closed(cls, view):
        if view.id() in cls.view_state_dict:
            del(cls.view_state_dict[view.id()])

    @classmethod
    def get(cls, view):
        # make sure current is set to this view
        if ViewState.current is None or ViewState.current.view != view:
            state = cls.view_state_dict.get(view.id(), None)
            if state is None:
                state = ViewState(view)
                cls.view_state_dict[view.id()] = state
                state.view = view
            ViewState.current = state
        return ViewState.current

    def reset(self):
        self.this_cmd = None
        self.last_cmd = None
        self.argument_supplied = False
        self.argument_value = 0
        self.argument_negative = False
        self.drag_count = 0
        self.entered = 0

    #
    # Get the argument count and reset it for the next command (unless peek is True).
    #
    def get_count(self, peek=False):
        if self.argument_supplied:
            count = self.argument_value
            if self.argument_negative:
                if count == 0:
                    count = -1
                else:
                    count = -count
                if not peek:
                    self.argument_negative = False
            if not peek:
                self.argument_supplied = False
        else:
            count = 1
        return count

    def last_was_kill_cmd(self):
        return self.last_cmd in kill_cmds

class ViewWatcher(sublime_plugin.EventListener):
    def __init__(self, *args, **kwargs):
        super(ViewWatcher, self).__init__(*args, **kwargs)
        self.pending_dedups = 0

    def on_close(self, view):
        ViewState.on_view_closed(view)

    def on_modified(self, view):
        CmdUtil(view).toggle_active_mark_mode(False)

    def on_activated_async(self, view):
        info = isearch_info_for(view)
        if info and not view.settings().get("is_widget"):
            # stop the search if we activated a new view in this window
            info.done()

    def on_query_context(self, view, key, operator, operand, match_all):
        def test(a):
            if operator == sublime.OP_EQUAL:
                return a == operand
            if operator == sublime.OP_NOT_EQUAL:
                return a != operand
            return False

        if key == "i_search_active":
            return test(isearch_info_for(view) is not None)
        if key == "sbp_has_visible_mark":
            if not SettingsManager.get("sbp_cancel_mark_enabled", False):
                return False
            return CmdUtil(view).state.mark_ring.has_visible_mark() == operand
        if key == "sbp_use_alt_bindings":
            return test(SettingsManager.get("sbp_use_alt_bindings"))
        if key == "sbp_use_super_bindings":
            return test(SettingsManager.get("sbp_use_super_bindings"))
        if key == "sbp_alt+digit_inserts":
            return test(SettingsManager.get("sbp_alt+digit_inserts") or not SettingsManager.get("sbp_use_alt_bindings"))
        if key == 'sbp_has_prefix_argument':
            return test(CmdUtil(view).has_prefix_arg())

    def on_post_save(self, view):
        # Schedule a dedup, but do not do it NOW because it seems to cause a crash if, say, we're
        # saving all the buffers right now. So we schedule it for the future.
        self.pending_dedups += 1
        def doit():
            self.pending_dedups -= 1
            if self.pending_dedups == 0:
                dedup_views(sublime.active_window())
        sublime.set_timeout(doit, 50)

class CmdWatcher(sublime_plugin.EventListener):

    def __init__(self, *args, **kwargs):
        super(CmdWatcher, self).__init__(*args, **kwargs)

    def on_anything(self, view):
        view.erase_status(JOVE_STATUS)


    def on_window_command(self, window, cmd, args):
        # Some window commands take us to new view. Here's where we abort the isearch if that happens.
        info = isearch_info_for(window)
        def check():
            if info is not None and window.active_view() != info.view:
                info.done()
        if info is not None:
            sublime.set_timeout(check, 0)

    #
    # Override some commands to execute them N times if the numberic argument is supplied.
    #
    def on_text_command(self, view, cmd, args):
        if isearch_info_for(view) is not None:
            if cmd not in ('sbp_inc_search', 'sbp_inc_search_escape'):
                return ('sbp_inc_search_escape', {'next_cmd': cmd, 'next_args': args})
            return

        vs = ViewState.get(view)
        self.on_anything(view)

        if args is None:
            args = {}


        # first keep track of this_cmd and last_cmd (if command starts with "sbp_" it's handled
        # elsewhere)
        if not cmd.startswith("sbp_"):
            vs.this_cmd = cmd

        #
        #  Process events that create a selection. The hard part is making it work with the emacs region.
        #
        if cmd == 'drag_select':
            info = isearch_info_for(view)
            if info:
                info.done()

            # Set drag_count to 0 when drag_select command occurs. BUT, if the 'by' parameter is
            # present, that means a double or triple click occurred. When that happens we have a
            # selection we want to start using, so we set drag_count to 2. 2 is the number of
            # drag_counts we need in the normal course of events before we turn on the active mark
            # mode.
            vs.drag_count = 2 if 'by' in args else 0

        if cmd in ('move', 'move_to') and vs.active_mark and not args.get('extend', False):
            # this is necessary or else the built-in commands (C-f, C-b) will not move when there is
            # an existing selection
            args['extend'] = True
            return (cmd, args)

        # now check for numeric argument and rewrite some commands as necessary
        if not vs.argument_supplied:
            return None

        if cmd in repeatable_cmds:
            count = vs.get_count()
            args.update({
                'cmd': cmd,
                '_times': abs(count),
            })
            if count < 0 and 'forward' in args:
                args['forward'] = not args['forward']
            return ("sbp_do_times", args)
        elif cmd == 'scroll_lines':
            args['amount'] *= vs.get_count()
            return (cmd, args)

    #
    # Post command processing: deal with active mark and resetting the numeric argument.
    #
    def on_post_text_command(self, view, cmd, args):
        vs = ViewState.get(view)
        cm = CmdUtil(view)
        if vs.active_mark and vs.this_cmd != 'drag_select' and vs.last_cmd == 'drag_select':
            # if we just finished a mouse drag, make sure active mark mode is off
            cm.toggle_active_mark_mode(False)

        # reset numeric argument (if command starts with "sbp_" this is handled elsewhere)
        if not cmd.startswith("sbp_"):
            vs.argument_value = 0
            vs.argument_supplied = False
            vs.last_cmd = cmd

        if vs.active_mark:
            cm.set_cursors(cm.get_regions())

        # if vs.active_mark:
        #     if len(view.sel()) > 1:
        #         # allow the awesomeness of multiple cursors to be used: the selection will disappear
        #         # after the next command
        #         vs.active_mark = False
        #     else:
        #         cm.set_selection(cm.get_mark(), cm.get_point())

        if cmd in ensure_visible_cmds and cm.just_one_cursor():
            cm.ensure_visible(cm.get_last_cursor())

    #
    # Process the selection if it was created from a drag_select (mouse dragging) command.
    #
    def on_selection_modified(self, view):
        vs = ViewState.get(view)
        selection = view.sel()

        if len(selection) == 1 and vs.this_cmd == 'drag_select':
            cm = CmdUtil(view, vs);
            if vs.drag_count == 2:
                # second event - enable active mark
                region = view.sel()[0]
                cm.set_mark([sublime.Region(region.a)], and_selection=False)
                cm.toggle_active_mark_mode(True)
            elif vs.drag_count == 0:
                cm.toggle_active_mark_mode(False)
        vs.drag_count += 1


    #
    # At a minimum this is called when bytes are inserted into the buffer.
    #
    def on_modified(self, view):
        ViewState.get(view).this_cmd = None
        self.on_anything(view)


class WindowCmdWatcher(sublime_plugin.EventListener):

    def __init__(self, *args, **kwargs):
        super(WindowCmdWatcher, self).__init__(*args, **kwargs)


    def on_window_command(self, window, cmd, args):
        # REMIND - JP: Why is this code here? Can't this be done in the SbpPaneCmd class?

        # Check the move state of the Panes and make sure we stop recursion
        if cmd == "sbp_pane_cmd" and args and args['cmd'] == 'move' and 'next_pane' not in args:
            lm = ll.LayoutManager(window.layout())
            if args["direction"] == 'next':
                pos = lm.next(window.active_group())
            else:
                pos = lm.next(window.active_group(), -1)

            args["next_pane"] = pos
            return cmd, args

#
# A helper class which provides a bunch of useful functionality on a view
#
class CmdUtil:
    def __init__(self, view, state=None, edit=None):
        self.view = view
        if state is None:
            state = ViewState.get(self.view)
        self.state = state
        self.edit = edit

    #
    # Sets the status text on the bottom of the window.
    #
    def set_status(self, msg):
        self.view.set_status(JOVE_STATUS, msg)

    #
    # Returns point. Point is where the cursor is in the possibly extended region. If there are multiple cursors it
    # uses the first one in the list.
    #
    def get_point(self):
        sel = self.view.sel()
        if len(sel) > 0:
            return sel[0].b
        return -1

    #
    # This no-op ensures the next/prev line target column is reset to the new locations.
    #
    def reset_target_column(self):
        selection = self.view.sel()
        if len(selection) == 1 and selection[0].empty() and selection[0].b < self.view.size():
            self.run_command("move", {"by": "characters", "forward": True})
            self.run_command("move", {"by": "characters", "forward": False})

    def get_tab_size(self):
        tab_size = self.view.settings().get("tab_size", 8)

    #
    # Returns the mark position.
    #
    def get_mark(self):
        mark = self.view.get_regions("jove_mark")
        if mark:
            mark = mark[0]
            return mark.a

    #
    # Returns true if all the regions are NON-empty.
    #
    def no_empty_regions(self, regions):
        for r in regions:
            if r.empty():
                return False
        return True

    #
    # Returns true if all the regions are empty.
    #
    def all_empty_regions(self, regions):
        for r in regions:
            if not r.empty():
                return False
        return True

    #
    # Get_region() returns the current selection as regions (if the cursors are not
    # empty).  If the cursors are empty but the number of cursors matches the number of
    # marks, and the marks are not overlapping, we return a region for each cursor.
    # Otherwise, we display an error.
    #
    def get_regions(self):
        view = self.view
        cursors = list(view.sel())
        if not self.state.active_mark and self.no_empty_regions(cursors):
            return cursors
        marks = self.view.get_regions("jove_mark")
        if len(marks) == len(cursors):
            regions = [sublime.Region(m.a, c.b) for m, c in zip(marks, cursors)]
            for i, r in enumerate(regions[1:]):
                if r.intersects(regions[i]):
                    self.set_status("Overlapping regions unpredictable outcome!")
            return regions
        self.set_status("Mark/Cursor mismatch: {} marks, {} cursors".format(len(marks), len(cursors)))

    #
    # Save all the current cursors because we're about to do something that could cause
    # them to move around. The only thing that handles that properly is using named
    # regions.
    #
    def save_cursors(self, name):
        cursors = self.get_cursors()
        if cursors:
            cursors = [sublime.Region(c.b) for c in cursors]
            self.view.add_regions(name, cursors, "mark", "", sublime.HIDDEN)

    #
    # Restore the current region to the named saved mark.
    #
    def restore_cursors(self, name):
        cursors = self.view.get_regions(name)
        if cursors:
            self.set_selection(cursors)
        self.view.erase_regions(name)

    #
    # Iterator on all the lines in the specified sublime Region.
    #
    def for_each_line(self, region):
        view = self.view
        pos = region.begin()
        limit = region.end()
        if pos == limit:
            limit += 1
        while pos < limit:
            line = view.line(pos)
            yield line
            pos = line.end() + 1

    #
    # Returns true if all the text between a and b is blank.
    #
    def is_blank(self, a, b):
        text = self.view.substr(sublime.Region(a, b))
        return re.match(r'[ \t]*$', text) is not None

    #
    # Returns the current indent of the line containing the specified POS and the column of POS.
    #
    def get_line_indent(self, pos):
        data,col,region = self.get_line_info(pos)
        m = re.match(r'[ \t]*', data)
        return (len(m.group(0)), col)

    #
    # Sets the buffers mark to the specified pos (or the current position in the view).
    #
    def set_mark(self, regions=None, update_status=True, and_selection=True):
        view = self.view
        mark_ring = self.state.mark_ring
        if regions is None:
            regions = self.get_cursors()

        # update the mark ring
        mark_ring.set(regions)

        if self.state.active_mark:
            # make sure the existing selection disappears and is replaced with an empty selection or
            # selections.
            self.set_cursors(self.get_regions())

        # if and_selection:
        #     self.set_selection(pos)
        if update_status:
            self.set_status("Mark Saved")

    # Allows to always set the active mark mode
    def set_active_mark_mode(self):
        self.set_cursors(self.get_regions())
        self.state.active_mark = True

    #
    # Enabling active mark means highlight the current emacs regions.
    #
    def toggle_active_mark_mode(self, value=None):
        if value is not None and self.state.active_mark == value:
            return

        self.state.active_mark = value if value is not None else (not self.state.active_mark)
        if self.state.active_mark:
            self.set_cursors(self.get_regions())
        else:
            self.make_cursors_empty()

        # elif len(self.view.sel()) <= 1:
        #     self.make_cursors_empty()

    def swap_point_and_mark(self):
        view = self.view
        mark_ring = self.state.mark_ring
        mark = mark_ring.exchange(self.get_cursors())
        if mark is not None:
            # set the cursors to where the mark was
            self.set_cursors(mark)
            if self.state.active_mark:
                # restore the visible region if there was one
                self.set_cursors(self.get_regions())
        else:
            self.set_status("No mark in this buffer")

    def get_cursors(self, begin=False):
        return [sublime.Region(c.a if begin else c.b) if not c.empty() else c for c in self.view.sel()]

    def count_cursors(self):
        return len(self.view.sel())

    def get_last_cursor(self):
        return self.view.sel()[-1]

    def set_cursors(self, regions, ensure_visible=True):
        if not regions:
            # save the caller from having to check - do nothing if the regions are null
            return
        sel = self.view.sel()
        sel.clear()
        sel.add_all(regions)
        if ensure_visible:
            self.ensure_visible(regions[-1])

    def make_cursors_empty(self):
        selection = self.view.sel()
        cursors = [sublime.Region(c.b) for c in selection]
        selection.clear()
        selection.add_all(cursors)

    def set_selection(self, regions):
        if isinstance(regions, sublime.Region):
            regions = [regions]
        selection = self.view.sel()
        selection.clear()
        selection.add_all(regions)

    def get_line_info(self, point):
        view = self.view
        region = view.line(point)
        data = view.substr(region)
        row,col = view.rowcol(point)
        return (data, col, region)

    def run_window_command(self, cmd, args):
        self.view.window().run_command(cmd, args)

    def has_prefix_arg(self):
        return self.state.argument_supplied

    def just_one_cursor(self):
        return len(self.view.sel()) == 1

    def get_count(self, peek=False):
        return self.state.get_count(peek)

    #
    # A helper function that runs the specified callback with args/kwargs on each cursor one after
    # another. It does this one cursor at a time from the end of the buffer towards the front of the
    # buffer in case any edits occur. This tries to watch out for overlapping cursors but that's
    # always problematic anyway.
    #
    def for_each_cursor(self, function, *args, **kwargs):
        view = self.view
        selection = view.sel()
        regions = list(selection)
        selection.clear()

        # REMIND: for delete-white-space and other commands that change the size of the
        # buffer, you need to keep the cursors in a named set of cursors (like the mark
        # ring) so that they are adjusted properly. Also if the function returns None,
        # grab the cursor from the selection.
        can_modify = kwargs.pop('can_modify', False)

        if can_modify:
            key = "tmp_cursors"
            view.add_regions(key, regions, "tmp", "", sublime.HIDDEN)
            for i in range(len(regions)):
                # Grab the region (whose position has been maintained/adjusted by
                # sublime). Unfortunately we need to assume one region might merge into
                # another at any time, and reload all regions to check.
                regions = view.get_regions(key)
                if i >= len(regions):
                    # we've deleted some cursors along the way - we're done
                    break
                selection.add(regions[i])
                cursor = function(regions[i], *args, **kwargs)
                selection.clear()
            cursors = view.get_regions(key)
            view.erase_regions(key)
        else:
            # run the command passing in each cursor and collecting the returned cursor
            cursors = []
            for i,cursor in enumerate(regions):
                selection.add(cursor)
                cursor = function(cursor, *args, **kwargs)
                selection.clear()
                cursors.append(cursor)

        # add them all back when we're done
        selection.add_all(cursors)

    def goto_line(self, line):
        if line >= 0:
            view = self.view
            point = view.text_point(line - 1, 0)
            self.push_mark_and_goto_position(point)

    #
    # Called when we're moving to a new single-cursor location. This pushes the mark onto the mark
    # ring so we can go right back.
    #
    def push_mark_and_goto_position(self, pos):
        if self.get_point() != pos:
            self.set_mark()
        self.set_cursors([sublime.Region(pos)], ensure_visible=True)
        if self.state.active_mark:
            self.set_cursors(self.get_regions())

    def is_visible(self, pos):
        visible = self.view.visible_region()
        return visible.contains(pos)

    def ensure_visible(self, cursor, force=False):
        if force or not self.is_visible(cursor.b):
            self.view.show_at_center(cursor.b)

    def is_word_char(self, pos, forward, separators):
        if not forward:
            if pos == 0:
                return False
            pos -= 1
        char = self.view.substr(pos)
        return not (char in " \t\r\n" or char in separators)

    def is_one_of(self, pos, chars):
        return self.view.substr(pos) in chars

    #
    # Goes to the other end of the scope at the specified position. The specified position should be
    # around brackets or quotes.
    #
    def to_other_end(self, point, direction):
        brac = "([{"
        kets = ")]}"

        view = self.view
        scope_name = view.scope_name(point)
        if scope_name.find("comment") >= 0:
            return None

        ch = view.substr(point)
        if direction > 0 and view.substr(point) in brac:
            return self.run_command("move_to", {"to": "brackets"}, point=point)
        elif direction < 0 and view.substr(point - 1) in kets:
            # this can be tricky due to inconsistencies with sublime bracket matching
            # we need to handle "))" and "()[0]" when between the ) and [
            if point < view.size() and view.substr(point) in brac:
                # go inside the bracket (point - 1), then to the inside of the match, then back one more
                return self.run_command("move_to", {"to": "brackets"}, point=point - 1) - 1
            else:
                return self.run_command("move_to", {"to": "brackets"}, point=point)

        # otherwise it's a string
        start = point + direction
        self.run_command("expand_selection", {"to": "scope"}, point=start)
        r = view.sel()[0]
        return r.end() if direction > 0 else r.begin()

    #
    # Run the specified command and args in the current view. If point is specified set point in the
    # view before running the command. Returns the resulting point.
    #
    def run_command(self, cmd, args, point=None):
        view = self.view
        if point is not None:
            view.sel().clear()
            view.sel().add(sublime.Region(point, point))
        view.run_command(cmd, args)
        return self.get_point()

#
# The baseclass for JOVE/SBP commands. This sets up state, creates a helper, processes the universal
# argument, and then calls the run_cmd method, which subclasses should override.
#
class SbpTextCommand(sublime_plugin.TextCommand):
    should_reset_target_column = False
    is_kill_cmd = False
    is_ensure_visible_cmd = False
    unregistered = False

    def run(self, edit, **kwargs):
        # get our view state
        vs = ViewState.get(self.view)

        # first keep track of this_cmd and last_cmd but only if we're not called recursively
        cmd = self.jove_cmd_name

        if vs.entered == 0 and (cmd != 'sbp_universal_argument' or self.unregistered):
            vs.this_cmd = cmd
        vs.entered += 1
        util = CmdUtil(self.view, state=vs, edit=edit)
        try:
            self.run_cmd(util, **kwargs)
        finally:
            vs.entered -= 1

        if vs.entered == 0 and (cmd != 'sbp_universal_argument' or self.unregistered):
            vs.last_cmd = vs.this_cmd
            vs.argument_value = 0
            vs.argument_supplied = False

            # this no-op ensures the next/prev line target column is reset to the new locations
            if self.should_reset_target_column:
                util.reset_target_column()

class SbpWindowCommand(sublime_plugin.WindowCommand):

    def run(self, **kwargs):
        self.util = CmdUtil(self.window.active_view(), state=ViewState.get(self.window.active_view()))
        self.run_cmd(self.util, **kwargs)

class SbpChainCommand(SbpTextCommand):
    """A command that easily runs a sequence of other commands."""

    def run_cmd(self, util, commands, use_window=False):
        for c in commands:
            if 'window_command' in c:
                util.run_window_command(c['window_command'], c['args'])
            elif 'command' in c:
                util.run_command(c['command'], c['args'])

#
# Calls run command a specified number of times.
#
class SbpDoTimesCommand(SbpTextCommand):
    def run_cmd(self, util, cmd, _times, **args):
        view = self.view
        window = view.window()
        visible = view.visible_region()
        def doit():
            for i in range(_times):
                window.run_command(cmd, args)

        if cmd in ('redo', 'undo'):
            sublime.set_timeout(doit, 10)
        else:
            doit()
            cursor = util.get_last_cursor()
            if not visible.contains(cursor.b):
                util.ensure_visible(cursor, True)

class SbpShowScopeCommand(SbpTextCommand):
    def run_cmd(self, util, direction=1):
        point = util.get_point()
        name = self.view.scope_name(point)
        region = self.view.extract_scope(point)
        status = "%d bytes: %s" % (region.size(), name)
        print(status)
        self.view.set_status(JOVE_STATUS, status)

#
# Advance to the beginning (or end if going backward) word unless already positioned at a word
# character. This can be used as setup for commands like upper/lower/capitalize words. This ignores
# the argument count.
#
class SbpMoveWordCommand(SbpTextCommand):
    should_reset_target_column = True
    is_ensure_visible_cmd = True

    def find_by_class_fallback(self, view, point, forward, classes, seperators):
      if forward:
        delta = 1
        end_position = self.view.size()
        if point > end_position:
          point = end_position
      else:
        delta = -1
        end_position = 0
        if point < end_position:
          point = end_position

      while point != end_position:
        if view.classify(point) & classes != 0:
          return point
        point += delta

      return point

    def find_by_class_native(self, view, point, forward, classes, separators):
        return view.find_by_class(point, forward, classes, separators)

    def run_cmd(self, util, direction=1):
        view = self.view

        separators = SettingsManager.get("sbp_word_separators", default_sbp_word_separators)

        # determine the direction
        count = util.get_count() * direction
        forward = count > 0
        count = abs(count)

        def call_find_by_class(point, classes, separators):
          '''
          This is a small wrapper that maps to the right find_by_class call
          depending on the version of ST installed
          '''
          if _ST3:
            return self.find_by_class_native(view, point, forward, classes, separators)
          else:
            return self.find_by_class_fallback(view, point, forward, classes, separators)

        def move_word0(cursor, first=False):
            point = cursor.b
            if forward:
                if not first or not util.is_word_char(point, True, separators):
                    point = call_find_by_class(point, sublime.CLASS_WORD_START, separators)
                point = call_find_by_class(point, sublime.CLASS_WORD_END, separators)
            else:
                if not first or not util.is_word_char(point, False, separators):
                    point = call_find_by_class(point, sublime.CLASS_WORD_END, separators)
                point = call_find_by_class(point, sublime.CLASS_WORD_START, separators)

            return sublime.Region(point, point)

        for c in range(count):
            util.for_each_cursor(move_word0, first=(c == 0))

#
# Advance to the beginning (or end if going backward) word unless already positioned at a word
# character. This can be used as setup for commands like upper/lower/capitalize words. This ignores
# the argument count.
#
class SbpMoveBackToIndentation(SbpTextCommand):
    should_reset_target_column = True

    def run_cmd(self, util, direction=1):
        view = self.view

        def to_indentation(cursor):
            start = cursor.begin()
            while util.is_one_of(start, " \t"):
                start += 1
            return start

        util.run_command("move_to", {"to": "hardbol", "extend": False})
        util.for_each_cursor(to_indentation)

#
# Advance to the beginning (or end if going backward) word unless already positioned at a word
# character. This can be used as setup for commands like upper/lower/capitalize words. This ignores
# the argument count.
#
class SbpToWordCommand(SbpTextCommand):
    should_reset_target_column = True

    def run_cmd(self, util, direction=1):
        view = self.view

        separators = SettingsManager.get("sbp_word_separators", default_sbp_word_separators)
        forward = direction > 0

        def to_word(cursor):
            point = cursor.b
            if forward:
                if not util.is_word_char(point, True, separators):
                    point = view.find_by_class(point, True, sublime.CLASS_WORD_START, separators)
            else:
                if not util.is_word_char(point, False, separators):
                    point = view.find_by_class(point, False, sublime.CLASS_WORD_END, separators)

            return sublime.Region(point, point)

        util.for_each_cursor(to_word)

class SbpCaseRegion(SbpTextCommand):

    def run_cmd(self, util, mode):
        region = util.get_regions()
        text = util.view.substr(region)
        if mode == "upper":
            text = text.upper()
        elif mode == "lower":
            text = text.lower()
        else:
            util.set_status("Unknown Mode")
            return

        util.view.replace(util.edit, region, text)


class SbpCaseWordCommand(SbpTextCommand):
    should_reset_target_column = True

    def run_cmd(self, util, mode, direction=1):
        # This works first by finding the bounds of the operation by executing a forward-word
        # command. Then it performs the case command.
        view = self.view
        count = util.get_count(True)

        # copy the cursors
        selection = view.sel()
        regions = list(selection)

        # If the regions are all empty, we just move from where we are to where we're going. If
        # there are regions, we use the regions and just do the cap, lower, upper within that
        # region. That's different from Emacs but I think this is better than emacs.
        empty = util.all_empty_regions(regions)

        if empty:
            # run the move-word command so we can create a region
            direction = -1 if count < 0 else 1
            util.run_command("sbp_move_word", {"direction": 1})

            # now the selection is at the "other end" and so we create regions out of all the
            # cursors
            new_regions = []
            for r, s in zip(regions, selection):
                new_regions.append(r.cover(s))
            selection.clear()
            selection.add_all(new_regions)

        # perform the operation
        if mode in ('upper', 'lower'):
            util.run_command(mode + "_case", {})
        else:
            for r in selection:
                util.view.replace(util.edit, r, view.substr(r).title())

        if empty:
            if count < 0:
                # restore cursors to original state if direction was backward
                selection.clear()
                selection.add_all(regions)
            else:
                # otherwise we leave the cursors at the end of the regions
                for r in new_regions:
                    r.a = r.b = r.end()
                selection.clear()
                selection.add_all(new_regions)



class SbpMoveSexprCommand(SbpTextCommand):
    is_ensure_visible_cmd = True
    should_reset_target_column = True

    def run_cmd(self, util, direction=1):
        view = self.view


        separators = SettingsManager.get("sbp_sexpr_separators", default_sbp_sexpr_separators)

        # determine the direction
        count = util.get_count() * direction
        forward = count > 0
        count = abs(count)

        def advance(cursor, first):
            point = cursor.b
            if forward:
                limit = view.size()
                while point < limit:
                    if util.is_word_char(point, True, separators):
                        point = view.find_by_class(point, True, sublime.CLASS_WORD_END, separators)
                        break
                    else:
                        ch = view.substr(point)
                        if ch in "({['\"":
                            next_point = util.to_other_end(point, direction)
                            if next_point is not None:
                                point = next_point
                                break
                        point += 1
            else:
                while point > 0:
                    if util.is_word_char(point, False, separators):
                        point = view.find_by_class(point, False, sublime.CLASS_WORD_START, separators)
                        break
                    else:
                        ch = view.substr(point - 1)
                        if ch in ")}]'\"":
                            next_point = util.to_other_end(point, direction)
                            if next_point is not None:
                                point = next_point
                                break
                        point -= 1

            cursor.a = cursor.b = point
            return cursor

        for c in range(count):
            util.for_each_cursor(advance, (c == 0))

# Move to paragraph depends on the functionality provided by the default
# plugin in ST. So for now we use this.
class SbpMoveToParagraphCommand(SbpTextCommand):

    def run_cmd(self, util, direction=1):
        # Clear all selections
        s = self.view.sel()[0]
        if direction == 1:
            if s.begin() == 0:
                return
            point = paragraph.expand_to_paragraph(self.view, s.begin()-1).begin()
        else:
            if s.end() == self.view.size():
                return
            point = paragraph.expand_to_paragraph(self.view, s.end()+1).end()

        self.view.sel().clear()
        #Clear selections

        if point < 0:
            point = 0

        if point > self.view.size():
            point = self.view.size()

        self.view.sel().add(sublime.Region(point, point))
        self.view.show(self.view.sel()[0].begin())

#
# This command remembers all the current cursor positions, executes a command on all the cursors,
# and then deletes all the data between the two.
#
# If there's only one selection, the deleted data is added to the kill ring appropriately.
#
class SbpMoveThenDeleteCommand(SbpTextCommand):
    is_ensure_visible_cmd = True
    is_kill_cmd = True

    def run_cmd(self, util, move_cmd, **kwargs):
        view = self.view
        selection = view.sel()

        # peek at the count
        count = util.get_count(True)
        if 'direction' in kwargs:
            count *= kwargs['direction']

        # remember the current cursor positions
        orig_cursors = [s for s in selection]
        view.run_command(move_cmd, kwargs)

        # extend each cursor so we can delete the bytes, and only if there is only one region will
        # we add the data to the kill ring
        new_cursors = [s for s in selection]

        selection.clear()
        for old,new in zip(orig_cursors, new_cursors):
            if old < new:
                selection.add(sublime.Region(old.begin(), new.end()))
            else:
                selection.add(sublime.Region(new.begin(), old.end()))

        # check to see if any regions will overlap each other after we perform the kill
        cursors = list(selection)
        regions_overlap = False
        for i, c in enumerate(cursors[1:]):
            if cursors[i].contains(c.begin()):
                regions_overlap = True
                break

        if regions_overlap:
            # restore everything to previous state
            selection.clear()
            selection.add_all(orig_cursors)
            return

        # copy the text into the kill ring
        regions = [view.substr(r) for r in view.sel()]
        kill_ring.add(regions, forward=count > 0, join=util.state.last_was_kill_cmd())

        # erase the regions
        for region in selection:
            view.erase(util.edit, region)


class SbpGotoLineCommand(SbpTextCommand):
    def run_cmd(self, util):
        if util.has_prefix_arg():
            util.goto_line(util.get_count())
        else:
            util.run_window_command("show_overlay", {"overlay": "goto", "text": ":"})

class SbpDeleteWhiteSpaceCommand(SbpTextCommand):
    def run_cmd(self, util):
        util.for_each_cursor(self.delete_white_space, util, can_modify=True)

    def delete_white_space(self, cursor, util, **kwargs):
        view = self.view
        line = view.line(cursor.a)
        data = view.substr(line)
        row,col = view.rowcol(cursor.a)
        start = col
        while start - 1 >= 0 and data[start-1: start] in (" \t"):
            start -= 1
        end = col
        limit = len(data)
        while end + 1 < limit and data[end:end+1] in (" \t"):
            end += 1
        view.erase(util.edit, sublime.Region(line.begin() + start, line.begin() + end))
        return None

class SbpUniversalArgumentCommand(SbpTextCommand):
    def run_cmd(self, util, value):
        state = util.state
        if not state.argument_supplied:
            state.argument_supplied = True
            if value == 'by_four':
                state.argument_value = 4
            elif value == 'negative':
                state.argument_negative = True
            else:
                state.argument_value = value
        elif value == 'by_four':
            state.argument_value *= 4
        elif isinstance(value, int):
            state.argument_value *= 10
            state.argument_value += value
        elif value == 'negative':
            state.argument_value = -state.argument_value

class SbpShiftRegionCommand(SbpTextCommand):
    """Shifts the emacs region left or right."""

    def run_cmd(self, util, direction):
        view = self.view
        state = util.state
        regions = util.get_regions()
        if not regions:
            regions = util.get_cursors()
        if regions:
            util.save_cursors("shift")
            util.toggle_active_mark_mode(False)
            selection = self.view.sel()
            selection.clear()

            # figure out how far we're moving
            if state.argument_supplied:
                cols = direction * util.get_count()
            else:
                cols = direction * util.get_tab_size()

            # now we know which way and how far we're shifting, create a cursor for each line we
            # want to shift
            amount = abs(cols)
            count = 0
            shifted = 0
            for region in regions:
                for line in util.for_each_line(region):
                    count += 1
                    if cols < 0 and (line.size() < amount or not util.is_blank(line.a, line.a + amount)):
                        continue
                    selection.add(sublime.Region(line.a, line.a))
                    shifted += 1

            # shift the region
            if cols > 0:
                # shift right
                self.view.run_command("insert", {"characters": " " * cols})
            else:
                for i in range(amount):
                    self.view.run_command("right_delete")

            # restore the region
            util.restore_cursors("shift")
            sublime.set_timeout(lambda: util.set_status("Shifted %d of %d lines in the region" % (shifted, count)), 100)

# Enum definition
def enum(**enums):
    return type('Enum', (), enums)

SCROLL_TYPES = enum(TOP=1, CENTER=0, BOTTOM=2)

class SbpCenterViewCommand(SbpTextCommand):
    '''
    Reposition the view so that the line containing the cursor is at the
    center of the viewport, if possible. Like the corresponding Emacs
    command, recenter-top-bottom, this command cycles through
    scrolling positions. If the prefix args are used it centers given an offset
    else the cycling command is used

    This command is frequently bound to Ctrl-l.
    '''

    last_sel = None
    last_scroll_type = None
    last_visible_region = None

    def rowdiff(self, start, end):
        r1,c1 = self.view.rowcol(start)
        r2,c2 = self.view.rowcol(end)
        return r2 - r1

    def run_cmd(self, util, center_only=False):
        view = self.view
        point = util.get_point()
        if util.has_prefix_arg():
            lines = util.get_count()
            line_height = view.line_height()
            ignore, point_offy = view.text_to_layout(point)
            offx, ignore = view.viewport_position()
            view.set_viewport_position((offx, point_offy - line_height * lines))
        elif center_only:
            self.view.show_at_center(util.get_point())
        else:
            self.cycle_center_view(view.sel()[0])

    def cycle_center_view(self, start):
        if start != SbpCenterViewCommand.last_sel:
            SbpCenterViewCommand.last_visible_region = None
            SbpCenterViewCommand.last_scroll_type = SCROLL_TYPES.CENTER
            SbpCenterViewCommand.last_sel = start
            self.view.show_at_center(SbpCenterViewCommand.last_sel)
            return
        else:
            SbpCenterViewCommand.last_scroll_type = (SbpCenterViewCommand.last_scroll_type + 1) % 3

        SbpCenterViewCommand.last_sel = start
        if SbpCenterViewCommand.last_visible_region == None:
            SbpCenterViewCommand.last_visible_region = self.view.visible_region()

        # Now Scroll to position
        if SbpCenterViewCommand.last_scroll_type == SCROLL_TYPES.CENTER:
            self.view.show_at_center(SbpCenterViewCommand.last_sel)
        elif SbpCenterViewCommand.last_scroll_type == SCROLL_TYPES.TOP:
            row,col = self.view.rowcol(SbpCenterViewCommand.last_visible_region.end())
            diff = self.rowdiff(SbpCenterViewCommand.last_visible_region.begin(), SbpCenterViewCommand.last_sel.begin())
            self.view.show(self.view.text_point(row + diff-2, 0), False)
        elif SbpCenterViewCommand.last_scroll_type == SCROLL_TYPES.BOTTOM:
            row, col = self.view.rowcol(SbpCenterViewCommand.last_visible_region.begin())
            diff = self.rowdiff(SbpCenterViewCommand.last_sel.begin(), SbpCenterViewCommand.last_visible_region.end())
            self.view.show(self.view.text_point(row - diff+2, 0), False)

class SbpSetMarkCommand(SbpTextCommand):
    def run_cmd(self, util):
        state = util.state
        if state.argument_supplied:
            cursors = state.mark_ring.pop()
            if cursors:
                util.set_cursors(cursors)
            else:
                util.set_status("No mark to pop!")
            state.this_cmd = "sbp_pop_mark"
        elif state.this_cmd == state.last_cmd:
            # at least two set mark commands in a row: turn ON the highlight
            util.toggle_active_mark_mode()
        else:
            # set the mark
            util.set_mark()

        if SettingsManager.get("sbp_active_mark_mode", False):
            util.set_active_mark_mode()

class SbpCancelMarkCommand(SbpTextCommand):
    def run_cmd(self, util):
        if util.state.active_mark:
            util.toggle_active_mark_mode()
        util.state.mark_ring.clear()

class SbpSwapPointAndMarkCommand(SbpTextCommand):
    def run_cmd(self, util):
        if util.state.argument_supplied:
            util.toggle_active_mark_mode()
        else:
            util.swap_point_and_mark()

class SbpMoveToCommand(SbpTextCommand):
    is_ensure_visible_cmd = True
    def run_cmd(self, util, to):
        if to == 'bof':
            util.push_mark_and_goto_position(0)
        elif to == 'eof':
            util.push_mark_and_goto_position(self.view.size())
        elif to in ('eow', 'bow'):
            visible = self.view.visible_region()
            util.set_cursors([sublime.Region(visible.a if to == 'bow' else visible.b)])

class SbpOpenLineCommand(SbpTextCommand):
    def run_cmd(self, util):
        view = self.view
        for point in view.sel():
            view.insert(util.edit, point.b, "\n")
        view.run_command("move", {"by": "characters", "forward": False})

class SbpKillRegionCommand(SbpTextCommand):
    is_kill_cmd = True
    def run_cmd(self, util, is_copy=False):
        view = self.view
        regions = util.get_regions()
        if regions:
            data = [view.substr(r) for r in regions]
            kill_ring.add(data, True, False)
            if not is_copy:
                for r in reversed(regions):
                    view.erase(util.edit, r)
            else:
                bytes = sum(len(d) for d in data)
                util.set_status("Copied %d bytes in %d regions" % (bytes, len(data)))
            util.toggle_active_mark_mode(False)

class SbpPaneCmdCommand(SbpWindowCommand):

    def run_cmd(self, util, cmd, **kwargs):
        if cmd == 'split':
            self.split(self.window, util, **kwargs)
        elif cmd == 'grow':
            self.grow(self.window, util, **kwargs)
        elif cmd == 'destroy':
            self.destroy(self.window, **kwargs)
        elif cmd in ('move', 'switch_tab'):
            self.move(self.window, **kwargs)
        else:
            print("Unknown command")

    #
    # Grow the current selected window group (pane). Amount is usually 1 or -1 for grow and shrink.
    #
    def grow(self, window, util, direction):
        if window.num_groups() == 1:
            return

        # Prepare the layout
        layout = window.layout()
        lm = ll.LayoutManager(layout)
        rows = lm.rows()
        cols = lm.cols()
        cells = layout['cells']

        # calculate the width and height in pixels of all the views
        width = height = dx = dy = 0

        for g,cell in enumerate(cells):
            view = window.active_view_in_group(g)
            w,h = view.viewport_extent()
            width += w
            height += h
            dx += cols[cell[2]] - cols[cell[0]]
            dy += rows[cell[3]] - rows[cell[1]]
        width /= dx
        height /= dy

        current = window.active_group()
        view = util.view

        # Handle vertical moves
        count = util.get_count()
        if direction in ('g', 's'):
            unit = view.line_height() / height
        else:
            unit = view.em_width() / width

        window.set_layout(lm.extend(current, direction, unit, count))

        # make sure point doesn't disappear in any active view - a delay is needed for this to work
        def ensure_visible():
            for g in range(window.num_groups()):
                view = window.active_view_in_group(g)
                util = CmdUtil(view)
                util.ensure_visible(util.get_point())
        sublime.set_timeout(ensure_visible, 50)

    #
    # Split the current pane in half. Clone the current view into the new pane. Refuses to split if
    # the resulting windows would be too small.
    def split(self, window, util, stype):
        layout = window.layout()
        current = window.active_group()
        group_count = window.num_groups()

        view = window.active_view()
        extent = view.viewport_extent()
        if stype == "h" and extent[1] / 2 <= 4 * view.line_height():
            return False

        if stype == "v" and extent[0] / 2 <= 20 * view.em_width():
            return False


        # Perform the layout
        lm = ll.LayoutManager(layout)
        if not lm.split(current, stype):
            return False

        window.set_layout(lm.build())

        # couldn't find an existing view so we have to clone the current one
        window.run_command("clone_file")

        # the cloned view becomes the new active view
        new_view = window.active_view()

        # move the new view into the new group (add the end of the list)
        window.set_view_index(new_view, group_count, 0)

        # make sure the original view is the focus in the original pane
        window.focus_view(view)

        # switch to new pane
        window.focus_group(group_count + 1)

        # after a short delay make sure the two views are looking at the same area
        def setup_views():
            selection = new_view.sel()
            selection.clear()
            selection.add_all([r for r in view.sel()])
            new_view.set_viewport_position(view.viewport_position(), False)

            point = util.get_point()
            new_view.show(point)
            view.show(point)

        sublime.set_timeout(setup_views, 10)
        return True

    #
    # Destroy the specified pane=self|others.
    #
    def destroy(self, window, pane):
        if window.num_groups() == 1:
            return
        view = window.active_view()
        layout = window.layout()

        current = window.active_group()
        lm = ll.LayoutManager(layout)

        if pane == "self":
            views = [window.active_view_in_group(i) for i in range(window.num_groups())]
            del(views[current])
            lm.killSelf(current)
        else:
            lm.killOther(current)
            views = [window.active_view()]

        window.set_layout(lm.build())


        for i in range(window.num_groups()):
            view = views[i]
            window.focus_group(i)
            window.focus_view(view)

        window.focus_group(max(0, current - 1))
        dedup_views(window)


    def move(self, window, **kwargs):
        if 'next_pane' in kwargs:
            window.focus_group(kwargs["next_pane"])
            return

        direction = kwargs['direction']
        if direction in ("prev", "next"):
            direction = 1 if direction == "next" else -1
            current = window.active_group()
            current += direction
            num_groups = window.num_groups()
            if current < 0:
                current = num_groups - 1
            elif current >= num_groups:
                current = 0
            window.focus_group(current)
        else:
            view = window.active_view()
            group,index = window.get_view_index(view)
            views = window.views_in_group(group)
            direction = 1 if direction == "right" else -1
            index += direction
            if index >= len(views):
                index = 0
            elif index < 0:
                index = len(views) - 1
            window.focus_view(views[index])

#
# Exists only to support kill-line with multiple cursors.
#
class SbpMoveForKillLineCommand(SbpTextCommand):
    def run_cmd(self, util, **kwargs):
        view = self.view
        state = util.state

        if state.argument_supplied:
            # we don't support negative arguments for kill-line
            count = abs(util.get_count())
            line_mode = True
        else:
            line_mode = False

        def advance(cursor):
            start = cursor.b
            text,index,region = util.get_line_info(start)

            if line_mode:
                # go down N lines
                for i in range(abs(count)):
                    view.run_command("move", {"by": "lines", "forward": True})

                end = util.get_point()
                if region.contains(end):
                    # same line we started on - must be on the last line of the file
                    end = region.end()
                else:
                    # beginning of the line we ended up on
                    end = view.line(util.get_point()).begin()
                    util.set_cursors(sublime.Region(end))
            else:
                end = region.end()

                # check if line is blank from here to the end and if so, delete the \n as well
                import re
                if re.match(r'[ \t]*$', text[index:]) and end < util.view.size():
                    end += 1

            # ST2 / ST3 compatibility
            return sublime.Region(end,end)

        util.for_each_cursor(advance)

class SbpYankCommand(SbpTextCommand):
    def run_cmd(self, util, pop=0):
        if pop and util.state.last_cmd != 'sbp_yank':
            util.set_status("Previous command was not yank!")
            return

        view = self.view

        # Get the cursors as selection, because if there is a selection we want to replace it with
        # what we're yanking.
        cursors = list(view.sel())
        data = kill_ring.get_current(len(cursors), pop)
        if not data:
            return
        if pop != 0:
            # erase existing regions
            regions = util.get_regions()
            if not regions:
                return
            for r in reversed(regions):
                view.erase(util.edit, r)

            # fetch updated cursors
            cursors = util.get_cursors()

        for region, data in reversed(list(zip(cursors, data))):
            view.replace(util.edit, region, data)
        util.state.mark_ring.set(util.get_cursors(begin=True), True)
        util.make_cursors_empty()
        util.ensure_visible(util.get_last_cursor())

#####################################################
#            Better incremental search              #
#####################################################
class ISearchInfo():
    last_search = None

    class StackItem():
        def __init__(self, search, regions, selected, current_index, forward, wrapped):
            self.prev = None
            self.search = search
            self.regions = regions
            self.selected = selected
            self.current_index = current_index
            self.forward = forward
            self.try_wrapped = False
            self.wrapped = wrapped
            if current_index >= 0 and regions:
                # add the new one to selected
                selected.append(regions[current_index])

        def get_point(self):
            if self.current_index >= 0:
                r = self.regions[self.current_index]
                return r.begin() if self.forward else r.end()
            return None

        def clone(self):
            return copy.copy(self)

        #
        # Clone is called when we want to make progress with the same search string as before.
        #
        def step(self, forward, keep):
            index = self.current_index
            matches = len(self.regions)
            if (self.regions and (index < 0 or (index == 0 and not forward) or (index == matches - 1) and forward)):
                # wrap around!
                index = 0 if forward else matches - 1
                if self.try_wrapped or not self.regions:
                    wrapped = True
                    self.try_wrapped = False
                else:
                    self.try_wrapped = True
                    return None
            elif (forward and index < matches - 1) or (not forward and index > 0):
                index = index + 1 if forward else index - 1
                wrapped = self.wrapped
            else:
                return None
            selected = copy(self.selected)
            if not keep and len(selected) > 0:
                del(selected[-1])
            return ISearchInfo.StackItem(self.search, self.regions, selected, index, forward, wrapped)


    def __init__(self, view, forward, regex):
        self.view = view
        self.current = ISearchInfo.StackItem("", [], [], -1, forward, False)
        self.util = CmdUtil(view)
        self.window = view.window()
        self.point = self.util.get_cursors()
        self.update()
        self.input_view = None
        self.in_changes = 0
        self.forward = forward
        self.regex = regex

    def open(self):
        window = self.view.window()
        self.input_view = window.show_input_panel("%sI-Search:" % ("Regexp " if self.regex else "", ),
                                                  "", self.on_done, self.on_change, self.on_cancel)

    def on_done(self, val):
        # on_done: stop the search, keep the cursors intact
        self.finish(abort=False)

    def on_cancel(self):
        # on_done: stop the search, return cursor to starting point
        self.finish(abort=True)

    def on_change(self, val):
        if self.in_changes > 0:
            # When we pop back to an old state, we have to replace the search string with what was
            # in effect at that state. We do that by deleting all the text and inserting the value
            # of the search string. This causes this on_change method to be called. We want to
            # ignore it, which is what we're doing here.
            self.in_changes -= 1
            return

        if self.current and self.current.search == val:
            # sometimes sublime calls us when nothing has changed
            return

        self.find(val)

    def find(self, val):
        # determine if this is case sensitive search or not
        flags = 0 if self.regex else sublime.LITERAL
        if not re.search(r'[A-Z]', val):
            flags |= sublime.IGNORECASE

        # find all instances if we have a search string
        if len(val) > 0:
            regions = self.view.find_all(val, flags)

            # find the closest match to where we currently are
            pos = None
            if self.current:
                pos = self.current.get_point()
            if pos is None:
                pos = self.point[-1].b
            index = self.find_closest(regions, pos, self.forward)

            # push this new state onto the stack
            self.push(ISearchInfo.StackItem(val, regions, [], index, self.forward, self.current.wrapped))
        else:
            regions = None
            index = -1
        self.update()

    #
    # Implementation and internal API.
    #

    #
    # Push a new state onto the stack.
    #
    def push(self, item):
        item.prev = self.current
        self.current = item

    #
    # Pop one state of the stack and restore everything to the state at that time.
    #
    def pop(self):
        if self.current.prev:
            self.current = self.current.prev
            self.set_text(self.current.search)
            self.forward = self.current.forward
            self.update()
        else:
            print("Nothing to pop so not updating!")

    def hide_panel(self):
        # close the panel which should trigger an on_done
        window = self.view.window()
        if window:
            window.run_command("hide_panel")

    def done(self):
        self.finish()

    #
    # Set the text of the search to a particular value. If is_pop is True it means we're restoring
    # to a previous state. Otherwise, we want to pretend as though this text were actually inserted.
    #
    def set_text(self, text, is_pop=True):
        if is_pop:
            self.in_changes += 1
        self.input_view.run_command("select_all")
        self.input_view.run_command("left_delete")
        self.input_view.run_command("insert", {"characters": text})

    def not_in_error(self):
        si = self.current
        while si and not si.selected and si.search:
            si = si.prev
        return si

    def is_active(self):
        return

    def finish(self, abort=False):
        util = self.util
        if isearch_info_for(self.view) != self:
            return
        if self.current and self.current.search:
            ISearchInfo.last_search = self.current.search
        util.set_status("")

        point_set = False
        if not abort:
            selection = self.view.sel()
            selection.clear()
            current = self.not_in_error()
            if current and current.selected:
                selection.add_all(current.selected)
                point_set = True

        if not point_set:
            # back whence we started
            util.set_cursors(self.point)
        else:
            util.set_mark(self.point, and_selection=False)

        # erase our regions
        self.view.erase_regions("find")
        self.view.erase_regions("selected")
        clear_isearch_info_for(self.view)
        self.hide_panel()

    def update(self):
        si = self.not_in_error()
        if si is None:
            return

        flags = sublime.DRAW_NO_FILL if _ST3 else sublime.DRAW_OUTLINED
        self.view.add_regions("find", si.regions, "text", "", flags)
        selected = si.selected or []
        self.view.add_regions("selected", selected, "string", "", sublime.DRAW_NO_OUTLINE)
        if selected:
            self.view.show(selected[-1])

        status = ""
        if si != self.current:
            status += "Failing "
        if self.current.wrapped:
            status += "Wrapped "
        status += "I-Search " + ("Forward" if self.current.forward else "Reverse")
        if si != self.current:
            if len(self.current.regions) > 0:
                status += " %s matches %s" % (len(self.current.regions), ("above" if self.forward else "below"))
        else:
            status += " %d matches, %d cursors" % (len(si.regions), len(si.selected))

        self.util.set_status(status)

    #
    # Try to make progress with the current search string. Even if we're currently failing (in our
    # current direction) it doesn't mean there aren't matches for what we've typed so far.
    #
    def next(self, keep, forward=None):
        if self.current.prev is None:
            # do something special if we invoke "i-search" twice at the beginning
            if ISearchInfo.last_search:
                # insert the last search string
                self.set_text(ISearchInfo.last_search, is_pop=False)
        else:
            if forward is None:
                forward = self.current.forward
            new = self.current.step(forward=forward, keep=keep)
            if new:
                self.push(new)
                self.update()

    def keep_all(self):
        while self.current.regions and self.current.current_index < len(self.current.regions):
            new = self.current.step(forward=self.current.forward, keep=True)
            if new:
                self.push(new)
            else:
                break
        self.update()

    def append_from_cursor(self):
        # Figure out the contents to the right of the last region in the current selected state, and
        # append characters from there.
        si = self.current
        if len(si.search) > 0 and not si.selected:
            # search is failing - no point in adding from current cursor!
            return

        view = self.view
        limit = view.size()
        if si.selected:
            # grab end of most recent item
            point = si.selected[-1].end()
        else:
            point = self.point[0].b
        if point >= limit:
            return

        # now push new states for each character we append to the search string
        helper = self.util
        search = si.search
        separators = SettingsManager.get("sbp_word_separators", default_sbp_word_separators)
        case_sensitive = re.search(r'[A-Z]', search) is not None

        def append_one(util):
            if not case_sensitive:
                util = util.lower()
            if self.regex and util in "{}()[].*+":
                return "\\" + util
            return util

        if point < limit:
            # append at least one character, word character or not
            search += append_one(view.substr(point))
            point += 1
            self.on_change(search)

            # now insert word characters
            while point < limit and helper.is_word_char(point, True, separators):
                util = view.substr(point)
                search += append_one(util)
                self.on_change(search)
                point += 1
        self.set_text(self.current.search)

    def quit(self):
        close = False

        if self.current.regions:
            # if we have some matched regions, we're in "successful" state and close down the whole
            # thing
            close = True
        else:
            # here the search is currently failing, so we back up until the last non-failing state
            while self.current.prev and not self.current.prev.regions:
                self.current = self.current.prev
            if self.current.prev is None:
                close = True
        if close:
            self.finish(abort=True)
        else:
            self.pop()

    def find_closest(self, regions, pos, forward):
        #
        # The regions are sorted so clearly this would benefit from a simple binary search ...
        #
        if len(regions) == 0:
            return -1
        # find the first region after the specified pos
        found = False
        if forward:
            for index,r in enumerate(regions):
                if r.end() >= pos:
                    return index
            return -1
        else:
            for index,r in enumerate(regions):
                if r.begin() > pos:
                    return index - 1
            return len(regions) - 1

class SbpIncSearchCommand(SbpTextCommand):
    def run_cmd(self, util, cmd=None, **kwargs):
        info = isearch_info_for(self.view)
        if info is None or cmd is None:
            regex = kwargs.get('regex', False)
            if util.state.argument_supplied:
                regex = not regex
            info = set_isearch_info_for(self.view, ISearchInfo(self.view, kwargs['forward'], regex))
            info.open()

        else:
            if cmd == "next":
                info.next(**kwargs)
            elif cmd == "pop":
                info.pop()
            elif cmd == "append_from_cursor":
                info.append_from_cursor()
            elif cmd == "keep_all":
                info.keep_all()
            elif cmd == "done":
                info.done()
            elif cmd == "quit":
                info.quit()
            elif cmd == "yank":
                info.input_view.run_command("sbp_yank")
            else:
                print("Not handling cmd", cmd, kwargs)

    def is_visible(self, **kwargs):
        # REMIND: is it not possible to invoke isearch from the menu for some reason. I think the
        # problem is that a focus thing is happening and we're dismissing ourselves as a result. So
        # for now we hide it.
        return False

class SbpIncSearchEscapeCommand(SbpTextCommand):
    # unregistered = True
    def run_cmd(self, util, next_cmd, next_args):
        info = isearch_info_for(self.view)
        info.done()
        info.view.run_command(next_cmd, next_args)

#
# Indent for tab command. If the cursor is not within the existing indent, just call reindent. If
# the cursor is within the indent, move to the start of the indent and call reindent. If the cursor
# was already at the indent didn't change after calling reindent, indent one more level.
#
class SbpTabCmdCommand(SbpTextCommand):
    def run_cmd(self, util, indent_on_repeat=False):
        point = util.get_point()
        indent,cursor = util.get_line_indent(point)
        tab_size = util.get_tab_size()
        if util.state.active_mark or cursor > indent:
            util.run_command("reindent", {})
        else:
            if indent_on_repeat and util.state.last_cmd == util.state.this_cmd:
                util.run_command("indent", {})
            else:
                # sublime gets screwy with indent if you're not currently a multiple of tab size
                if (indent % tab_size) != 0:
                    delta = tab_size - (indent % tab_size)
                    self.view.run_command("insert", {"characters": " " * delta})
                if cursor < indent:
                    util.run_command("move_to", {"to": "bol", "extend": False})
                util.run_command("reindent", {})

class SbpQuitCommand(SbpTextCommand):
    def run_cmd(self, util):
        window = self.view.window()

        info = isearch_info_for(self.view)
        if info:
            info.quit()
            return

        for cmd in ['clear_fields', 'hide_overlay', 'hide_auto_complete', 'hide_panel']:
            window.run_command(cmd)

        if util.state.active_mark:
            util.toggle_active_mark_mode()
            return

        # If there is a selection, set point to the end of it that is visible.
        s = list(self.view.sel())
        if s:
            start = s[0].a
            end = s[-1].b

            if util.is_visible(end):
                pos = end
            elif util.is_visible(start):
                pos = start
            else:
                # set point to the beginning of the line in the middle of the window
                visible = self.view.visible_region()
                top_line = self.view.rowcol(visible.begin())[0]
                bottom_line = self.view.rowcol(visible.end())[0]
                pos = self.view.text_point((top_line + bottom_line) / 2, 0)
            util.set_selection(sublime.Region(pos))

# This is the actual editor of the zap command
class SbpZapToCharEdit(sublime_plugin.TextCommand):

    def run(self, edit, begin, end):
        region = sublime.Region(int(begin), int(end))
        kill_ring.add(self.view.substr(region), True, False)
        self.view.erase(edit, region)


# This command handles the actual selecting of the zap char
class SbpZapToCharCommand(SbpTextCommand):

    is_kill_cmd = True
    panel = None

    def run_cmd(self, util, **args):
        self.util = util
        self.panel = self.view.window().show_input_panel("Zap To Char:", "", self.zap, self.on_change, None)

    def zap(self):
        pass

    def on_change(self, content):
        """Search forward from the current selection to the next ocurence
        of char"""

        if self.panel == None:
            return

        self.panel.window().run_command("hide_panel")

        start = finish = self.util.get_point()
        found = False
        while not found and finish < self.view.size():
            data = self.view.substr(finish)
            if data == content:
                found = True
                break
            finish += 1

        # Zap to char
        if found:
            self.view.run_command("sbp_zap_to_char_edit", {"begin": start, "end": finish + 1})
        else:
            sublime.status_message("Character %s not found" % content)

class SbpConvertPlistToJsonCommand(SbpTextCommand):
    JSON_SYNTAX = "Packages/Javascript/JSON.tmLanguage"
    PLIST_SYNTAX = "Packages/XML/XML.tmLanguage"

    def run_cmd(self, util):
        import json
        from plistlib import readPlistFromBytes, writePlistToBytes

        data = self.view.substr(sublime.Region(0, self.view.size())).encode("utf-8")
        self.view.replace(util.edit, sublime.Region(0, self.view.size()),
                          json.dumps(readPlistFromBytes(data), indent=4, separators=(',', ': ')))
        self.view.set_syntax_file(JSON_SYNTAX)

class SbpConvertJsonToPlistCommand(SbpTextCommand):
    JSON_SYNTAX = "Packages/Javascript/JSON.tmLanguage"
    PLIST_SYNTAX = "Packages/XML/XML.tmLanguage"

    def run_cmd(self, util):
        import json
        from plistlib import readPlistFromBytes, writePlistToBytes

        data = json.loads(self.view.substr(sublime.Region(0, self.view.size())))
        self.view.replace(util.edit, sublime.Region(0, self.view.size()), writePlistToBytes(data).decode("utf-8"))
        self.view.set_syntax_file(PLIST_SYNTAX)

class SbpTrimTrailingWhiteSpaceAndEnsureNewlineAtEofCommand(sublime_plugin.TextCommand):
    def run(self, edit, trim_whitespace, ensure_newline):
        # make sure you trim trailing whitespace FIRST and THEN check for Newline
        if trim_whitespace:
            trailing_white_space = self.view.find_all("[\t ]+$")
            trailing_white_space.reverse()
            for r in trailing_white_space:
                self.view.erase(edit, r)
        if ensure_newline:
            if self.view.size() > 0 and self.view.substr(self.view.size() - 1) != '\n':
                self.view.insert(edit, self.view.size(), "\n")

class SbpPreSaveWhiteSpaceHook(sublime_plugin.EventListener):
    def on_pre_save(self, view):
        trim = SettingsManager.get("sbp_trim_trailing_white_space_on_save") == True
        ensure = SettingsManager.get("sbp_ensure_newline_at_eof_on_save") == True
        if trim or ensure:
            view.run_command("sbp_trim_trailing_white_space_and_ensure_newline_at_eof",
                             {"trim_whitespace": trim, "ensure_newline": ensure})

#
# Function to dedup views in all the groups of the specified window. This does not close views that
# have changes because that causes a warning to popup. So we have a monitor which dedups views
# whenever a file is saved in order to dedup them then when it's safe.
#
def dedup_views(window):
    group = window.active_group()
    for g in range(window.num_groups()):
        found = dict()
        views = window.views_in_group(g)
        active = window.active_view_in_group(g)
        for v in views:
            if v.is_dirty():
                # we cannot nuke a dirty buffer or we'll get an annoying popup
                continue
            id = v.buffer_id()
            if id in found:
                if v == active:
                    # oops - nuke the one that's already been seen and put this one in instead
                    before = found[id]
                    found[id] = v
                    v = before
                window.focus_view(v)
                window.run_command('close')
            else:
                 found[id] = v
        window.focus_view(active)
    window.focus_group(group)

def InitModule(module_name):
    def get_cmd_name(cls):
        name = cls.__name__
        name = re.sub('(?!^)([A-Z]+)', r'_\1', name).lower()
        # strip "_command"
        return name[0:len(name) - 8]

    module = sys.modules[module_name]
    for name in dir(module):
        if name.startswith("Sbp"):
            cls = getattr(module, name)
            try:
                if not issubclass(cls, SbpTextCommand):
                    continue
            except:
                continue
            # see what the deal is
            name = get_cmd_name(cls)
            cls.jove_cmd_name = name
            if cls.is_kill_cmd:
                kill_cmds.add(name)
            if cls.is_ensure_visible_cmd:
                ensure_visible_cmds.add(name)

InitModule(__name__)
