import re, sys, time, os
import functools as fu
import sublime, sublime_plugin
from copy import copy

from .lib.misc import *
from .lib import kill_ring
from .lib import isearch

import Default.paragraph as paragraph
from . import sbp_layout as ll

# repeatable commands
repeatable_cmds = set(['move', 'left_delete', 'right_delete', 'undo', 'redo'])

# built-in commands we need to do ensure_visible after being run
# REMIND: I think we can delete this.
built_in_ensure_visible_cmds = set(['move', 'move_to'])

class ViewWatcher(sublime_plugin.EventListener):
    def __init__(self, *args, **kwargs):
        super(ViewWatcher, self).__init__(*args, **kwargs)
        self.pending_dedups = 0

    def on_close(self, view):
        ViewState.on_view_closed(view)

    def on_modified(self, view):
        CmdUtil(view).toggle_active_mark_mode(False)

    def on_activated(self, view):
        update_pinned_status(view)

    def on_activated_async(self, view):
        info = isearch.info_for(view)
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
            return test(isearch.info_for(view) is not None)
        if key == "sbp_has_active_mark":
            return test(CmdUtil(view).state.active_mark)
        if key == "sbp_has_visible_selection":
            return test(view.sel()[0].size() > 1)
        if key == "sbp_use_alt_bindings":
            return test(settings_helper.get("sbp_use_alt_bindings"))
        if key == "sbp_use_super_bindings":
            return test(settings_helper.get("sbp_use_super_bindings"))
        if key == "sbp_alt+digit_inserts":
            return test(settings_helper.get("sbp_alt+digit_inserts") or not settings_helper.get("sbp_use_alt_bindings"))
        if key == 'sbp_has_prefix_argument':
            return test(CmdUtil(view).has_prefix_arg())
        if key == "sbp_catchall":
            return True

    def on_post_save(self, view):
        # Schedule a dedup, but do not do it NOW because it seems to cause a crash if, say, we're
        # saving all the buffers right now. So we schedule it for the future.
        self.pending_dedups += 1
        def doit():
            self.pending_dedups -= 1
            if self.pending_dedups == 0:
                dedup_views(sublime.active_window())
        sublime.set_timeout(doit, 50)

#
# CmdWatcher watches all the commands and tries to correctly process the following situations:
#
#   - canceling i-search if another window command is performed or a mouse drag starts
#   - override commands and run them N times if there is a numeric argument supplied
#   - if transient mark mode, automatically extend the mark when using certain commands like forward
#     word or character
#
class CmdWatcher(sublime_plugin.EventListener):
    def __init__(self, *args, **kwargs):
        super(CmdWatcher, self).__init__(*args, **kwargs)
        self.pinned_text = None

    def on_post_window_command(self, window, cmd, args):
        # update_pinned_status(window.active_view())
        info = isearch.info_for(window)
        if info is None:
            return None

        # Some window commands take us to new view. Here's where we abort the isearch if that happens.
        if window.active_view() != info.view:
            info.done()

    #
    # Override some commands to execute them N times if the numberic argument is supplied.
    #
    def on_text_command(self, view, cmd, args):
        # escape the current isearch if one is in progress, unless the command is already related to
        # isearch
        if isearch.info_for(view) is not None:
            if cmd not in ('sbp_inc_search', 'sbp_inc_search_escape', 'drag_select'):
                return ('sbp_inc_search_escape', {'next_cmd': cmd, 'next_args': args})
            return

        vs = ViewState.get(view)

        if args is None:
            args = {}

        # first keep track of this_cmd and last_cmd (if command starts with "sbp_" it's handled
        # elsewhere)
        if not cmd.startswith("sbp_"):
            vs.this_cmd = cmd

        #
        # Process events that create a selection. The hard part is making it work with the emacs
        # region.
        #
        if cmd == 'drag_select':
            info = isearch.info_for(view)
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
        util = CmdUtil(view)
        if vs.active_mark and vs.this_cmd != 'drag_select' and vs.last_cmd == 'drag_select':
            # if we just finished a mouse drag, make sure active mark mode is off
            if cmd != "context_menu":
                util.toggle_active_mark_mode(False)

        # reset numeric argument (if command starts with "sbp_" this is handled elsewhere)
        if not cmd.startswith("sbp_"):
            vs.argument_value = 0
            vs.argument_supplied = False
            vs.last_cmd = cmd

        if vs.active_mark:
            util.set_cursors(util.get_regions())

        # if cmd in built_in_ensure_visible_cmds and util.just_one_cursor():
        #     util.ensure_visible(util.get_last_cursor())

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

