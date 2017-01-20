import sublime, sublime_plugin, time, re

from .lib.misc import *

#
# Called when the system is initialized.
#
def plugin_loaded():
    global extra_word_characters, separator_characters, settings_helper

    settings_helper = SettingsHelper()
    extra_word_characters = settings_helper.get("sbp_syntax_specific_extra_word_characters")
    separator_characters = settings_helper.get("sbp_word_separators", default_sbp_word_separators)

#
# Switch buffer command that sorts buffers by last access and displays file name as well.
#
MIN_AUTO_COMPLETE_WORD_SIZE = 3
MAX_AUTO_COMPLETE_WORD_SIZE = 100
class CompleteAllBuffers(sublime_plugin.EventListener):
    def on_query_completions(self, view, prefix, locations):
        if settings_helper.get("sbp_use_internal_complete_all_buffers") != True:
            return None
        if view.settings().get("inhibit_all_complete"):
            return None

        # This happens if you type a non-word character. We don't want to process any completions in
        # this case because there are too many.
        if len(prefix) == 0:
            return None

        seen = set()
        words = []
        re_by_syntax = {}

        # get a sorted (by last access) list of views in the current window
        window = sublime.active_window()
        views = ViewState.sorted_views(window)

        # determine the set of root directories in the current project if possible
        roots = get_project_roots()
        start = time.time()
        re_flags = sublime.IGNORECASE if prefix.lower() == prefix else 0
        for v in views:
            if v.is_scratch():
                continue

            point = 0
            sel = v.selection
            if len(sel) > 0:
                point = sel[-1].begin()

            # Determine regex by syntax. Rewrite the prefix so it does fuzzy matching rather than
            # strict prefix matching.
            syntax_name = v.settings().get("syntax")
            regex = re_by_syntax.get(syntax_name, None)
            if regex is None:
                extra = extra_word_characters.get(syntax_name) or ""
                word_re = r'[\w' + extra + r']'
                re_prefix = (word_re + '*').join(re.escape(p) for p in prefix)

                # If our starting character is not considered a word character, we cannot use '\b'
                # to start this regex.
                if prefix[0] in separator_characters:
                    regex = ""
                else:
                    regex = r'\b'
                regex += re_prefix + word_re + r'+\b'
                re_by_syntax[syntax_name] = regex

            view_words = self.extract_completions_from_view(v, regex, re_flags, point, view, seen)
            if len(view_words) == 0:
                continue

            # figure the best way to display the file name unless this is the current view
            if v == view:
                file_name = None
            else:
                file_name = get_relative_path(roots, v.file_name())

            for word in view_words:
                if v == view:
                    trigger = word + "\t[HERE]"
                else:
                    trigger = "%s\t%s" % (word, file_name)
                words.append((trigger, word.replace("$", "\\$")))
        tm = time.time() - start
        if tm > 0.20:
            print("COMPLETE in", time.time() - start)
        return (words, sublime.INHIBIT_WORD_COMPLETIONS)

    def extract_from_view(self, view, prefix, point):
        return view.extract_completions(prefix, point)

    def extract_completions_from_view(self, view, regex, re_flags, point, current_view, seen):
        regions = sorted(view.find_all(regex, re_flags),
                         key=lambda r: abs(point - r.begin()))
        results = []
        for region in regions:
            if view == current_view and region.contains(point):
                continue
            if MIN_AUTO_COMPLETE_WORD_SIZE <= region.size() <= MAX_AUTO_COMPLETE_WORD_SIZE:
                word = view.substr(region)
                if word not in seen:
                    results.append(word)
                    seen.add(word)
        return results

