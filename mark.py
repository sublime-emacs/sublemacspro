import sublime, sublime_plugin

# Remove any existing marks
#
class CancelMarkCommand(sublime_plugin.TextCommand):
  def run(self, edit, **args):


    m = self.view.get_regions("mark")
    if m:
        self.view.erase_regions("mark")

        self.view.sel().clear()
        self.view.sel().add(sublime.Region(m[0].end(), m[0].end()))


class SetMarkCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        mark = [s for s in self.view.sel()]
        self.view.add_regions("mark", mark, "mark", "dot",
            sublime.HIDDEN | sublime.PERSISTENT)

class SwapWithMarkCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        old_mark = self.view.get_regions("mark")

        mark = [s for s in self.view.sel()]
        self.view.add_regions("mark", mark, "mark", "dot",
            sublime.HIDDEN | sublime.PERSISTENT)

        if len(old_mark):
            self.view.sel().clear()
            for r in old_mark:
                self.view.sel().add(r)

class SelectToMarkCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        mark = self.view.get_regions("mark")

        num = min(len(mark), len(self.view.sel()))

        regions = []
        for i in xrange(num):
            regions.append(self.view.sel()[i].cover(mark[i]))

        for i in xrange(num, len(self.view.sel())):
            regions.append(self.view.sel()[i])

        self.view.sel().clear()
        for r in regions:
            self.view.sel().add(r)

class DeleteToMark(sublime_plugin.TextCommand):
    def run(self, edit):
        self.view.run_command("select_to_mark")
        self.view.run_command("add_to_kill_ring", {"forward": False})
        self.view.run_command("left_delete")

#
# If a mark has been set, color the region between the mark and the point
#
class EmacsMarkDetector(sublime_plugin.EventListener):
  
  def __init__(self, *args, **kwargs):
    sublime_plugin.EventListener.__init__(self, *args, **kwargs)

  # When text is modified, we cancel the mark.
  def on_modified(self, view):    
    #view.erase_regions("mark")
    pass
    
  def on_selection_modified(self, view):
    mark = view.get_regions("mark")

    num = min(len(mark), len(view.sel()))

    regions = []
    for i in xrange(num):
      regions.append(view.sel()[i].cover(mark[i]))

    for i in xrange(num, len(view.sel())):
      regions.append(view.sel()[i])

    view.sel().clear()
    for r in regions:
      view.sel().add(r)
      
  def on_query_context(self, view, key, operator, operand, match_all):    
    if key == "emacs_has_mark":
      if operator == sublime.OP_EQUAL:
        return len(view.get_regions("mark")) > 0