class SbpChainCommand(SbpTextCommand):
    """A command that easily runs a sequence of other commands."""

    def run_cmd(self, util, commands, ensure_point_visible=False):
        for c in commands:
            if 'window_command' in c:
                util.run_window_command(c['window_command'], c['args'])
            elif 'command' in c:
                util.run_command(c['command'], c['args'])

        if ensure_point_visible:
            util.ensure_visible(sublime.Region(util.get_point()))


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
        util.set_status(status)

#
# Implements moving by words, emacs style.
#
class SbpMoveWordCommand(SbpTextCommand):
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

        separators = settings_helper.get("sbp_word_separators", default_sbp_word_separators)

        # determine the direction
        count = util.get_count() * direction
        forward = count > 0
        count = abs(count)

        def call_find_by_class(point, classes, separators):
          '''
          This is a small wrapper that maps to the right find_by_class call
          depending on the version of ST installed
          '''
          return self.find_by_class_native(view, point, forward, classes, separators)

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
# Perform the uppercase/lowercase/capitalize commands on all the current cursors. If use_region is
# true, the command will be applied to the regions, not to words. The regions are either existing
# visible selection, OR, the emacs region(s) which might not be visible. If there are no non-empty
# regions and use_region=True, this command is a no-op.
#
class SbpChangeCaseCommand(SbpTextCommand):
    re_to_underscore = re.compile('((?<=[a-z0-9])[A-Z]|(?!^)[A-Z](?=[a-z]))')
    re_to_camel = re.compile(r'(?!^)_([a-zA-Z])')

    # re_to_camel = re.compile('((?<=[a-z0-9])[A-Z]|(?!^)[A-Z](?=[a-z]))')

    def underscore(self, text):
        s1 = self.re_to_underscore.sub(r'_\1', text).lower()
        return s1

    def camel(self, text):
        s1 = self.re_to_camel.sub(lambda m: m.group(1).upper(), text)
        return s1

    def run_cmd(self, util, mode, use_region=False, direction=1):
        view = self.view
        count = util.get_count(True)

        # If cursors are not empty (e.g., visible marks) then we use the selection and we're in
        # region mode. If the cursors are empty but the emacs regions are not, we use them as long
        # as mode="regions". Otherwise, we generate regions by applying a word motion command.
        selection = view.sel()
        regions = list(selection)
        empty_cursors = util.all_empty_regions(regions)
        if empty_cursors and use_region:
            emacs_regions = util.get_regions()
            if emacs_regions and not util.all_empty_regions(emacs_regions):
                empty_cursors = False
                selection.clear()
                selection.add_all(emacs_regions)

        if empty_cursors:
            if use_region:
                return

            # This works first by finding the bounds of the operation by executing a forward-word
            # command. Then it performs the case command. But only if there are no selections or
            # regions to operate on.

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
        elif mode == "title":
            for r in selection:
                util.view.replace(util.edit, r, view.substr(r).title())
        elif mode in ("underscore", "camel"):
            fcn = self.underscore if mode == "underscore" else self.camel
            delta = 0
            for r, s in zip(regions, selection):
                orig = view.substr(s)
                replace = fcn(orig)
                this_delta = len(orig) - len(replace)
                util.view.replace(util.edit, s, replace)
                # We need to adjust the size of regions by this_delta, and the position of each
                # region by the accumulated delta for when we put the selection back at the end.
                if s.b > s.a:
                    r.b -= this_delta
                else:
                    r.a -= this_delta
                r.b -= delta
                r.a -= delta
                delta += this_delta
        else:
            print("Unknown case setting:", mode)
            return

        if empty_cursors and count > 0:
            # was a word-based execution
            for r in new_regions:
                r.a = r.b = r.end()
            selection.clear()
            selection.add_all(new_regions)
        else:
            # we used the selection or the emacs regions
            selection.clear()
            selection.add_all(regions)

