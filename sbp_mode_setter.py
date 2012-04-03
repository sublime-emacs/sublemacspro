import sublime, sublime_plugin
import re
import os

# Must contain a single group, for extracting the syntax name
EMACS_SYNTAX_MARK_RE = r'-\*-\s*(.+)\s*-\*-'

# Aliases for some of the syntax values.
SYNTAX_ALIASES = {
    'sh'    : 'shell-unix-generic',
    'shell' : 'shell-unix-generic',
    'bash'  : 'shell-unix-generic',

    # HAML and SASS depend on https://github.com/n00ge/sublime-text-haml-sass
    'sass'  : 'ruby sass',
    'haml'  : 'ruby haml'
}

class SbpEmacsModeSetter(sublime_plugin.EventListener):
    '''
    This plugin makes Sublime Text 2 mimic Emacs' behavior of setting
    the buffer syntax based on a special "mode line" somewhere in the
    first non-blank line of a buffer. For instance, if file "foo.C"
    would normally be displayed using C syntax rules, but you want to
    force Sublime to use C++ rules, simply include a comment like this
    in the first non-blank line of the file:

        -*- c++ -*-

    The name of the syntax must match a tmLanguage file somewhere
    under your Sublime "Packages" directory. The match is case-insensitive,
    and white space between the "-*-" markers is optional.
    '''
    def __init__(self):
        self._syntax_re = re.compile(EMACS_SYNTAX_MARK_RE)
        self._syntaxes = {}

        # Construct a regular expression that will take a full path and
        # extract everything from "Packages/" to the end. This expression
        # will be use to map paths like /path/to/Packages/C/C.tmLanguage
        # to just Packages/C/C.tmLanguage, which is what Sublime wants
        # as a syntax setting.
        sep = r'\\' if os.sep == "\\" else os.sep
        package_pattern = '^.*%s(Packages%s.*)$' % (sep, sep)
        package_re = re.compile(package_pattern)  

        # Recursively walk the Sublime Packages directory, looking for
        # '.tmLanguage' files. Convert each one to a short language name
        # (used as a dictionary key) and the full name that Sublime wants.
        for root, dirs, files in os.walk(sublime.packages_path()):
            # Filter out files that don't end in .tmLanguage
            lang_files = [f for f in files if f.endswith('.tmLanguage')]

            # Map to a full path...
            full_paths = [os.path.join(root, l) for l in lang_files]

            # ... and strip off everything prior to "Packages"
            for p in full_paths:
                # The "Emacs" name is something like "C", or "Python"
                emacs_syntax_name = os.path.splitext(os.path.basename(p))[0]

                # The Sublime name is as described above.
                sublime_syntax_name = package_re.search(p).group(1)

                # Store in the hash.
                self._syntaxes[emacs_syntax_name.lower()] = sublime_syntax_name

    def on_activated(self, view):
        '''
        Called when a view is activated (i.e., receives focus). That's a good
        time to re-check the syntax setting.
        '''
        self._check_syntax(view)

    def on_load(self, view):
        '''
        Called when a view is first loaded. Check the syntax setting then.
        '''
        self._check_syntax(view)

    def on_pre_save(self, view):
        '''
        Called right after a save. Check the syntax then, in case it changed.
        '''
        self._check_syntax(view)
    
    def _check_syntax(self, view):
        '''
        Does the actual work of checking the syntax setting and changing it,
        if necessary.
        '''
        name = view.name() or view.file_name()
        # Scan the buffer to find the embedded syntax setting, if one exists.
        buffer_syntax_value = self._find_emacs_syntax_value(view)
        if buffer_syntax_value is None:
            view.settings().erase("sticky-syntax")
        else:
            # The buffer has a syntax setting. See if it maps to one of the
            # known ones.
            syntax = self._syntaxes.get(buffer_syntax_value.lower(), None)
            if syntax is None:
                # The syntax value doesn't map to something Sublime groks
                print('WARNING: Unknown syntax value "%s" in file "%s".' %
                       (buffer_syntax_value, name))
                view.settings().erase("sticky-syntax")
            else:
                # It does. Is it different from the current syntax of the
                # buffer? If so, change the buffer's syntax setting.
                if view.settings().get('syntax') != syntax:
                    print("EmacsLikeSyntaxSetter: %s: %s" % (name, syntax))
                    view.set_syntax_file(syntax)
                    # Use the view's settings object to set a 'sticky-syntax'
                    # setting, which will prevent my other plugin from
                    # overwriting this value.
                    view.settings().set("sticky-syntax", True)
                else:
                    view.settings().erase("sticky-syntax")

    def _find_emacs_syntax_value(self, view):
        '''
        Finds the first blank line, searches it for a syntax/mode marker and,
        if found, extracts the language name without verifying that it's valid.

        Returns the (string) name or None.
        '''
        # Must be somewhere in the first nonblank line.
        first_nonblank_line = self._first_nonblank_line(view)
        syntax_expression = None
        name = view.name() or view.file_name()
        if first_nonblank_line is not None:
            m = self._syntax_re.search(first_nonblank_line)
            if m is not None:
                syntax_expression = m.group(1).strip()

        # If it's in the aliases table, map it. Otherwise, default to using
        # the value we just parsed.
        return SYNTAX_ALIASES.get(syntax_expression, syntax_expression)

    def _first_nonblank_line(self, view):
        '''
        Finds the first non-blank line in the view, starting at the top,
        and returns it.

        Returns the line (str) or None
        '''
        # Start with point=0, which is the top of the buffer. Stop if point
        # ever gets to the end of the buffer.
        point = 0
        size = view.size()
        result = None
        while (result is None) and (point < size):
            # Get the region associated with the line at the current point.
            region = view.line(point)
            if region is None:
                # No region. Point is invalid. We're done.
                break

            # Extract the line itself.
            line = view.substr(region)
            if len(line.strip()) > 0:
                # Non-empty line. We're done.
                result = line
            else:
                # Empty. Move past it.
                point = region.b + 1

        return result
