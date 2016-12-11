import time

import sublime, sublime_plugin

from .mark_ring import MarkRing

#
# We store state about each view.
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
        self.touch()

        # a mark ring per view (should be per buffer)
        self.mark_ring = MarkRing(view)
        self.reset()

    @classmethod
    def on_view_closed(cls, view):
        if view.id() in cls.view_state_dict:
            del(cls.view_state_dict[view.id()])

    @classmethod
    def find_or_create(cls, view):
        state = cls.view_state_dict.get(view.id(), None)
        if state is None:
            state = ViewState(view)
        return state

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

    @classmethod
    def sorted_views(cls, window):
        views = window.views()
        states = [cls.find_or_create(view) for view in window.views()]
        sorted_states = sorted(states, key=lambda state: state.touched, reverse=True)
        return [state.view for state in sorted_states]

    def reset(self):
        self.this_cmd = None
        self.last_cmd = None
        self.argument_supplied = False
        self.argument_value = 0
        self.argument_negative = False
        self.drag_count = 0
        self.entered = 0

    def touch(self):
        self.touched = time.time()

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
        from sublemacspro.lib.misc import kill_cmds
        return self.last_cmd in kill_cmds