#
# A poor implementation of moving by s-expressions. The problem is it tries to use the built-in
# sublime capabilities for matching brackets, and it can be tricky getting that to work.
#
# The real solution is to figure out how to require/request the bracket highlighter code to be
# loaded and just use it.
#
class SbpMoveSexprCommand(SbpTextCommand):
    is_ensure_visible_cmd = True
    should_reset_target_column = True

    def run_cmd(self, util, direction=1):
        view = self.view

        separators = settings_helper.get("sbp_sexpr_separators", default_sbp_sexpr_separators)

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
                        if ch in "({[`'\"":
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
                        if ch in ")}]`\"":
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
        view = self.view

        count = util.get_count() * direction
        forward = count > 0
        count = abs(count)

        def advance(cursor):
            whitespace = '\t\x0b\x0c\r \n'
            if not forward:
                # Remove whitespace and new lines for moving forward and backward paragraphs
                this_region_begin = max(0, cursor.begin() - 1)
                while this_region_begin > 0 and view.substr(this_region_begin) in whitespace:
                    this_region_begin -= 1
                point = paragraph.expand_to_paragraph(view, this_region_begin).begin()
            else:
                this_region_end = cursor.end()
                limit = self.view.size() - 1
                while this_region_end < limit and view.substr(this_region_end) in whitespace:
                    this_region_end += 1
                point = paragraph.expand_to_paragraph(self.view, this_region_end).end()

            return sublime.Region(point)

        for c in range(count):
            util.for_each_cursor(advance)

        s = view.sel()
        util.ensure_visible(s[-1] if forward else s[0])

#
# A class which implements all the hard work of performing a move and then delete/kill command. It
# keeps track of the cursors, then runs the command to move all the cursors, and then performs the
# kill. This is used by the generic SbpMoveThenDeleteCommand command, but also commands that require
# input from a panel and so are not synchronous.
#
class MoveThenDeleteHelper():
    def __init__(self, util):
        self.util = util
        self.selection = util.view.sel()

        # assume forward kill direction
        self.forward = True

        # remember the current cursor positions
        self.orig_cursors = [s for s in self.selection]

        # Remember if previous was a kill command now, because if we check in self.finish() it's too
        # late and the answer is always yes (because of this command we're "helping").
        self.last_was_kill_cmd = util.state.last_was_kill_cmd()

    #
    # Finish the operation. Sometimes we're called later with a new util object, because the whole
    # thing was done asynchronously (see the zap code).
    #
    def finish(self, new_util=None):
        util = new_util if new_util else self.util
        view = util.view
        selection = self.selection
        orig_cursors = self.orig_cursors

        # extend all cursors so we can delete the bytes
        new_cursors = list(selection)

        # but first check to see how many regions collapsed as a result of moving the cursors (e.g.,
        # if they pile up at the end of the buffer)
        collapsed_regions = len(orig_cursors) - len(new_cursors)
        if collapsed_regions == 0:
            # OK - so now check to see how many collapse after we combine the beginning and end
            # points of each region. We do that by creating the selection object, which disallows
            # overlapping regions by collapsing them.
            selection.clear()
            for old,new in zip(orig_cursors, new_cursors):
                if old < new:
                    selection.add(sublime.Region(old.begin(), new.end()))
                else:
                    selection.add(sublime.Region(new.begin(), old.end()))

            collapsed_regions = len(orig_cursors) - len(selection)

            # OK one final check to see if any regions will overlap each other after we perform the
            # kill.
            if collapsed_regions == 0:
                cursors = list(selection)
                for i, c in enumerate(cursors[1:]):
                    if cursors[i].contains(c.begin()):
                        collapsed_regions += 1

        if collapsed_regions != 0:
            # restore everything to previous state and display a popup error
            selection.clear()
            selection.add_all(orig_cursors)
            sublime.error_message("Couldn't perform kill operation because %d regions would have collapsed into adjacent regions!" % collapsed_regions)
            return

        # copy the text into the kill ring
        regions = [view.substr(r) for r in view.sel()]
        kill_ring.add(regions, forward=self.forward, join=self.last_was_kill_cmd)

        # erase the regions
        for region in selection:
            view.erase(util.edit, region)


