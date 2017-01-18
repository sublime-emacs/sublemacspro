import functools as fu
import sublime
import sublime_plugin
import re

from .lib.misc import *

class SbpRegisterStore:
    """
    Base class to store data for the registers, could be a plain dict,
    but we make it more complicated by wrapping the dict :)
    """
    registers = {}

    # If you want seperate text and point registers enabling mapping to the same keys
    # delete the global registers and uncomment the code below
    # def __init__(self):
    #     self.registers = {}

    def get(self, key):
        if not key in self.registers:
            return ""
        else:
            return self.registers[key]

    def format_for_popup(self, text):
        # stripe newlines, spaces and tabs from the beginning and end
        text = text.strip("\n \t")

        # collapse multiple newlines into a single and convert to a glyph
        # text = re.sub("\n+", "↩", text)
        # text = re.sub("\n+", "\u23ce", text)
        text = re.sub("\n+", "\u00b6", text)

        # replace multiple white space with single spaces within the string
        text = re.sub("\\s\\s+", " ", text)

        # Old formatting before using glyphs
        # text = text.strip("\n \t").replace("\n", " \\n")
        # text = re.sub("(\s\\\\n)+"," \\\\n", text)
        # text = re.sub("\\s\\s+", " ", text)

        return text

    def truncate_for_popup(self, view, text, reg_type):
        # Detect width of viewport and modify output text accordingly for better viewing
        # 3 subtracted because the beginning of each registers is like (a: ) before the start of
        # the text
        #
        max_chars = (view.viewport_extent()[0] / view.em_width()) * .9 - 3

        # truncate text registers showing half of the beginning and end portion
        # for point registers just show the beginning portion where the jump will occur too
        if len(text) > max_chars and reg_type == "text":
            half = int(max_chars / 2)
            text = text[:half] + "\u27FA" + text[-half:] + "   "
        else:
            text = text[:int(max_chars)] + "   "

        return text

    def get_point_registers(self):
        items = []
        for item in self.registers.items():
            if item[1][0] is not None:
                items.append([item[0],self.format_for_popup(item[1][3])])
        return items

    def get_text_registers(self):
        items = []
        for item in self.registers.items():
            if item[1][0] is None:
                items.append([item[0],self.format_for_popup(item[1][3])])
        return items

    # TODO: Clear all text registers or point registers
    # TODO: Possibly use pop-up to delete registers if easy


    def store(self, key, val):
        self.registers[key] = val

    def  __contains__(self, key):
        return key in self.registers

# Global variable to store data in the registers
sbp_text_registers = SbpRegisterStore()
sbp_point_registers = SbpRegisterStore()

class SbpPointToRegister(SbpTextCommand):
    ''' Stores the current selection, if it is a single selection, in a special
    register. This allows quick bookkeeping of positions in the document. However
    it stores as well the window and the region so that focussing from other
    windows is possible'''
    panel = None

    def run_cmd(self, jove):
        self.jove = jove
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
        line = self.view.line(sel[0])
        line_substr = ''
        if (sel is None) or len(sel) != 1:
            return

        # grab first four lines below the current line for viewing of jump
        for i in range(4):
            line_substr += self.view.substr(line) + '\n'
            line = self.view.line(line.end()+2)

        sbp_point_registers.store(register, (self.view, self.view.window(), sel[0],
            line_substr))


class SbpJumpToPoint:
    def jump(point_data):
        point = point_data[2]

        point_data[0].sel().clear()
        point_data[0].sel().add(point)

        point_data[1].focus_group(0)
        point_data[1].focus_view(point_data[0])

        # Check if the point is in view, if not scroll to
        visible = point_data[0].visible_region()
        if not visible.contains(point):
            point_data[0].run_command("jove_center_view")

# For some reason switching windows does not work and we can only switch to files
# in the current window
class SbpPointFromRegister(sublime_plugin.TextCommand):
    '''Restore the point from a register with a given command. This will focus the
    point even if it comes from another window and view'''

    panel = None

    def run(self, edit, register = None):
        if register in sbp_point_registers:
            self.insert(edit, register)
        else:
            self.panel = self.view.window().show_input_panel("Jump to point from register:", "", \
            None, \
            fu.partial(self.insert, edit),\
            None)

    def insert(self, edit, register):
        if not self.panel:
            return

        self.panel.window().run_command("hide_panel")

        if register in sbp_point_registers:
            SbpJumpToPoint.jump(sbp_point_registers.get(register))

class SbpRegisterStore(SbpTextCommand):
    '''
    Emacs style command allowing to store a certain value
    inside a global register.
    '''
    panel = None

    def run_cmd(self, jove):
        self.jove = jove
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
        sbp_text_registers.store(register, (None, None, None, self.view.substr(self.jove.get_encompassing_region())))



class SbpRegisterDoInsert(SbpTextCommand):

    def run_cmd(self, jove, content):
        sel = jove.get_point()
        jove.view.replace(jove.edit, sublime.Region(sel, sel), content)
        jove.view.sel().clear()
        jove.view.sel().add(sublime.Region(sel + len(content), sel + len(content)))
        jove.view.window().focus_view(self.view)

class SbpRegisterInsert(SbpTextCommand):
    """
    Simple command to insert the value stored in the register
    at the point that is currently active
    """

    panel = None

    def run_cmd(self, jove):
        self.panel = self.view.window().show_input_panel("Insert from register:", "", \
            None, \
            self.insert,\
            None)

    def insert(self, register):
        if not self.panel:
            return

        self.panel.window().run_command("hide_panel")

        sel = self.view.sel()
        if (sel is None) or len(sel) != 1:
            return

        self.view.window().run_command("sbp_register_do_insert", {"content": sbp_text_registers.get(register)[3]})

class SbpChooseAndYankRegister(SbpTextCommand):

    def run_cmd(self, util):
        # items is an array of (index, text) pairs
        items = sbp_text_registers.get_text_registers()

        def on_done(idx):
            if idx >= 0:
                util.run_command("sbp_register_do_insert", {"content": sbp_text_registers.get(items[idx][0])[3]})

        # To pass in for truncation of display strings
        view      = self.view

        if items:
            sublime.active_window().show_quick_panel([item[0] + ": " + sbp_text_registers.truncate_for_popup(view, item[1], "text") for item in items], on_done)
        else:
            sublime.status_message('Nothing in history')
class SbpChooseAndYankPoint(SbpTextCommand):

    def run_cmd(self, util):
        # items is an array of (index, text) pairs
        items = sbp_point_registers.get_point_registers()

        def on_done(idx):
            if idx >= 0:
                SbpJumpToPoint.jump(sbp_point_registers.get(items[idx][0]))

        # To pass in for truncation of display strings
        view      = self.view

        if items:
            sublime.active_window().show_quick_panel([item[0] + ": " + sbp_point_registers.truncate_for_popup(view, item[1], "point") for item in items], on_done)
        else:
            sublime.status_message('Nothing in history')
        # if items:
        #     sublime.active_window().show_quick_panel([item[0] + ": " + item[1][:viewTextLength] for item in items], on_done)
        # else:
        #     sublime.status_message('Nothing in history')
