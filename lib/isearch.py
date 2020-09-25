#####################################################
#            Better incremental search              #
#####################################################

import re
from copy import copy

import sublime, sublime_plugin

from .misc import *

# Region names we use for i-search. Using our own names means that there is no interference from
# Sublime in terms of messages it displays regarding regions and matches, etc.
REGION_FIND = "rf"
REGION_SELECTED = "rs"

# preserved isearch settings
isearch_history_settings = None
ISEARCH_SETTINGS_FILE = "sublemacspro_isearch_history.sublime-settings"

# ring buffer of saved searches - actual values loaded from settings
isearch_history_size = 64

# most recently added item
isearch_current = 0

# most recently accessed via up/down arrows
isearch_index = 0

def initialize():
    global isearch_history_settings, isearch_history, isearch_current, isearch_history_size

    isearch_history_size = SettingsHelper().get("sbp_isearch_history_size", 64)

    isearch_history_settings = sublime.load_settings(ISEARCH_SETTINGS_FILE)
    if isearch_history_settings.get("isearch_current") is None:
        isearch_history_settings.set("isearch_current", 0)
        isearch_history = [None] * isearch_history_size
        isearch_history_settings.set("items", isearch_history)
    else:
        isearch_current = isearch_history_settings.get("isearch_current")
        isearch_history = isearch_history_settings.get("items")
        if len(isearch_history) > isearch_history_size:
            isearch_history = isearch_history[:isearch_history_size]
            save_search_settings()
        elif len(isearch_history) < isearch_history_size:
            isearch_history = isearch_history + [None] * (isearch_history_size - len(isearch_history))
            save_search_settings()


isearch_info = dict()
def info_for(view):
    if isinstance(view, sublime.Window):
        window = view
    else:
        window = view.window()
    if window:
        info = isearch_info.get(window.id(), None)
        if info is not None and not info.is_valid():
            info.finish(abort=False, input_panel_hack=True)
            info = None
        return info
    return None
def set_info_for(view, info):
    window = view.window()
    isearch_info[window.id()] = info
    return info
def clear_info_for(view):
    window = view.window()
    del(isearch_info[window.id()])

#
# Save the search string to the ring buffer if it's different from the most recent entry.
#
def save_search(search):
    global isearch_current, isearch_index
    current = isearch_history[(isearch_current - 1) % isearch_history_size]
    if search != current:
        isearch_history[isearch_current] = search
        isearch_current = (isearch_current + 1) % isearch_history_size

        # reset the index to the new current whenever one is added
        isearch_index = isearch_current
        save_search_settings()

def save_search_settings():
    isearch_history_settings.set("isearch_current", isearch_current)
    isearch_history_settings.set("items", isearch_history)
    sublime.save_settings(ISEARCH_SETTINGS_FILE)

#
# Get the most recently saved search string.
#
def get_saved_search():
    return isearch_history[(isearch_current - 1) % isearch_history_size]

#
# Cycle through history searching for the next search string.
#
def cycle_history(dir):
    global isearch_index
    start = isearch_index
    while True:
        isearch_index = (isearch_index + dir) % isearch_history_size
        if isearch_index == start:
            return None
        if isearch_history[isearch_index] is not None:
            return isearch_history[isearch_index]