#
# This command remembers all the current cursor positions, executes a command on all the cursors,
# and then deletes all the data between the two.
#
class SbpMoveThenDeleteCommand(SbpTextCommand):
    is_ensure_visible_cmd = True
    is_kill_cmd = True

    def run_cmd(self, util, move_cmd, **kwargs):
        # prepare
        helper = MoveThenDeleteHelper(util)

        # peek at the count and update the helper's forward direction
        count = util.get_count(True)
        if 'direction' in kwargs:
            count *= kwargs['direction']
        helper.forward = count > 0

        util.view.run_command(move_cmd, kwargs)
        helper.finish()

#
# Goto the the Nth line as specified by the emacs arg count, or prompt for a line number of one
# isn't specified.
#
class SbpGotoLineCommand(SbpTextCommand):
    is_ensure_visible_cmd = True
    def run_cmd(self, util):
        if util.has_prefix_arg():
            util.goto_line(util.get_count())
        else:
            util.run_window_command("show_overlay", {"overlay": "goto", "text": ":"})

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
            util.set_status("Shifted %d of %d lines in the region" % (shifted, count))

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

        if settings_helper.get("sbp_active_mark_mode", False):
            util.set_active_mark_mode()

class SbpCancelMarkCommand(SbpTextCommand):
    def run_cmd(self, util):
        if util.state.active_mark:
            util.toggle_active_mark_mode()
        util.state.mark_ring.clear()

class SbpSwapPointAndMarkCommand(SbpTextCommand):
    def run_cmd(self, util, toggle_active_mark_mode=False):
        if util.state.argument_supplied or toggle_active_mark_mode:
            util.toggle_active_mark_mode()
        else:
            util.swap_point_and_mark()

class SbpEnableActiveMarkCommand(SbpTextCommand):
    def run_cmd(self, util, enabled):
        util.toggle_active_mark_mode(enabled)

class SbpMoveToCommand(SbpTextCommand):
    is_ensure_visible_cmd = True
    def run_cmd(self, util, to, always_push_mark=False):
        if to == 'bof':
            util.push_mark_and_goto_position(0)
        elif to == 'eof':
            util.push_mark_and_goto_position(self.view.size())
        elif to in ('eow', 'bow'):
            visible = self.view.visible_region()
            pos = visible.a if to == 'bow' else visible.b
            if always_push_mark:
                util.push_mark_and_goto_position(pos)
            else:
                util.set_cursors([sublime.Region(pos)])

class SbpSelectAllCommand(SbpTextCommand):
    def run_cmd(self, util, activate_mark=True):
        # set mark at current position
        util.set_mark()

        # set a mark at end of file
        util.set_mark(regions=[sublime.Region(self.view.size())])

        # goto the top of the file
        util.set_point(0)

        if activate_mark:
            util.toggle_active_mark_mode(True)
        else:
            util.ensure_visible(sublime.Region(0))


class SbpOpenLineCommand(SbpTextCommand):
    def run_cmd(self, util):
        view = self.view
        count = util.get_count()
        if count > 0:
            for point in view.sel():
                view.insert(util.edit, point.b, "\n" * count)
            while count > 0:
                view.run_command("move", {"by": "characters", "forward": False})
                count -= 1

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
                util.ensure_visible(util.get_last_cursor())
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
# Close the N least recently touched views, leaving at least one view remaining.
#
class SbpCloseStaleViewsCommand(SbpWindowCommand):
    def run_cmd(self, util, n_windows=None):
        window = sublime.active_window()
        sorted = ViewState.sorted_views(window, window.active_group())
        if n_windows is None or util.has_prefix_arg():
            n_windows = util.get_count()
        while n_windows > 0 and len(sorted) > 1:
            view = sorted.pop()
            if view.is_dirty() or view.settings().get("pinned"):
                continue
            window.focus_view(view)
            window.run_command('close')
            n_windows -= 1

        # go back to the original view
        window.focus_view(util.view)

#
# Toggle the pinned state of the current view.
#
class SbpToggleViewPinnedCommand(SbpTextCommand):
    def run_cmd(self, util):
        view = self.view
        settings = view.settings()
        pinned = settings.get("pinned", False)
        settings.set("pinned", not pinned)
        update_pinned_status(view)

