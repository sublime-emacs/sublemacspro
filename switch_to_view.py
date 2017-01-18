import sublime, sublime_plugin, time, re

from .lib.misc import *

#
# Switch buffer command. "C-x b" equiv in emacs. This limits the set of files in a chooser to the
# ones currently loaded. We sort the files by last access hopefully like emacs.
#
class SbpSwitchToViewCommand(SbpTextCommand):
    def run(self, util, current_group_only=False, preview=True, completion_components=2, display_components=1):
        self.preview = preview
        self.completion_components = completion_components
        self.display_components = display_components
        window = self.window = sublime.active_window()
        self.group = window.active_group()
        self.views = ViewState.sorted_views(window, window.active_group() if current_group_only else None)
        if window.num_groups() > 1 and not current_group_only:
            self.group_views = set(view.id() for view in ViewState.sorted_views(window, window.active_group()))
        else:
            self.group_views = None
        self.roots = get_project_roots()
        self.original_view = window.active_view()
        self.highlight_count = 0

        # swap the top two views to enable switching back and forth like emacs
        if len(self.views) >= 2:
            index = 1
        else:
            index = 0
        window.show_quick_panel(self.get_items(), self.on_select, 0, index, self.on_highlight)

    def on_select(self, index):
        if index >= 0:
            self.window.focus_view(self.views[index])
        else:
            self.window.focus_view(self.original_view)

    def on_highlight(self, index):
        if not self.preview:
            return
        self.highlight_count += 1
        if self.highlight_count > 1:
            if self.group_views is None or self.views[index].id() in self.group_views:
                self.window.focus_view(self.views[index])

    def get_items(self):
        if self.display_components > 0:
            return [[self.get_path(view), self.get_display_name(view)] for view in self.views]
        return [[self.get_path(view)] for view in self.views]

    def get_display_name(self, view):
        mod_star = '*' if view.is_dirty() else ''

        if view.is_scratch() or not view.file_name():
            disp_name = view.name() if len(view.name()) > 0 else 'untitled'
        else:
            disp_name = get_relative_path(self.roots, view.file_name(), self.display_components)

        return '%s%s' % (disp_name, mod_star)

    def get_path(self, view):
        if view.is_scratch():
            return view.name() or ""

        if not view.file_name():
            return '<unsaved>'

        return get_relative_path(self.roots, view.file_name(), self.completion_components)

