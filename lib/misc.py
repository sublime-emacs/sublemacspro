import os, re, time, traceback
import sublime, sublime_plugin

from .viewstate import *

# name we use to indicate jove-related status messages
JOVE_STATUS = "1:jove"
PINNED_STATUS = "0:jove_pinned"

# initialized at the end of this file after all commands are defined
kill_cmds = set()
settings_helper = None

default_sbp_sexpr_separators = "./\\()\"'-:,.;<>~!@#$%^&*|+=[]{}`~?";
default_sbp_word_separators = "./\\()\"'-_:,.;<>~!@#$%^&*|+=[]{}`~?";

is_bracket_highlighter_installed = None

def bracket_highlighter_installed():
    global is_bracket_highlighter_installed
    if is_bracket_highlighter_installed is None:
        try:
            import BracketHighlighter.bh_core as bh_core
        except ImportError as e:
            is_bracket_highlighter_installed = False
        else:
            is_bracket_highlighter_installed = True
    return is_bracket_highlighter_installed

def pluralize(string, count, es="s"):
    if count == 1:
        return "%d %s" % (count, string)
    else:
        return "%d %s%s" % (count, string, es)

#
# Handle displaying a view's pinned status.
#
pinned_text = None
def update_pinned_status(view):
    global pinned_text;

    if view.settings().get("is_widget"):
        return

    if view.settings().get("pinned"):
        if pinned_text is None:
            pinned_text = settings_helper.get("sbp_pinned_tab_status_text", False)
        if pinned_text:
            view.set_status(PINNED_STATUS, pinned_text)
    elif pinned_text:
        view.erase_status(PINNED_STATUS)

#
# Get the current set of project roots, sorted from longest to shortest. They are suitable for
# passing to the get_relative_path function to produce the best relative path for a view file name.
#
def get_project_roots():
    window = sublime.active_window()
    if window.project_file_name() is None:
        roots = None
    else:
        project_dir = os.path.dirname(window.project_file_name())
        roots = sorted([os.path.normpath(os.path.join(project_dir, folder))
                       for folder in window.folders()],
                       key=lambda name: len(name), reverse=True)
    return roots

#
# Returns the relative path for the specified file name. The roots are supplied by the
# get_project_roots function, which sorts them appropriately for this function.
#
def get_relative_path(roots, file_name, n_components=2):
    if file_name is not None:
        if roots is not None:
            for root in roots:
                if file_name.startswith(root):
                    file_name = file_name[len(root) + 1:]
                    break
        # show (no more than the) last 2 components of the matching path name
        return os.path.sep.join(file_name.split(os.path.sep)[-n_components:])
    else:
        return "<no file>"

#
# A settings helper class which looks at the current view's settings and uses sublime settings as a
# default value.
#
class SettingsHelper:
    def __init__(self):
        self.global_settings = None

    def get(self, key, default = None):
        if self.global_settings is None:
            self.global_settings = sublime.load_settings('sublemacspro.sublime-settings')

        settings = sublime.active_window().active_view().settings()
        value = settings.get(key, None)
        if value is None:
            value = self.global_settings.get(key, default)
        return value

#
# Called by all modules that define sublime editor commands.
#
def preprocess_module(module):
    def get_cmd_name(cls):
        name = cls.__name__
        name = re.sub('(?!^)([A-Z]+)', r'_\1', name).lower()
        # strip "_command"
        return name[0:len(name) - 8]

    for name in dir(module):
        if name.startswith("Sbp"):
            cls = getattr(module, name)
            try:
                if not issubclass(cls, SbpTextCommand):
                    # print("SKIP", cls)
                    continue
            except Exception as e:
                print("EXCEPTION", e)
                continue
            # see what the deal is
            name = get_cmd_name(cls)
            cls.jove_cmd_name = name
            if cls.is_kill_cmd:
                kill_cmds.add(name)

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
            if self.is_ensure_visible_cmd and util.just_one_cursor():
                util.ensure_visible(util.get_last_cursor())
        finally:
            vs.entered -= 1

        if vs.entered == 0 and (cmd != 'sbp_universal_argument' or self.unregistered):
            vs.last_cmd = vs.this_cmd
            vs.argument_value = 0
            vs.argument_supplied = False

            if self.should_reset_target_column:
                util.reset_target_column()

#
# Simple wrapper for window commands.
#
class SbpWindowCommand(sublime_plugin.WindowCommand):
    def run(self, **kwargs):
        self.util = CmdUtil(self.window.active_view(), state=ViewState.get(self.window.active_view()))
        self.run_cmd(self.util, **kwargs)

STATUS_MSG_DISPLAY_TIME = 3000
status_msg_time = None
def set_jove_status(view, msg, auto_erase):
    global status_msg_time
    # erase this message some time in the future, unless another message appears
    view.set_status(JOVE_STATUS, msg)
    status_msg_time = tm = time.time()
    def doit():
        if status_msg_time == tm:
            view.erase_status(JOVE_STATUS)
    if auto_erase:
        sublime.set_timeout(doit, STATUS_MSG_DISPLAY_TIME)

