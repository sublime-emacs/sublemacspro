import functools as fu
import sublime
import sublime_plugin

from .lib.misc import *

class SbpRectangleDelete(SbpTextCommand):
  """
  Deletes the content of a given rectangle, content is not saved to kill ring
  and cannot be pasted
  """
  def run_cmd(self, jove, **args):
    region = jove.get_encompassing_region()

    if not region:
        return

    # get the beginning and end of the region
    b_row, b_col = self.view.rowcol(region.begin())
    e_row, e_col = self.view.rowcol(region.end())

    # Create rectangle
    top = b_row
    left = min(b_col, e_col)

    bot = e_row
    right = max(b_col, e_col)

    current_edit = jove.edit
    for l in range(top, bot + 1):
        r = sublime.Region(self.view.text_point(l, left), self.view.text_point(l, right))
        if not r.empty():
            self.view.erase(current_edit, r)

    self.view.end_edit(jove.edit)


class SbpRectangleInsertHandler(SbpTextCommand):
  """
  executes the actual insert from the rectangle
  """

  def run_cmd(self, jove, content):
    region = jove.get_encompassing_region()
    if not region:
        return

    # get the beginning and end of the region
    b_row, b_col = self.view.rowcol(region.begin())
    e_row, e_col = self.view.rowcol(region.end())

    # Create rectangle
    top = b_row
    left = min(b_col, e_col)

    bot = e_row
    right = max(b_col, e_col)

    # For each line in the region, replace the contents by what we
    # gathered from the overlay
    current_edit = jove.edit
    for l in range(top, bot + 1):
      r = sublime.Region(self.view.text_point(l, left), self.view.text_point(l, right))
      if not r.empty():
        self.view.erase(current_edit, r)
      self.view.insert(current_edit, self.view.text_point(l, left), content)
    self.view.end_edit(jove.edit)


class SbpRectangleInsert(SbpTextCommand):
  """
  Given a rectangle insert the text at points
  """
  def run_cmd(self, jove, **args):
    self.jove = jove
    self.view.window().show_input_panel("Content:", "", self.replace, None, None)

  def replace(self, content):
    self.jove.view.run_command("sbp_rectangle_insert_handler", {"content": content})
