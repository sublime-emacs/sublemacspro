"""
Emacs-style kill ring (and yank ring) commands.

Settings:

sbp_kill_with_copy - If true, kill or yank also performs an editor copy
    (as if Ctrl-C, or Cmd-C on the Mac, had been pressed). If false, kill does
    NOT perform a copy. The default is "true", which better mimics Emacs'
    behavior. The setting allows you to disable the behavior, if you don't like
    it.
"""

import sublime_plugin
import sublime
import functools
import string


class SbpUtil:
    # FIXME: Move to someplace common.

    @classmethod
    def atEOL(cls, view, point):
        nextChar = view.substr(point)
        return  nextChar == "\n"

    @classmethod
    def atEOF(cls, view, point):
        nextChar = view.substr(point)
        return ord(nextChar) == 0

    @classmethod
    def add_to_kill_ring(cls, view):
        # kill_with_copy setting enables editor copy when kill (C-w)
        # or Emacs-copy (M-w) is invoked.
        kill_with_copy = view.settings().get("sbp_kill_with_copy", True)
        if kill_with_copy:
            view.run_command("copy")
        view.run_command("sbp_add_to_kill_ring", {"forward": False})


class SbpKillRing:
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
        """This method pushes the string to the kill ring.

        However, we do need some kind of sanitation to make sure
        we don't push too many white spaces."""

        sanitized = string.strip(text)
        if len(sanitized) == 0:
            return

        self.buffer.insert(0, sanitized)
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

sbp_kill_ring = SbpKillRing()


class SbpYankChoiceCommand(sublime_plugin.TextCommand):

    def insert(self, edit, idx):

        if idx == -1:
            return

        regions = [r for r in self.view.sel()]
        regions.reverse()

        text = sbp_kill_ring.get(idx)
        for s in regions:
            num = self.view.insert(edit, s.begin(), text)
            self.view.erase(edit, sublime.Region(s.begin() + num,
                s.end() + num))

    def run(self, edit):
        names = [sbp_kill_ring.get(idx) for idx in range(len(sbp_kill_ring)) if sbp_kill_ring.get(idx) != None]
        if len(names) > 0:
            self.view.window().show_quick_panel(names, functools.partial(self.insert, edit))


class SbpYankCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        text = sbp_kill_ring.top()
        lines = text.splitlines()

        regions = [r for r in self.view.sel()]
        regions.reverse()

        if len(regions) > 1 and len(regions) == len(lines):
            # insert one line from the top of the kill ring at each
            # corresponding selection
            for i in range(len(regions)):
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
        return len(sbp_kill_ring) > 0


class SbpAddToKillRingCommand(sublime_plugin.TextCommand):
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

        sbp_kill_ring.add(self.view.id(), "\n".join(text), regions, forward)


class SbpKillRingSaveCommand(sublime_plugin.TextCommand):
    def run(self, edit, **args):
        SbpUtil.add_to_kill_ring(self.view)
        self.view.run_command("sbp_cancel_mark")


class SbpKillToEndOfSentence(sublime_plugin.TextCommand):
    """
    SbpKillToEndOfSentence is the equivalent of the Emacs (kill-sentence)
    command, typically bound to M-k. It kills from point to the end of the
    current sentence. "Current sentence" is defined as either (a) end of file,
    or (b) a space preceded by ".", "?" or "!".
    """
    def run(self, edit):
        s = self.view.sel()[0]
        region = self._sentence_region(self.view, s.begin())
        self.view.sel().clear()
        self.view.sel().add(region)
        SbpUtil.add_to_kill_ring(self.view)
        self.view.erase(edit, region)

    def _sentence_region(self, view, point):
        last_was_punct = False
        begin = end = point

        while not SbpUtil.atEOF(self.view, end):
            c = self.view.substr(end)
            if c in ['.', '!', '?']:
                last_was_punct = True

            elif c.isspace():
                if last_was_punct:
                    break
                last_was_punct = False

            else:
                last_was_punct = False

            end += 1

        if end > begin:
            return sublime.Region(begin, end)
        else:
            return None


#
# Kill Line
#
class SbpKillLineCommand(sublime_plugin.TextCommand):

    def expandSelectionForKill(self, view, begin, end):
        """Returns a selection that will be cut; basically,
        the 'select what to kill next' command."""

        # the emacs kill-line command either cuts
        # until the end of the current line, or if
        # the cursor is already at the end of the
        # line, will kill the EOL character. Will
        # not do anything at EOF

        if  self.atEOL(view, end):
            # select the EOL char
            selection = sublime.Region(begin, end + 1)
            return selection

        elif self.atEOF(view, end):
            # at the end of file, do nothing; the
            # selection is just the initial selection
            return sublime.Region(begin, end)

        else:
            # mid-string -- extend to EOL
            current = end
            while not self.atEOF(view, current) and not self.atEOL(view, current):
                current = current + 1
            selection = sublime.Region(begin, current)
            return selection

    def atEOL(self, view, point):
        return SbpUtil.atEOL(view, point)

    def atEOF(self, view, point):
        return SbpUtil.atEOF(view, point)

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
        global sbp_kill_ring

        s = self.view.sel()[0]
        expanded = self.expandSelectionForKill(self.view, s.begin(), s.end())
        self.view.sel().clear()
        self.view.sel().add(expanded)
        SbpUtil.add_to_kill_ring(self.view)
        self.view.erase(edit, expanded)