class ISearchInfo():
    def __init__(self, view, forward, regex):
        self.view = view
        self.current = StackItem("", [], [], -1, forward, False)
        self.util = CmdUtil(view)
        self.window = view.window()
        self.point = self.util.get_cursors(True)
        self.input_view = None
        self.in_changes = 0
        self.forward = forward
        self.regex = regex

        # This helps us treat a series of individual characters appended at once with Ctrl-W as a
        # single item when deleting, if desired. This way we support adding a whole word with ctrl-w
        # and then deleting one character, OR, adding a whole word and then deleting it all at once.
        self.append_group_id = 1
        self.in_append_from_cursor = False

        # REMIND: this is to help us identify when the input panel has been taken over by someone
        # else
        self.view_change_count = 0

    def is_valid(self):
        if self.view_change_count != self.input_view.change_count():
            return False
        return True

    #
    # Restart the search.
    #
    def restart(self, text=""):
        item = self.current
        while item.prev != None:
            item = item.prev
        self.util.set_cursors(self.point)
        self.current = item
        if True or self.test_string(text):
            # REMIND: recreate the search one character at a time unless it's > 500, in which case
            # that can be quite slow
            self.in_append_from_cursor = True
            self.append_group_id += 1
            if len(text) < 1000:
                for index in range(0, len(text)):
                    self.on_change(text[0:index])
            else:
                self.on_change(text)
            self.in_append_from_cursor = False
        self.set_text(text, False)
        self.update()

    def open(self):
        window = self.view.window()
        in_error_str = "" if self.not_in_error() else "Failing "
        self.input_view = window.show_input_panel("%s%sI-Search:" % (in_error_str, "Regexp " if self.regex else ""),
                                                  "", self.on_done, self.on_change, self.on_cancel)
        self.view_change_count = self.input_view.change_count()

        # check if a single selection is present and if so, use it as the initial search string
        sel = self.view.sel()
        if len(sel) == 1:
            region = sel[0]
            init_text = self.view.substr(region)
            if len(init_text) > 0:
                self.point = [sublime.Region(region.begin())]
                self.restart(init_text)

                # when we start a search from the selection
                self.util.toggle_active_mark_mode(False)

    def on_done(self, val):
        # on_done: stop the search, keep the cursors intact
        self.finish(abort=False)

    def on_cancel(self):
        # on_done: stop the search, return cursor to starting point
        self.finish(abort=True)

    def on_change(self, val):
        if self.input_view is None:
            return
        self.view_change_count = self.input_view.change_count()
        if self.in_changes > 0:
            # When we pop back to an old state, we have to replace the search string with what was
            # in effect at that state. We do that by deleting all the text and inserting the value
            # of the search string. This causes this on_change method to be called. We want to
            # ignore it, which is what we're doing here.
            self.in_changes -= 1
            return

        if self.current and self.current.search == val:
            # sometimes sublime calls us when nothing has changed
            return

        self.find(val)

    def search_flags(self, search_string):
        # determine if this is case sensitive search or not
        flags = 0 if self.regex else sublime.LITERAL
        if not re.search(r'[A-Z]', search_string):
            flags |= sublime.IGNORECASE
        return flags

    #
    # Test a search string to see if it exists anywhere in the buffer.
    #
    def test_string(self, val):
        flags = self.search_flags(val)
        regions = self.view.find_all(val, flags)
        return len(regions) > 0

    def find(self, val):
        flags = self.search_flags(val)

        # find all instances if we have a search string
        if len(val) > 0:
            regions = self.view.find_all(val, flags)

            # find the closest match to where we currently are
            pos = None
            if self.current:
                pos = self.current.get_point()
            if pos is None:
                pos = self.point[-1].b
            index = self.find_closest(regions, pos, self.forward)

            # push this new state onto the stack
            group_id = self.append_group_id if self.in_append_from_cursor else None
            si = StackItem(val, regions, [], index, self.forward, self.current.wrapped, group_id)
            self.push(si)
        else:
            regions = None
            index = -1
        self.update()

    #
    # Push a new state onto the stack.
    #
    def push(self, item):
        item.prev = self.current
        self.current = item

    #
    # Pop one state of the stack and restore everything to the state at that time.
    #
    def pop(self, is_group=False):
        if not self.current.prev:
            return

        # TODO: when popping, skip over items that were not kept because it's a pain to rethink
        # all those ...

        if is_group and self.current.group_id is not None:
            id = self.current.group_id
            item = self.current.prev
            while item.prev and item.group_id == id:
                item = item.prev
        else:
            item = self.current.prev

        self.current = item
        self.set_text(self.current.search)
        self.forward = self.current.forward
        self.update()

    def hide_panel(self):
        # close the panel which should trigger an on_done
        window = self.view.window()
        if window:
            window.run_command("hide_panel")

    def done(self):
        self.finish()

    def history(self, dir):
        search = cycle_history(dir)
        if search:
            self.restart(search)

    #
    # INTERNAL FUNCTIONATITY BELOW
    #

    #
    # Set the text of the search to a particular value. If is_pop is True it means we're restoring
    # to a previous state. Otherwise, we want to pretend as though this text were actually inserted.
    #
    def set_text(self, text, is_pop=True):
        if is_pop:
            self.in_changes += 1
        v = self.input_view
        self.input_view.run_command("sbp_inc_search", {"cmd": "set_search", "text": text})

    #
    # Find the most recent stack item where we were not in the error state.
    #
    def not_in_error(self):
        si = self.current
        while si and not si.selected and si.search:
            si = si.prev
        return si

    def finish(self, abort=False, input_panel_hack=False):
        util = self.util
        if not input_panel_hack and info_for(self.view) != self:
            return
        if self.current and self.current.search:
            save_search(self.current.search)
        util.set_status("", False)
        util.toggle_active_mark_mode(False)

        point_set = False
        if not abort:
            selection = self.view.sel()
            selection.clear()
            current = self.current
            not_in_error = self.not_in_error()
            if current and current.selected:
                if not current.forward:
                    # put the cursor at the front of the each region
                    selected = (sublime.Region(s.b, s.a) for s in current.selected)
                else:
                    selected = current.selected
                selection.add_all(selected)
                point_set = True
            elif not_in_error and not_in_error.regions:
                selection.add_all([not_in_error.regions[not_in_error.current_index]])
                point_set = True

        if not point_set:
            # back whence we started
            util.set_cursors(self.point)
        else:
            util.set_mark(self.point, and_selection=False)

        # erase our regions
        self.view.erase_regions(REGION_FIND)
        self.view.erase_regions(REGION_SELECTED)
        clear_info_for(self.view)
        if not input_panel_hack:
            self.hide_panel()

    def update(self):
        current = self.current
        if current is None:
            return
        not_in_error = self.not_in_error()

        # figure out which of the input is NOT in error
        if not_in_error != current:
            scope = "markup.deleted.git_gutter"
        else:
            scope = "string"

        if not_in_error != current:
            # highlight the part of the search that is in error
            self.input_view.add_regions(REGION_FIND,
                                        [sublime.Region(len(not_in_error.search), len(current.search))],
                                        "text", "", sublime.DRAW_NO_OUTLINE)
        elif self.input_view is not None:
            # erase the error indicator
            self.input_view.add_regions(REGION_FIND, [], "text", "", sublime.DRAW_NO_OUTLINE)

        self.view.add_regions(REGION_FIND, current.regions, "text", "", sublime.DRAW_NO_FILL)
        selected = current.selected or (not_in_error.selected and [not_in_error.selected[-1]]) or []
        self.view.add_regions(REGION_SELECTED, selected, scope, "", sublime.DRAW_NO_OUTLINE)
        if selected:
            self.view.show(selected[-1])

        status = ""
        if current != not_in_error or current.try_wrapped:
            status += "Failing "
        if self.current.wrapped:
            status += "Wrapped "
        status += "I-Search " + ("Forward" if self.current.forward else "Reverse")
        if current != not_in_error:
            if len(self.current.regions) > 0:
                status += " %s %s" % (pluralize("match", len(self.current.regions), "es"), ("above" if self.forward else "below"))
        else:
            n_cursors = min(len(current.selected), len(current.regions))
            status += " %s, %s" % (pluralize("match", len(current.regions), "es"), pluralize("cursor", n_cursors))

        self.util.set_status(status, False)

    #
    # Try to make progress with the current search string. Even if we're currently failing (in our
    # current direction) it doesn't mean there aren't matches for what we've typed so far.
    #
    def next(self, keep, forward=None):
        if self.current.prev is None:
            # do something special if we invoke "i-search" twice at the beginning
            last_search = get_saved_search()
            if last_search is not None:
                self.restart(last_search)
        else:
            if forward is None:
                forward = self.current.forward
            new = self.current.step(forward=forward, keep=keep)
            if new:
                self.push(new)
            self.update()

    def keep_all(self):
        while self.current.regions and self.current.current_index < len(self.current.regions):
            new = self.current.step(forward=self.current.forward, keep=True)
            if new:
                self.push(new)
            else:
                break
        self.update()

    def append_from_cursor(self):
        # Figure out the contents to the right of the last region in the current selected state, and
        # append characters from there.
        si = self.current
        if len(si.search) > 0 and not si.selected:
            # search is failing - no point in adding from current cursor!
            return

        view = self.view
        limit = view.size()
        if si.selected:
            # grab end of most recent item
            point = si.selected[-1].end()
        else:
            point = self.point[0].b
        if point >= limit:
            return

        # now push new states for each character we append to the search string
        helper = self.util
        search = si.search
        separators = settings_helper.get("sbp_word_separators", default_sbp_word_separators)
        case_sensitive = re.search(r'[A-Z]', search) is not None

        self.in_append_from_cursor = True
        self.append_group_id += 1

        def append_one(ch):
            if not case_sensitive:
                ch = ch.lower()
            if self.regex and ch in "{}()[].*+":
                return "\\" + ch
            return ch

        if point < limit:
            # append at least one character, word character or not
            ch = view.substr(point)
            search += append_one(ch)
            point += 1
            self.on_change(search)

            # If we started on whitespace, and the next character is whitespace, consume all the
            # whitespace. Otherwise, if the next character is a word char, consume that word.
            # Otherwise, we're done.

            whitespace = '\t '

            if point < limit:
                if ch in whitespace and view.substr(point) in whitespace:
                    while point < limit:
                        ch = view.substr(point)
                        if ch not in whitespace:
                            break
                        search += append_one(ch)
                        self.on_change(search)
                        point += 1
                else:
                    # now insert word characters
                    while point < limit and helper.is_word_char(point, True, separators):
                        ch = view.substr(point)
                        search += append_one(ch)
                        self.on_change(search)
                        point += 1

        self.set_text(self.current.search)
        self.in_append_from_cursor = False

    def quit(self):
        close = False

        if self.current.regions:
            # if we have some matched regions, we're in "successful" state and close down the whole
            # thing
            close = True
        else:
            # here the search is currently failing, so we back up until the last non-failing state
            while self.current.prev and not self.current.prev.regions:
                self.current = self.current.prev
            if self.current.prev is None:
                close = True
        if close:
            self.finish(abort=True)
        else:
            self.pop()

    def find_closest(self, regions, pos, forward):
        #
        # The regions are sorted so clearly this would benefit from a simple binary search ...
        #
        if len(regions) == 0:
            return -1
        # find the first region after the specified pos
        found = False
        if forward:
            for index,r in enumerate(regions):
                if r.end() >= pos:
                    return index
            return -1
        else:
            for index,r in enumerate(regions):
                if r.begin() > pos:
                    return index - 1
            return len(regions) - 1

