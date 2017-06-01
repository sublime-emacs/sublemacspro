import time

import sublime, sublime_plugin

from .mark_ring import MarkRing

#
# We store state about each view. In particular, the mark ring, whether active_mark is set, a
# boolean to manage resetting the target column, the argument count, this and previous command
# names, and the last touched time. Only last touched time is saved when sublime exits.
#
class ViewState():
    # per view state
    view_state_dict = dict()

    # currently active view
    current = None

    def __init__(self, view):
        ViewState.view_state_dict[view.id()] = self
        self.view = view
        self.active_mark = False
        self.touched = view.settings().get("touched")
        if self.touched is None:
            self.touch()

        # a mark ring per view (should be per buffer)
        self.mark_ring = MarkRing(view)
        self.reset()

    @classmethod
    def on_view_closed(cls, view):
        if view.id() in cls.view_state_dict:
            del(cls.view_state_dict[view.id()])

    #
    # Finds ot creates the state for the given view. This doesn't imply a touch().
    #
    @classmethod
    def find_or_create(cls, view):
        state = cls.view_state_dict.get(view.id(), None)
        if state is None:
            state = ViewState(view)
        return state

    #
    # Find (or create) the state for the specified view, and touch() it. Also sets the current
    # view_state to the one for this view.
    #
    @classmethod
    def get(cls, view):
        # make sure current is set to this view
        if ViewState.current is None or ViewState.current.view != view:
            state = cls.view_state_dict.get(view.id(), None)
            if state is None:
                state = ViewState(view)
            ViewState.current = state
        ViewState.current.touch()
        return ViewState.current

    #
    # Returns a list of views from a given window sorted by most recently accessed/touched. If group
    # is specified, uses only views in that group.
    #
    @classmethod
    def sorted_views(cls, window, group=None):
        views = window.views_in_group(group) if group is not None else window.views()
        states = [cls.find_or_create(view) for view in views]
        sorted_states = sorted(states, key=lambda state: state.touched, reverse=True)
        return [state.view for state in sorted_states]

    #
    # Reset the state for this view.
    #
    def reset(self):
        self.this_cmd = None
        self.last_cmd = None
        self.argument_supplied = False
        self.argument_value = 0
        self.argument_negative = False
        self.drag_count = 0
        self.entered = 0

    #
    # Touch this view.
    #
    def touch(self):
        self.touched = time.time()
        self.view.settings().set("touched", self.touched)

    #
    # Get the argument count and reset it for the next command (unless peek is True).
    #
    def get_count(self, peek=False):
        if self.argument_supplied:
            count = self.argument_value
            if self.argument_negative:
                if count == 0:
                    count = -1
                else:
                    count = -count
                if not peek:
                    self.argument_negative = False
            if not peek:
                self.argument_supplied = False
        else:
            count = 1
        return count

    def last_was_kill_cmd(self):
        from .misc import kill_cmds
        return self.last_cmd in kill_cmds