#
# Closes the current view and selects the most recently used one in its place. This is almost like
# kill buffer in emacs but if another view is displaying this file, it will still exist there. In
# short, this is like closing a tab but rather than selecting an adjacent tab, it selects the most
# recently used "buffer".
#
class SbpCloseCurrentViewCommand(SbpWindowCommand):
    def run_cmd(self, util, n_windows=10):
        window = sublime.active_window()
        sorted = ViewState.sorted_views(window, window.active_group())
        if len(sorted) > 0:
            view = sorted.pop(0)
            window.focus_view(view)
            window.run_command('close')
            if len(sorted) > 0:
                window.focus_view(sorted[0])
        else:
            window.run_command('close')

#
# Exists only to support kill-line with multiple cursors.
#
class SbpMoveForKillLineCommand(SbpTextCommand):
    def run_cmd(self, util, **kwargs):
        view = self.view
        state = util.state

        line_mode = state.argument_supplied
        count = util.get_count()

        def advance(cursor):
            start = cursor.b
            text,index,region = util.get_line_info(start)

            if line_mode:
                # go down N lines
                for i in range(abs(count)):
                    view.run_command("move", {"by": "lines", "forward": count > 0})

                end = util.get_point()
                if count != 0 and region.contains(end):
                    # same line we started on - must be on the last line of the file
                    end = region.end() if count > 0 else region.begin()
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

            return sublime.Region(end, end)

        util.for_each_cursor(advance)

#
# Emacs Yank and Yank Pop commands.
#
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

#
# Like the yank command except it displays a menu of all the kills and lets you choose which one to
# yank.
#
class SbpChooseAndYank(SbpTextCommand):
    def run_cmd(self, util, all_cursors=False):
        # items is an array of (index, text) pairs
        items = kill_ring.get_popup_sample(util.view)

        def on_done(idx):
            if idx >= 0:
                kill_ring.set_current(items[idx][0])

                if all_cursors:
                    util.run_command("sbp_yank_all_cursors")
                else:
                    util.run_command("sbp_yank", {})

        if items:
            sublime.active_window().show_quick_panel([item[1] for item in items], on_done)
        else:
            util.set_status('Nothing in history')

#
# Like the yank command except this automatically creates the number of cursors you need to handle
# the yanked text. For example, if there are 10 yanked regions in the most recent kill, this command
# will automatically create 10 cursors on 10 lines, and then perform the yank.
#
class SbpYankAllCursorsCommand(SbpTextCommand):
    def run_cmd(self, util):
        view = self.view

        # request the regions of text from the current kill
        texts = kill_ring.get_current(0, 0)
        if texts is None:
            util.set_status("Nothing to yank")

        # insert the right number of lines
        point = util.get_point()
        view.insert(util.edit, point, "\n" * len(texts))
        regions = (sublime.Region(point + p) for p in range(len(texts)))
        selection = view.sel()
        selection.clear()
        selection.add_all(regions)

        view.run_command("sbp_yank")


#
# A special command that allows us to invoke incremental-search commands from the menu.
#
class SbpIncSearchFromMenuCommand(SbpTextCommand):
    def run_cmd(self, util, **kwargs):
        def doit():
            util.run_command("sbp_inc_search", kwargs)
        sublime.set_timeout(doit, 50)


class SbpIncSearchCommand(SbpTextCommand):
    def run_cmd(self, util, cmd=None, **kwargs):
        info = isearch.info_for(self.view)
        if info is None or cmd is None:
            regex = kwargs.get('regex', False)
            if util.state.argument_supplied:
                regex = not regex
            info = isearch.set_info_for(self.view, isearch.ISearchInfo(self.view, kwargs['forward'], regex))
            info.open()
        else:
            if cmd == "next":
                info.next(**kwargs)
            elif cmd == "pop_one":
                info.pop()
            elif cmd == "pop_group":
                info.pop(True)
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
            elif cmd == "set_search":
                view = info.input_view
                view.replace(util.edit, sublime.Region(0, view.size()), kwargs['text'])
                view.run_command("move_to", {"to": "eof"})
            elif cmd == "history":
                info.history(**kwargs)
            else:
                print("Not handling cmd", cmd, kwargs)

    def is_visible(self, **kwargs):
        # REMIND: is it not possible to invoke isearch from the menu for some reason. I think the
        # problem is that a focus thing is happening and we're dismissing ourselves as a result. So
        # for now we hide it.
        return True

