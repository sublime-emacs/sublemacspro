import re
import sublime, sublime_plugin
from .misc import SettingsHelper

# initialized below
kill_ring_size = kill_index = pop_index = entries = None

#
# Called from JOVE when the plugin has loaded.
#
def initialize():
    global kill_ring, kill_ring_size, kill_index, pop_index, entries

    settings_helper = SettingsHelper()

    # kill ring size - default 64 entries
    kill_ring_size = settings_helper.get("sbp_kill_ring_size", 64)

    entries = [None] * kill_ring_size
    kill_index = 0

#
# Add some text to the kill ring. 'forward' indicates whether the editing command that produced
# this data was in the forward or reverse direction. It only matters if 'join' is true, because
# it tells us how to add this data to the most recent kill ring entry rather than creating a new
# entry.
#
def add(regions, forward, join):
    global kill_index

    total_bytes = sum((len(c) for c in regions))

    if total_bytes == 0:
        return
    try:
        if not join:
            # if the current item is the same as what we're trying to kill, don't bother
            if entries[kill_index] and entries[kill_index].same_as(regions):
                return
        else:
            # try to join
            if entries[kill_index] and entries[kill_index].join_if_possible(regions, forward):
                return

        # create the new entry
        kill_index = (kill_index + 1) % kill_ring_size
        entries[kill_index] = Kill(regions)
    finally:
        set_current(kill_index)

#
# Returns a sample of the first region of each entry in the kill ring, so that it can be
# displayed to the user to allow them to choose it. The sample is truncated unfortunately.
#
def get_popup_sample(view):
    add_external_clipboard()

    index = kill_index
    result = []
    seen = {}
    while True:
        kill = entries[index]
        if kill:
            text = kill.get_sample(view)
            if text not in seen:
                result.append((index, text))
                seen[text] = True
        index = (index - 1) % kill_ring_size
        if index == kill_index:
            break
    return result

#
# Sets the current kill ring index. Normally this is managed within this file, but choose and yank
# sets the index to the chosen index from the overlay.
#
def set_current(index):
    global kill_index

    if entries[index]:
        kill_index = index
        entries[index].set_clipboard()

#
# Add the external clipboard to the kill ring, if appropriate. And return it if we do.
#
def add_external_clipboard():
    # first check to see whether we bring in the clipboard
    index = kill_index
    entry = entries[index]
    clipboard = sublime.get_clipboard()

    if clipboard and (entry is None or not entry.matches_clipboard()):
        # We switched to another app and cut or copied something there, so add the clipboard
        # to our kill ring.
        result = [clipboard]
        add(result, True, False)
        return result
    return None

#
# Returns the current entry in the kill ring for the purposes of yanking. If pop is non-zero, we
# move backwards or forwards once in the kill ring and return that data instead. If the number
# of regions doesn't match, we either truncate or duplicate the regions to make a match.
#
# If n_regions is 0, the caller doesn't care how many regions there are: just return them all.
#
def get_current(n_regions, pop):
    global pop_index

    clipboard = result = None
    if pop == 0:
        index = kill_index
        entry = entries[index]

        # grab the external clipboard if available
        result = add_external_clipboard()
        if not result:
            result = entry.regions
        pop_index = None
    else:
        if pop_index is None:
            pop_index = kill_index

        incr = -1 if pop > 0 else 1
        index = (pop_index + incr) % kill_ring_size
        while entries[index] is None:
            if index == pop_index:
                return None
            index = (index + incr) % kill_ring_size

        pop_index = index
        result = entries[index].regions
        entries[index].set_clipboard()

    # Make sure we have enough data for the specified number of regions, duplicating regions until
    # we meet the requested number of cursors. Special case of 1 request region with multiple kill
    # regions is handled by joining all the regions into a single Newline separated string.
    if result:
        if n_regions > 0:
            if n_regions == 1 and len(result) > 1:
                result = ["\n".join(result)]
            else:
                while len(result) < n_regions:
                    result *= 2
            return result[0:n_regions]
        return result
    return None

class Kill(object):
    """A single kill (maybe with multiple cursors)"""
    def __init__(self, regions):
        self.regions = regions
        self.n_regions = len(regions)

    # Joins a set of regions with our existing set, if possible. We must have
    # the same number of regions.
    def join_if_possible(self, regions, forward):
        if len(regions) != self.n_regions:
            return False
        for i, c in enumerate(regions):
            if forward:
                self.regions[i] += regions[i]
            else:
                self.regions[i] = regions[i] + self.regions[i]
        return True

    #
    # Get a sample from the first cursor. This is trickier than it seems because we don't like the
    # way sublime samples the string when displaying it, so we need to try to make sure it fits on
    # the screen or at least comes close. We pass in the view to get the current approximate width
    # of the screen in characters.
    #
    def get_sample(self, view):
        # approximate number of chars we can show
        max_chars = (view.viewport_extent()[0] / view.em_width()) * .9
        text = self.regions[0]
        n_regions = len(self.regions)

        # stripe newlines, spaces and tabs from the beginning and end
        text = text.strip("\n \t")

        # collapse multiple newlines into a single and convert to a glyph
        # text = re.sub("\n+", "↩", text)
        # text = re.sub("\n+", "\u23ce", text)
        text = re.sub("\n+", "\u00b6", text)

        # replace multiple white space with single spaces within the string
        text = re.sub("\\s\\s+", " ", text)

        # truncate if necessary
        if len(text) > max_chars:
            half = int(max_chars / 2)
            text = text[:half] + "\u27FA" + text[-half:] + "   "

        if n_regions > 1:
            text = "[%d]: %s" % (n_regions, text)
        return text

    #
    # We set the clipboard to the concatenation of all the regions with "\n" like Sublime already
    # did.
    #
    def set_clipboard(self):
        sublime.set_clipboard("\n".join(self.regions))

    #
    # Returns true if this region matches the current external clipboard.
    #
    def matches_clipboard(self):
        clipboard = sublime.get_clipboard()
        offset = 0
        for region in self.regions:
            length = len(region)
            if region != clipboard[offset:offset+length]:
                return False
            # skip the region and the following newline character
            offset += length + 1
        return offset >= len(clipboard)

    def same_as(self, regions):
        if len(regions) != self.n_regions:
            return False
        for me, him in zip(regions, self.regions):
            if me != him:
                return False
        return True