#
# A helper class which provides a bunch of useful functionality on a view.
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
    def set_status(self, msg, auto_erase=True):
        set_jove_status(self.view, msg, auto_erase)

    #
    # Returns point. Point is where the cursor is in the possibly extended region. If there are
    # multiple cursors it uses the first one in the list.
    #
    def get_point(self):
        sel = self.view.sel()
        if len(sel) > 0:
            return sel[0].b
        return -1

    #
    # Sets the point to the specified value. This will erase multiple cursors and replace with just
    # one.
    def set_point(self, point):
        selection = self.view.sel()
        selection.clear()
        selection.add(sublime.Region(point))

    #
    # This no-op ensures the next/prev line target column is reset to the new locations.
    #
    def reset_target_column(self):
        selection = self.view.sel()
        if len(selection) > 0 and selection[-1].empty() and selection[-1].b < self.view.size():
            self.run_command("move", {"by": "characters", "forward": True})
            self.run_command("move", {"by": "characters", "forward": False})

    def get_tab_size(self):
        return self.view.settings().get("tab_size", 8)

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
    # Get_regions() returns the current selection as regions (if the cursors are not
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

    def get_encompassing_region(self):
        regions = self.get_regions()
        if regions:
            return sublime.Region(regions[0].begin(), regions[-1].end())
        return None

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
        return re.match(r'^[ \t]*$', text) is not None

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
            self.set_cursors(self.get_regions(), ensure_visible=False)
        else:
            self.make_cursors_empty()

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
        return [sublime.Region(c.begin() if begin else c.b) if not c.empty() else c for c in self.view.sel()]

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

    def make_cursors_empty(self, to_start=False):
        selection = self.view.sel()
        if to_start:
            cursors = [sublime.Region(c.a) for c in selection]
        else:
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
        fail = False

        # REMIND: for delete-white-space and other commands that change the size of the
        # buffer, you need to keep the cursors in a named set of cursors (like the mark
        # ring) so that they are adjusted properly.
        can_modify = kwargs.pop('can_modify', False)

        if can_modify:
            key = "tmp_cursors"
            view.add_regions(key, regions, "tmp", "", sublime.HIDDEN)
            for i in range(len(regions)):
                # Grab the region (whose position has been maintained/adjusted by sublime).
                # Unfortunately we need to assume one region might merge into another at any time,
                # and reload all regions to check. Also, if the function returns a cursor, we need
                # to use it rather than relying on the default location of that cursor as managed by
                # sublime. (That is rather expensive but we hardly use this feature.)
                regions = view.get_regions(key)
                if i >= len(regions):
                    # we've deleted some cursors along the way - we're done
                    break
                selection.add(regions[i])
                cursor = function(regions[i], *args, **kwargs)
                if cursor is not None:
                    # grab adjusted regions
                    regions = view.get_regions(key)

                    # stick our value in
                    regions[i] = cursor

                    # reset the regions
                    view.erase_regions(key)
                    view.add_regions(key, regions, "tmp", "", sublime.HIDDEN)

                selection.clear()
            cursors = view.get_regions(key)
            view.erase_regions(key)
        else:
            # run the command passing in each cursor and collecting the returned cursor
            cursors = []
            for i,cursor in enumerate(regions):
                selection.add(cursor)
                cursor = function(cursor, *args, **kwargs)
                if cursor is None:
                    fail = True
                    break
                selection.clear()
                cursors.append(cursor)

        # add them all back when we're done
        if fail:
            self.set_status("Operation failed on one of your cursors")
            selection.add_all(regions)
        else:
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
        self.set_cursors([sublime.Region(pos)], ensure_visible=False)
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
        #
        # Original but broken version of this code which uses sublime functions to do bracket
        # and string matching.
        #
        def goto_orig():
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
        # A version which uses the bracket highlighter package when available.
        #
        def goto_bracket_highlighter():
            view = self.view
            scope_name = view.scope_name(point)
            if scope_name.find("comment") >= 0:
                # we don't handle this brackets inside comments so just keep going
                return None

            brac = "([{'`\""
            kets = ")]}'`\""

            if direction > 0:
                ch = view.substr(point)
                index = brac.find(ch)
                if view.substr(point + 1) == kets[index]:
                    # right next to the matching pair - bracket highlight doesn't handle this well
                    return point + 2
                self.set_point(point + 1)
                self.run_command("bh_key", {
                                     "lines": True, "no_block_mode": True, "no_outside_adj": True,
                                     "plugin": {
                                         "args": {"select": "right"},
                                         "command": "bh_modules.bracketselect", "type": ["__all__"]
                                     }
                                 })
                return self.get_point() + 1
            elif direction < 0:
                ch = view.substr(point - 1)
                index = kets.find(ch)
                if view.substr(point - 2) == brac[index]:
                    # right next to the matching pair - bracket highlight doesn't handle this well
                    return point - 2
                self.set_point(point - 1)
                self.run_command("bh_key", {
                                     "lines": True, "no_block_mode": True, "no_outside_adj": True,
                                     "plugin": {
                                         "args": {"select": "left"},
                                         "command": "bh_modules.bracketselect", "type": ["__all__"]
                                     }
                                 })
                return self.get_point() - 1

            return None

        return goto_bracket_highlighter() if bracket_highlighter_installed() else goto_orig()

    #
    # Run the specified command and args in the current view. If point is specified set point in the
    # view before running the command. Returns the resulting point.
    #
    def run_command(self, cmd, args=None, point=None):
        view = self.view
        if point is not None:
            view.sel().clear()
            view.sel().add(sublime.Region(point, point))
        view.run_command(cmd, args)
        return self.get_point()

settings_helper = SettingsHelper()