class SbpIncSearchEscapeCommand(SbpTextCommand):
    # unregistered = True
    def run_cmd(self, util, next_cmd, next_args):
        info = isearch.info_for(self.view)
        info.done()
        if next_cmd in ("show_overlay",):
            sublime.active_window().run_command(next_cmd, next_args)
        else:
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

#
# A quit command which is basically a no-op unless there are multiple cursors or a selection, in
# which case it tries to pick one end or the other to make the single selection.
#
class SbpQuitCommand(SbpTextCommand):
    def run_cmd(self, util, favor_side="start"):
        window = self.view.window()

        # get all the regions
        regions = list(self.view.sel())
        if not util.all_empty_regions(regions):
            util.make_cursors_empty(to_start=favor_side == "start")
            util.toggle_active_mark_mode(False)
            return

        # If there is a selection or multiple cursors, set point to the end of it that is visible OR
        # if neither the start nor end is visible, go to whichever is closest.
        if regions and regions[0].begin() != regions[-1].end():
            start = regions[0].a
            end = regions[-1].b

            favor_start = favor_side == "start"
            favor_end = favor_side == "end"

            start_visible = util.is_visible(start)
            end_visible = util.is_visible(end)

            pos = None
            if not (start_visible or end_visible):
                # pick whichever side is closest
                visible = self.view.visible_region()
                if abs(visible.begin() - start) < abs(visible.end() - end):
                    pos = start
                else:
                    pos = end
            elif len(regions) > 1:
                if favor_start and start_visible:
                    pos = start
                elif favor_end and end_visible:
                    pos = end
                elif start_visible:
                    pos = start
                elif end_visible:
                    pos = end
            # default value for pos is the current end of the single selection
            if pos is None:
                pos = regions[-1].b
            else:
                regions = sublime.Region(pos)
                util.set_selection(regions)
                util.ensure_visible(regions)
            return

        #
        # Cancel the mark if it's visible and we're supposed to.
        #
        if settings_helper.get("sbp_cancel_mark_enabled", False):
            # if util.state.mark_ring.has_visible_mark():
            util.run_command("sbp_cancel_mark")


#
# A class which knows how to ask for a single character and then does something with it.
#
class AskCharOrStringBase(SbpTextCommand):
    def run_cmd(self, util, prompt="Type character"):
        self.util = util
        self.window = self.view.window()
        self.count = util.get_count()
        self.mode = "char"

        # kick things off by showing the panel
        self.window.show_input_panel(prompt, "", self.on_done, self.on_change, None)

    def on_change(self, content):
        # on_change is notified immediate upon showing the panel before a key is even pressed
        if self.mode == "string" or len(content) < 1:
            return
        self.process_cursors(content)

    def process_cursors(self, content):
        util = self.util
        self.window.run_command("hide_panel")

        count = abs(self.count)
        for i in range(count):
            self.last_iteration = (i == count - 1)
            util.for_each_cursor(self.process_one, content)

    def on_done(self, content):
        if self.mode == "string":
            self.process_cursors(content)

#
# Jump to char command inputs one character and jumps to it. If include_char is True it goes just past
# the character in question, otherwise it stops just before it.
#
class SbpJumpToCharCommand(AskCharOrStringBase):
    def run_cmd(self, util, *args, include_char=True, **kwargs):
        if 'prompt' not in kwargs:
            kwargs['prompt'] = "Jump to char: "
        super(SbpJumpToCharCommand, self).run_cmd(util, *args, **kwargs)
        self.include_char = include_char

    def process_one(self, cursor, ch):
        r = self.view.find(ch, cursor.end(), sublime.LITERAL)
        if r:
            p = r.begin()
            if self.include_char or not self.last_iteration:
                # advance one more if this is not the last_iteration or else we'll forever be stuck
                # at the same position
                p += 1
            return p
        return None

class SbpZapToCharCommand(SbpJumpToCharCommand):
    is_kill_cmd = True
    def run_cmd(self, util, **kwargs):
        # prepare
        self.helper = MoveThenDeleteHelper(util)
        kwargs['prompt'] = "Zap to char: "
        super(SbpZapToCharCommand, self).run_cmd(util, **kwargs)

    def process_cursors(self, content):
        # process cursors does all the work (of jumping) and then ...
        super(SbpZapToCharCommand, self).process_cursors(content)

        # Save the helper in view state and invoke a command to make use of it. We can't use it now
        # because we don't have access to a valid edit object, because this function
        # (process_cursors) is called asynchronously after the original text command has returned.
        vs = ViewState.get(self.view)
        vs.pending_move_then_delete_helper = self.helper

        # ... we can finish what we started
        self.window.run_command("sbp_finish_move_then_delete")

