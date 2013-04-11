import functools as fu
import sublime
import sublime_plugin

try:
    import paragraph
except ImportError:
    import Default.paragraph as paragraph

def enum(**enums):
    return type('Enum', (), enums)

# Sublime 3 compatibility
try:
    import paragraph
except ImportError:
    import Default.paragraph as paragraph


class SbpSearchFocus:

    def __init__(self):
        self.value = False
        self.vid = -1

    def set(self, val, id):
        self.vid = id
        self.value = val

    def get(self):
        return self.vid, self.value

sbp_has_open_search = SbpSearchFocus()

# The goal of this event listener is to be able to close the search panel
# once we loose focus of the orignal search query
class HideSearchIfFocusLost(sublime_plugin.EventListener):

    def on_activated(self, view):
        pair = sbp_has_open_search.get()
        if pair[0] == view.id() and pair[1]:
            sbp_has_open_search.set(False, -1)
            view.window().run_command("hide_panel")

    def on_query_context(self, view, key, operator, operand, match_all):
        if key == "sbp_search_focus_check" and operand == True:
            self.status = True
            sbp_has_open_search.set(True, view.id())
            return True
        return None
    


class SbpMoveToParagraphCommand(sublime_plugin.TextCommand):

    def run(self, edit, forward):

        # Clear all selections
        s = self.view.sel()[0]
        if not forward:
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
sbp_point_register = SbpRegisterStore()


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


class SbpPointToRegister(sublime_plugin.TextCommand):
    ''' Stores the current selection, if it is a single selection, in a special
    register. This allows quick bookkeeping of positions in the document. However
    it stores as well the window and the region so that focussing from other
    windows is possible'''
    panel = None

    def run(self, edit):
        self.panel = self.view.window().show_input_panel("Store point into register:", "", \
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
        sbp_point_register.store(register, (self.view, self.view.window(), sel[0]))


# For some reason switching windows does not work and we can only switch to files
# in the current window
class SbpPointFromRegister(sublime_plugin.TextCommand):
    '''Restore the point from a register with a given command. This will focus the 
    point even if it comes from another window and view'''

    panel = None

    def run(self, edit):
        self.panel = self.view.window().show_input_panel("Jumpo to point from register:", "", \
            None, \
            fu.partial(self.insert, edit),\
            None)

    def insert(self, edit, register):
        if not self.panel:
            return

        self.panel.window().run_command("hide_panel")
        if register in sbp_registers:

            point_data = sbp_registers.get(register)
            point = point_data[2]

            point_data[0].sel().clear()
            point_data[0].sel().add(point)

            point_data[1].focus_group(0)
            point_data[1].focus_view(point_data[0])

            # Check if the point is in view, if not scroll to
            visible = point_data[0].visible_region()
            if not visible.contains(point):
                point_data[0].run_command("sbp_recenter_in_view")

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

################################################################################
# Centering View
################################################################################



# All Scroll Types
SCROLL_TYPES = enum(TOP=1, CENTER=0, BOTTOM=2)

class SbpRecenterInView(sublime_plugin.TextCommand):
    '''
    Reposition the view so that the line containing the cursor is at the
    center of the viewport, if possible. Like the corresponding Emacs
    command, recenter-top-bottom, this command cycles through
    scrolling positions.

    This command is frequently bound to Ctrl-l.
    '''

    last_sel = None
    last_scroll_type = None
    last_visible_region = None


    def rowdiff(self, start, end):
        r1,c1 = self.view.rowcol(start)
        r2,c2 = self.view.rowcol(end)
        return r2 - r1

    
    def run(self, edit):
        start = self.view.sel()[0]
        if start != SbpRecenterInView.last_sel:
            SbpRecenterInView.last_visible_region = None
            SbpRecenterInView.last_scroll_type = SCROLL_TYPES.CENTER
            SbpRecenterInView.last_sel = start
            self.view.show_at_center(SbpRecenterInView.last_sel)
            return
        else:
            SbpRecenterInView.last_scroll_type = (SbpRecenterInView.last_scroll_type + 1) % 3

        SbpRecenterInView.last_sel = start
        if SbpRecenterInView.last_visible_region == None:
            SbpRecenterInView.last_visible_region = self.view.visible_region()

        # Now Scroll to position
        if SbpRecenterInView.last_scroll_type == SCROLL_TYPES.CENTER:
            self.view.show_at_center(SbpRecenterInView.last_sel)
        elif SbpRecenterInView.last_scroll_type == SCROLL_TYPES.TOP:
            row,col = self.view.rowcol(SbpRecenterInView.last_visible_region.end())
            diff = self.rowdiff(SbpRecenterInView.last_visible_region.begin(), SbpRecenterInView.last_sel.begin())
            self.view.show(self.view.text_point(row + diff-2, 0), False)
        elif SbpRecenterInView.last_scroll_type == SCROLL_TYPES.BOTTOM:
            row, col = self.view.rowcol(SbpRecenterInView.last_visible_region.begin())
            diff = self.rowdiff(SbpRecenterInView.last_sel.begin(), SbpRecenterInView.last_visible_region.end())
            self.view.show(self.view.text_point(row - diff+2, 0), False)            


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
        current_edit = edit
        for l in range(top, bot + 1):
            r = sublime.Region(self.view.text_point(l, left), self.view.text_point(l, right))
            if not r.empty():
                self.view.erase(current_edit, r)

        self.view.end_edit(edit)
        self.view.run_command("sbp_cancel_mark")


class SbpRectangleInsertHandler(sublime_plugin.TextCommand):

    def run(self, edit, content):
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
        current_edit = edit#self.view.begin_edit()
        for l in range(top, bot + 1):
            r = sublime.Region(self.view.text_point(l, left), self.view.text_point(l, right))
            if not r.empty():
                self.view.erase(current_edit, r)

            self.view.insert(current_edit, self.view.text_point(l, left), content)
        self.view.end_edit(edit)
        self.view.run_command("sbp_cancel_mark")


class SbpRectangleInsert(sublime_plugin.TextCommand):
    def run(self, edit, **args):
        self.view.window().show_input_panel("Content:", "", self.replace, None, None)

    def replace(self, content):
        self.view.run_command("sbp_rectangle_insert_handler", {"content": content})

        

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



class SbpZapToCharEdit(sublime_plugin.TextCommand):

    def run(self, edit, begin, end):
        self.view.erase(edit, sublime.Region(int(begin), int(end)))


class SbpZapToChar(sublime_plugin.TextCommand):

    panel = None

    def run(self, edit, **args):
        self.edit = edit
        self.panel = self.view.window().show_input_panel("Zap To Char:", "", self.zap, self.on_change, None)

    def on_change(self, content):
        """Search forward from the current selection to the next ocurence
        of char"""

        if self.panel == None:
            return

        self.panel.window().run_command("hide_panel")

        sel = self.view.sel()
        if (sel is None) or len(sel) != 1:
            return

        sel = sel[0]

        # Convert to point
        new_sel = sel.begin()
        found = False
        while not found and new_sel < self.view.size():
            data = self.view.substr(new_sel)
            if data == content:
                found = True
                break
            new_sel += 1
        
        # Zap to char
        if found:
            self.view.run_command("sbp_zap_to_char_edit", {"begin": sel.begin(), "end": new_sel + 1})
            self.view.run_command("sbp_cancel_mark")
        else:
            sublime.status_message("Character %s not found" % content)

    def zap(self, content):
       pass