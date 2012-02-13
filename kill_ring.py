import sublime_plugin, sublime, functools

class KillRing:
    def __init__(self):
        self.limit = 16
        self.buffer = []
        self.kill_points = []
        self.kill_id = 0

    def top(self):
        return self.buffer[self.head]

    def seal(self):
        self.kill_points = []
        self.kill_id = 0

    def push(self, text):
        self.buffer.insert(0, text)
        if len(self.buffer) > self.limit:
            self.buffer.pop()

    def add(self, view_id, text, regions, forward):
        if view_id != self.kill_id:
            # view has changed, ensure the last kill ring entry will not be
            # appended to
            self.seal()

        begin_points = []
        end_points = []
        for r in regions:
            begin_points.append(r.begin())
            end_points.append(r.end())

        if forward:
            compare_points = begin_points
        else:
            compare_points = end_points

        if compare_points == self.kill_points:
            # Selection hasn't moved since the last kill, append/prepend the
            # text to the current entry
            if forward:
                self.buffer[self.head] = self.buffer[self.head] + text
            else:
                self.buffer[self.head] = text + self.buffer[self.head]
        else:
            # Create a new entry in the kill ring for this text
            self.push(text)

        self.kill_points = begin_points
        self.kill_id = view_id

    def get(self, index):
        return self.buffer[index % self.limit]

    def __len__(self):
        return len(self.buffer)

kill_ring = KillRing()

class YankChoiceCommand(sublime_plugin.TextCommand):
    
    def insert(self, edit, idx):

        if idx == -1:
            return

        regions = [r for r in self.view.sel()]
        regions.reverse()

        text = kill_ring.get(idx)
        for s in regions:
            num = self.view.insert(edit, s.begin(), text)
            self.view.erase(edit, sublime.Region(s.begin() + num,
                s.end() + num))


    def run(self, edit):
        names = [kill_ring.get(idx) for idx in range(len(kill_ring)) if kill_ring.get(idx) != None]
        if len(names) > 0:
            self.view.window().show_quick_panel(names, functools.partial(self.insert, edit))
        


class YankCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        text = kill_ring.top()
        lines = text.splitlines()

        regions = [r for r in self.view.sel()]
        regions.reverse()

        if len(regions) > 1 and len(regions) == len(lines):
            # insert one line from the top of the kill ring at each
            # corresponding selection
            for i in xrange(len(regions)):
                s = regions[i]
                line = lines[i]
                num = self.view.insert(edit, s.begin(), line)
                self.view.erase(edit, sublime.Region(s.begin() + num,
                    s.end() + num))
        else:
            # insert the top of the kill ring at each selection
            for s in regions:
                num = self.view.insert(edit, s.begin(), text)
                self.view.erase(edit, sublime.Region(s.begin() + num,
                    s.end() + num))

    def is_enabled(self):
        return len(kill_ring) > 0

class AddToKillRingCommand(sublime_plugin.TextCommand):
    def run(self, edit, forward):
        delta = 1
        if not forward:
            delta = -1

        text = []
        regions = []
        for s in self.view.sel():
            if s.empty():
                s = sublime.Region(s.a, s.a + delta)
            text.append(self.view.substr(s))
            regions.append(s)

        kill_ring.add(self.view.id(), "\n".join(text), regions, forward)

class KillRingSaveCommand(sublime_plugin.TextCommand):
  def run(self, edit, **args):
    self.view.run_command("add_to_kill_ring", {"forward": False})
    self.view.run_command("cancel_mark")




#
# Kill Line
#
class KillLineCommand(sublime_plugin.TextCommand):

    def expandSelectionForKill(self, view, begin, end):
        """Returns a selection that will be cut; basically,
        the 'select what to kill next' command."""

        # the emacs kill-line command either cuts
        # until the end of the current line, or if
        # the cursor is already at the end of the
        # line, will kill the EOL character. Will
        # not do anything at EOF

        if  atEOL(view, end):
            # select the EOL char
            selection = sublime.Region(begin, end+1)
            return selection

        elif atEOF(view, end):
            # at the end of file, do nothing; the
            # selection is just the initial selection
            return sublime.Region(begin, end)

        else:
            # mid-string -- extend to EOL
            current = end
            while not atEOF(view, current) and not atEOL(view, current):
                current = current+1
            selection = sublime.Region(begin,current)
            return selection

    def atEOL(view, point):
        nextChar = view.substr(point)
        return  nextChar == "\n"

    def atEOF(view, point):
        nextChar = view.substr(point)
        return ord(nextChar) == 0

    def isEnabled(self, edit, args):
        if len(self.view.sel()) != 1:
            return False

        # if we are at the end of the file, we can't kill.
        s = self.view.sel()[0]
        charAfterPoint = self.view.substr(s.end())
        if ord(charAfterPoint) == 0:
            # EOF
            return False

        return True

    def run(self, edit, **args):
        global kill_ring

        s = self.view.sel()[0]
        expanded = self.expandSelectionForKill(self.view, s.begin(), s.end())
        self.view.sel().clear()
        self.view.sel().add(expanded)
        self.view.run_command("add_to_kill_ring", {"forward": False})
        self.view.erase(edit, expanded)
