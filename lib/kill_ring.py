import re
import sublime, sublime_plugin

#
# Classic emacs kill ring except this supports multiple cursors.
#
class KillRing:
    KILL_RING_SIZE = 64

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

        def get_sample(self):
            text = self.regions[0][0:256]
            text = text.strip("\n \t").replace("\n", "\\n")
            text = re.sub("\\s\\s+", " ", text)
            return text

        def set_clipboard(self):
            sublime.set_clipboard(self.regions[0])

        def same_as(self, regions):
            if len(regions) != self.n_regions:
                return False
            for me, him in zip(regions, self.regions):
                if me != him:
                    return False
            return True

    def __init__(self):
        self.entries = [None] * self.KILL_RING_SIZE
        self.index = 0
        self.pop_index = None

    #
    # Add some text to the kill ring. 'forward' indicates whether the editing command that produced
    # this data was in the forward or reverse direction. It only matters if 'join' is true, because
    # it tells us how to add this data to the most recent kill ring entry rather than creating a new
    # entry.
    #
    def add(self, regions, forward, join):
        total_bytes = sum((len(c) for c in regions))

        if total_bytes == 0:
            return
        index = self.index
        try:
            if not join:
                # if the current item is the same as what we're trying to kill, don't bother
                if self.entries[index] and self.entries[index].same_as(regions):
                    return
            else:
                # try to join
                if self.entries[index] and self.entries[index].join_if_possible(regions, forward):
                    return

            # create the new entry
            index = (index + 1) % self.KILL_RING_SIZE
            self.entries[index] = KillRing.Kill(regions)
        finally:
            self.index = index
            self.entries[index].set_clipboard()

    #
    # Returns a sample of the first region of each entry in the kill ring, so that it can be
    # displayed to the user to allow them to choose it. The sample is truncated unfortunately.
    #
    def get_popup_sample(self):
        index = self.index
        result = []
        seen = {}
        while True:
            kill = self.entries[index]
            if kill:
                text = kill.get_sample()
                if text not in seen:
                    result.append((index, text))
                    seen[text] = True
            index = (index - 1) % self.KILL_RING_SIZE
            if index == self.index:
                break
        return result

    def set_current(self, index):
        if self.entries[index]:
            self.index = index
            self.entries[index].set_clipboard()

    #
    # Returns the current entry in the kill ring for the purposes of yanking. If pop is non-zero, we
    # move backwards or forwards once in the kill ring and return that data instead. If the number
    # of regions doesn't match, we either truncate or duplicate the regions to make a match.
    #
    def get_current(self, n_regions, pop):
        entries = self.entries

        clipboard = result = None
        if pop == 0:
            index = self.index
            entry = entries[index]

            # first check to see whether we bring in the clipboard
            clipboard = sublime.get_clipboard()

            if clipboard and (entry is None or entry.n_regions != 1 or entry.regions[0] != clipboard):
                # We switched to another app and cut or copied something there, so add the clipboard
                # to our kill ring.
                result = [clipboard]
                self.add(result, True, False)
            elif entry:
                result = entry.regions
            self.pop_index = None
        else:
            if self.pop_index is None:
                self.pop_index = self.index

            incr = -1 if pop > 0 else 1
            index = (self.pop_index + incr) % self.KILL_RING_SIZE
            while entries[index] is None:
                if index == self.pop_index:
                    return None
                index = (index + incr) % self.KILL_RING_SIZE

            self.pop_index = index
            result = entries[index].regions
            entries[index].set_clipboard()

        # make sure we have enough data for the specified number of regions
        if result:
            while len(result) < n_regions:
                result *= 2
            return result[0:n_regions]
        return None

# kill ring shared across all buffers
kill_ring = KillRing()
