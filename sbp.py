import functools as fu
import sublime
import sublime_plugin
import paragraph


class SbpRegisterStore:
    """
    Base class to stroe data for the registers, could be a plain dict,
    but we make it more complicated by wrapping the dict :)
    """
    registers = {}

    def get(self, key):
        if not key in self.registers:
            return ""
        else:
            return self.registers[key]

    def store(self, key, val):
        self.registers[key] = val

    def  __contains__(self, key):
        return key in self.registers

# Global variable to store data in the registers
sbp_registers = SbpRegisterStore()


class SbpWrapParagraphCommand(paragraph.WrapLinesCommand):
    '''
    The Sublime "wrap_width" setting controls both on-screen wrapping and
    the column at which the WrapLinesCommand folds lines. Those two
    settings should be different; otherwise, things don't look right
    on the screen. This plugin looks for a "wrap_paragraph" setting and,
    if found, uses that value to override the value of "wrap_width". Then,
    it invokes the stock SublimeText "wrap_lines" command.

    Bind "wrap_paragraph" to a key to use this command.
    '''

    def run(self, edit, width=0):
        if width == 0 and self.view.settings().get("wrap_paragraph"):
            try:
                width = int(self.view.settings().get("wrap_paragraph"))
            except TypeError:
                pass
        super(SbpWrapParagraphCommand, self).run(edit, width)


class SbpFixupWhitespaceCommand(sublime_plugin.TextCommand):
    '''
    SbpFixupWhitespaceCommand is a Sublime Text 2 plugin command that emulates
    the Emacs (fixup-whitespace) command: It collapses white space behind
    and ahead of the cursor, leaving just one space. For compatibility with
    Emacs, if the cursor is in the first column, this plugin leaves no spaces.
    Also for compatibility with Emacs, if the character at point is not a
    white space character, the plugin inserts one.
    '''

    def run(self, edit):
        sel = self.view.sel()
        if (sel is None) or (len(sel) == 0):
            return

        # Determine whether there's white space at the cursor.

        cursor_region = sel[0]
        point = cursor_region.begin()
        line = self.view.line(point)
        cur = self.view.substr(point)
        prev = self.view.substr(point - 1) if point > line.begin() else u'\x00'

        if prev.isspace():
            prefix_ws_region = self._handle_prefix_whitespace(point, line)
        else:
            prefix_ws_region = None

        if cur.isspace() and (not self._line_end(cur)):
            suffix_ws_region = self._handle_suffix_whitespace(point, line)
        else:
            suffix_ws_region = None

        if (suffix_ws_region is None) and (prefix_ws_region is None):
            # We're not on white space. Insert a blank.
            self.view.insert(edit, point, ' ')
        else:
            # Now do the actual delete.
            if suffix_ws_region is not None:
                self.view.erase(edit, suffix_ws_region)

            if prefix_ws_region is not None:
                self.view.erase(edit, prefix_ws_region)

            # Make sure there's one blank left, unless:
            #
            # a) the next character is not a letter or digit, or
            # b) the previous character is not a letter or digit, or
            # c) we're at the beginning of the line
            point = self.view.sel()[0].begin()
            bol = line.begin()
            if point > bol:
                def letter_or_digit(c):
                    return c.isdigit() or c.isalpha()

                c = self.view.substr(point)
                c_prev = self.view.substr(point - 1)

                if letter_or_digit(c) or letter_or_digit(c_prev):
                    self.view.insert(edit, point, ' ')

    def _handle_prefix_whitespace(self, point, line):
        p = point - 1
        c = self.view.substr(p)
        bol = line.begin()
        while (p > bol) and c.isspace():
            p -= 1
            c = self.view.substr(p)

        # "point" is now one character behind where we want it to be,
        # unless we're at the beginning of the line.
        if p > bol or (not c.isspace()):
            p += 1

        # Return the region of white space.
        return sublime.Region(p, point)

    def _handle_suffix_whitespace(self, point, line):
        p = point
        c = self.view.substr(p)
        eol = line.end()
        while (p <= eol) and (c.isspace()) and (not self._line_end(c)):
            p += 1
            c = self.view.substr(p)

        # Return the region of white space.
        return sublime.Region(point, p)

    def _line_end(self, c):
        return (c in ["\r", "\n", u'\x00'])


