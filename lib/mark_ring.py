import sublime, sublime_plugin

#
# Classic emacs mark ring with multi-cursor support. Each entry in the ring is implemented
# with a named view region with an index, so that the marks are adjusted automatically by
# Sublime. The special region called "jove_mark" is used to display the current mark. It's
# a copy of the current mark with gutter display properties turned on.
#
# Each entry is an array of 1 or more regions.
#
class MarkRing:
    MARK_RING_SIZE = 16

    def __init__(self, view):
        self.view = view
        self.index = 0

        # in case any left over from before
        self.view.erase_regions("jove_mark")
        for i in range(self.MARK_RING_SIZE):
            self.view.erase_regions(self.get_key(i))

    def get_key(self, index):
        return "jove_mark:" + str(index)

    def clear(self):
        self.view.erase_regions("jove_mark")

    def has_visible_mark(self):
        return self.view.get_regions("jove_mark") != None and len(self.view.get_regions("jove_mark")) > 0

    #
    # Update the display to show the current mark.
    #
    def display(self):
        # display the mark's dot
        regions = self.get()
        if regions is not None:
            self.view.add_regions("jove_mark", regions, "mark", "dot", sublime.HIDDEN)

    #
    # Get the current mark(s).
    #
    def get(self):
        return self.view.get_regions(self.get_key(self.index))

    #
    # Set the mark to pos. If index is supplied we overwrite that mark, otherwise we push to the
    # next location.
    #
    def set(self, regions, reuse_index=False):
        if self.get() == regions:
            # don't set another mark in the same place
            return
        if not reuse_index:
            self.index = (self.index + 1) % self.MARK_RING_SIZE
        self.view.add_regions(self.get_key(self.index), regions, "mark", "", sublime.HIDDEN)
        self.display()

    #
    # Exchange the current mark with the specified pos, and return the current mark.
    #
    def exchange(self, regions):
        current = self.get()
        if current is not None:
            self.set(regions, True)
            return current

    #
    # Pops the current mark from the ring and returns it. The caller sets point to that value. The
    # new mark is the previous mark on the ring.
    #
    def pop(self):
        regions = self.get()

        # find a non-None mark in the ring
        start = self.index
        while True:
            self.index -= 1
            if self.index < 0:
                self.index = self.MARK_RING_SIZE - 1
            if self.get() or self.index == start:
                break
        self.display()
        return regions
