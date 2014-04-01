import functools as fu
import sublime
import sublime_plugin

# Handling the different imports in Sublime
if sublime.version() < '3000':
    # we are on ST2 and Python 2.X
    _ST3 = False
    import jove
else:
    _ST3 = True
    from . import jove

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
        self.panel = self.view.window().show_input_panel("Jump to point from register:", "", \
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
                point_data[0].run_command("jove_center_view")

class SbpRegisterStore(jove.SbpTextCommand):
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
        sbp_registers.store(register, self.view.substr(self.jove.get_region()))



class SbpRegisterDoInsert(jove.SbpTextCommand):

    def run_cmd(self, jove, content):
        sel = jove.get_point()
        jove.view.replace(jove.edit, sublime.Region(sel,sel) , content)
        jove.view.sel().clear()
        jove.view.sel().add(sublime.Region(sel + len(content), sel + len(content)))
        jove.view.window().focus_view(self.view)

class SbpRegisterInsert(jove.SbpTextCommand):
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

        self.view.window().run_command("sbp_register_do_insert", {"content": sbp_registers.get(register)})