#
# A helper class which will simply finish what was started in a previous command that was using a
# MoveThenDeleteHelper class. Some commands return before they are finished (e.g., they pop up a
# panel) and so we need a new 'edit' instance to be able to perform any edit operations. This is how
# we do that.
#
class SbpFinishMoveThenDeleteCommand(SbpTextCommand):
    is_kill_cmd = True
    def run_cmd(self, util):
        vs = ViewState.get(self.view)
        helper = vs.pending_move_then_delete_helper
        vs.pending_move_then_delete_helper = None
        helper.finish(util)

#
# Jump to string command inputs a string and jumps to it (case sensitive).
# If include_string is True it jumps past the string being searched,
# otherwise it stops just before it.
#
class SbpJumpToStringCommand(AskCharOrStringBase):
    def run_cmd(self, util, *args, include_string=True, **kwargs):
        if 'prompt' not in kwargs:
            kwargs['prompt'] = "Jump to string: "
        super(SbpJumpToStringCommand, self).run_cmd(util, *args, **kwargs)
        self.mode = "string"
        self.include_string = include_string

    def process_one(self, cursor, word):
        r = self.view.find(word, cursor.end(), sublime.LITERAL)
        if r:
            if self.include_string is False:
                # Jump to beginning of string
                p = r.begin()
            else:
                # Jump to after the string
                p = r.end()
            return p
        return None

# Largely unchanged from zap to char command besides calling jump to string
class SbpZapToStringCommand(SbpJumpToStringCommand):
    is_kill_cmd = True
    def run_cmd(self, util, **kwargs):
        # prepare
        self.helper = MoveThenDeleteHelper(util)
        kwargs['prompt'] = "Zap to string: "
        super(SbpZapToStringCommand, self).run_cmd(util, **kwargs)

    def process_cursors(self, content):
        # process cursors does all the work (of jumping) and then ...
        super(SbpZapToStringCommand, self).process_cursors(content)

        # Save the helper in view state and invoke a command to make use of it. We can't use it now
        # because we don't have access to a valid edit object, because this function
        # (process_cursors) is called asynchronously after the original text command has returned.
        vs = ViewState.get(self.view)
        vs.pending_move_then_delete_helper = self.helper

        # ... we can finish what we started
        self.window.run_command("sbp_finish_move_then_delete")

#
# A single command that does both ensuring newline at end of file AND deleting trailing whitespace.
# If this is not a single command, blank spaces at the end of the file will cause an extra newline.
# It's important to delete end of line whitespace before doing the end of file newline check.
#
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
        trim = settings_helper.get("sbp_trim_trailing_white_space_on_save") == True
        ensure = settings_helper.get("sbp_ensure_newline_at_eof_on_save") == True
        if trim or ensure:
            view.run_command("sbp_trim_trailing_white_space_and_ensure_newline_at_eof",
                             {"trim_whitespace": trim, "ensure_newline": ensure})

#
# Function to dedup views in all the groups of the specified window. This does not close views that
# have changes because that causes a warning to popup. So we have a monitor which dedups views
# whenever a file is saved in order to dedup them then when it's safe.
#
def dedup_views(window):
    # remember the current group so we can focus back to it when we're done
    group = window.active_group()
    for g in range(window.num_groups()):
        # get views for current group sorted by most recently used
        active = window.active_view_in_group(g)
        views = ViewState.sorted_views(window, g)
        view_by_buffer_id = dict()
        for v in views:
            if v.is_dirty():
                # we cannot nuke a dirty buffer or we'll get an annoying popup
                continue
            id = v.buffer_id()
            if id in view_by_buffer_id:
                # already have a view with this buffer - so nuke this one - it's older
                window.focus_view(v)
                window.run_command('close')
            else:
                 view_by_buffer_id[id] = v
        window.focus_view(active)
    window.focus_group(group)

def plugin_loaded():
    kill_ring.initialize()
    isearch.initialize()

    # preprocess this module
    preprocess_module(sys.modules[__name__])