class StackItem():
    def __init__(self, search, regions, selected, current_index, forward, wrapped, group_id=None):
        self.prev = None
        self.search = search
        self.regions = regions
        self.selected = selected
        self.current_index = current_index
        self.forward = forward
        self.try_wrapped = False
        self.wrapped = wrapped
        self.group_id = group_id
        if current_index >= 0 and regions:
            # add the new one to selected
            selected.append(regions[current_index])

    def get_point(self):
        if self.current_index >= 0:
            r = self.regions[self.current_index]
            return r.begin() if self.forward else r.end()
        return None

    #
    # Clone is called when we want to make progress with the same search string as before.
    #
    def clone(self):
        return copy.copy(self)

    #
    # Go to the next match of the current string. Keep means "keep the current location as a
    # future cursor" and forward is True if we're moving forward.
    #
    def step(self, forward, keep):
        index = self.current_index
        matches = len(self.regions)
        if (self.regions and (index < 0 or (index == 0 and not forward) or (index == matches - 1) and forward)):
            # wrap around!
            index = 0 if forward else matches - 1
            if self.try_wrapped or not self.regions:
                wrapped = True
                self.try_wrapped = False
            else:
                self.try_wrapped = True
                return None
        elif (forward and index < matches - 1) or (not forward and index > 0):
            index = index + 1 if forward else index - 1
            wrapped = self.wrapped
        else:
            return None
        selected = copy(self.selected)
        if not keep and len(selected) > 0:
            del(selected[-1])
        return StackItem(self.search, self.regions, selected, index, forward, wrapped)