class SbpRegisterStore(sublime_plugin.TextCommand):
    '''
    Emacs style command allowing to store a certain value
    inside a global register.
    '''
    panel = None

    def run(self, edit):
        self.panel = self.view.window().show_input_panel("Store into register:", "", \
            self.on_done, \
            self.on_change,\
            self.on_cancel)

    def on_done(self, register):
        pass

    def on_cancel(self):
        pass

    def on_change(self, register):

        if self.panel == None:
            return

        self.panel.window().run_command("hide_panel")

        sel = self.view.sel()
        if (sel is None) or len(sel) != 1:
            return

        # Get the region
        sbp_registers.store(register, self.view.substr(sel[0]))
        self.view.run_command("sbp_cancel_mark")


class SbpRegisterInsert(sublime_plugin.TextCommand):
    """
    Simple command to insert the value stored in the register
    at the point that is currently active
    """

    panel = None

    def run(self, edit):
        self.panel = self.view.window().show_input_panel("Insert from register:", "", \
            None, \
            fu.partial(self.insert, edit),\
            None)

    def insert(self, edit, register):
        if not self.panel:
            return

        self.panel.window().run_command("hide_panel")

        sel = self.view.sel()
        if (sel is None) or len(sel) != 1:
            return

        begin = sel[0].begin()
        if register in sbp_registers:

            cnt = sbp_registers.get(register)
            self.view.replace(edit, sel[0], cnt)

            sel.clear()
            self.view.sel().add(begin + len(cnt))


class SbpOpenLineCommand(sublime_plugin.TextCommand):
    '''
    Emacs-style 'open-line' command: Inserts a newline at the current
    cursor position, without moving the cursor like Sublime's insert
    command does.
    '''
    def run(self, edit):
        sel = self.view.sel()
        if (sel is None) or (len(sel) == 0):
            return

        point = sel[0].end()
        self.view.insert(edit, point, '\n')
        self.view.run_command('move', {'by': 'characters', 'forward': False})


class SbpRecenterInView(sublime_plugin.TextCommand):
    '''
    Reposition the view so that the line containing the cursor is at the
    center of the viewport, if possible. Unlike the corresponding Emacs
    command, recenter-top-bottom, this command does not cycle through
    scrolling positions. It always repositions the view the same way.

    This command is frequently bound to Ctrl-l.
    '''
    def run(self, edit):
        self.view.show_at_center(self.view.sel()[0])


class SbpRectangleDelete(sublime_plugin.TextCommand):
    def run(self, edit, **args):
        sel = self.view.sel()[0]
        b_row, b_col = self.view.rowcol(sel.begin())
        e_row, e_col = self.view.rowcol(sel.end())

        # Create rectangle
        top = b_row
        left = min(b_col, e_col)

        bot = e_row
        right = max(b_col, e_col)

        # For each line in the region, replace the contents by what we
        # gathered from the overlay
        current_edit = self.view.begin_edit()
        for l in range(top, bot + 1):
            r = sublime.Region(self.view.text_point(l, left), self.view.text_point(l, right))
            if not r.empty():
                self.view.erase(current_edit, r)

        self.view.end_edit(edit)
        self.view.run_command("sbp_cancel_mark")


class SbpRectangleInsert(sublime_plugin.TextCommand):
    def run(self, edit, **args):
        self.view.window().show_input_panel("Content:", "", fu.partial(self.replace, edit), None, None)

    def replace(self, edit, content):

        sel = self.view.sel()[0]
        b_row, b_col = self.view.rowcol(sel.begin())
        e_row, e_col = self.view.rowcol(sel.end())

        # Create rectangle
        top = b_row
        left = min(b_col, e_col)

        bot = e_row
        right = max(b_col, e_col)

        # For each line in the region, replace the contents by what we
        # gathered from the overlay
        current_edit = self.view.begin_edit()
        for l in range(top, bot + 1):
            r = sublime.Region(self.view.text_point(l, left), self.view.text_point(l, right))
            if not r.empty():
                self.view.erase(current_edit, r)

            self.view.insert(current_edit, self.view.text_point(l, left), content)
        self.view.end_edit(edit)
        self.view.run_command("sbp_cancel_mark")

class SbpCycleFocusGroup(sublime_plugin.WindowCommand):
    def run(self):
        window = sublime.active_window()
        num = window.num_groups()
        active = window.active_group()
        if (num - 1) == active:
            next = 0
        else:
            next = active + 1
        window.focus_group(next)
