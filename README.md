# Welcome to SublemacsPro.

The reasoning behind writing these set of functions is that we love Emacs. On the other hand,
we cannot move to another editor, since many of those hyped editors share that they don't
provide the key bindings that we love and have embraced over time.

Then, we found Sublime Text. A completely customizable editor allowing you to easily modify
all default behaviors so that they suit your editing style and can be made Emacs awesome.

The goal is to bring "emacs essentials" to Sublime Text. This includes things like the using classic
emacs key bindings, subtle differences in word and line motion, the behavior of the ctrl+k command,
etc. But we have also embraced Sublime's multi-cursor editing while making these changes, so that
the Emacs mark and kill/yank commands are fully multi-cursor aware. Incremental search is another
example, where you can keep or skip matches along the way so that when you're done the kept matches
are available as cursors for further editing.


## Installation

To install SublemacsPro you have to install [Package Control]
(http://wbond.net/sublime_packages/package_control) as an automatic package manager for
Sublime Text. Now, you can easily install SublemacsPro and your installation will never be
outdated. After you install Package Control, hit ``[CMD]-Shift P`` on Mac or ``[Ctrl]-Shift
P`` on Windows\Linux to open up the command palette and type ``install``. Now select ``Package
Control: Install Package``. This will load all packages from the remote repository and you can
select ``sublemacspro`` from the drop-down list.

## Sublime Text 2 and 3 Support

The main development for Sublemacs is now Sublime Text 3 only. However, there is still the
branch using the earlier codebase for ST2.

[https://github.com/grundprinzip/sublemacspro/tree/st2](https://github.com/grundprinzip/sublemacspro/tree/st2)

## Features and Key Bindings
The following features have largely been implemented from scratch and are only supported with
Sublime Text 3. For the bindings below, ``meta`` is the ``alt`` key on Windows/Linux or
``option`` on the Mac. ``super`` is the ``Command`` key on the Mac.

### Key Features Overview
  * Emacs-style Universal, Numeric, and Negative Argument Handling
  * Emacs-style Kill Ring with Multi-cursor Support and Sublime Quick Panel Selection
  * Emacs-style Mark Ring with Multi-cursor Support
  * Emacs-style Incremental Search with History (regular and regex supported)
  * Emacs-style Frame (Window), Window (Window Pane), and Buffer (View) Commands
  * Emacs-style Switch to Buffer (View) Command (remembers most recent views)
  * Change Case Commands (upper,lower,title,camelCase, and Underscore supported)
  * Zap/Jump to Char and String with Multi-cursor Support
  * Rectangle and Text/Point Register Commands (not Multi-cursor aware)
  * Emacs Navigation Commands
  * All Buffers (Views) Auto Complete

#### Emacs-style Universal, Numeric, and Negative Argument Handling
  * ``ctrl+u``: Emacs universal argument command (so 4^n where n is the number of times
    ``ctrl+u`` has been pressed) E.g., ``ctrl+u ctrl+u ctrl+f`` means go forward 16
    characters.
  * ``meta+0`` ... ``meta+9``: Emacs numeric arguments - you provide a prefix using the numeric
    arguments before a command to run it that many times. E.g., ``meta+2 meta+3 ctrl+f`` means go
    forward 23 characters.
  * ``alt+-``: Emacs negative argument command - reverses the direction of the command. E.g.,
    ``meta+2 meta+3 alt+- ctrl+f`` means go backward 23 characters.

#### Emacs-style Kill Ring with Multi-cursor Support and Sublime Quick Panel Selection
  * *Commands that utilize the kill ring
    * ``ctrl+w`` and ``meta+w``: Kill (cut) and copy to the top of the kill ring.
    * ``ctrl+y``: Yank (Paste) from the last entry put into the kill ring.
    * ``meta+y`` and ``shift+meta+y``: Yank-pop forward and backward on the kill ring, but
      requires a yank command before running either one.
    * ``ctrl+k``: Kill to the end of line.
      * Mimics emacs almost exactly (it does not support a 0 numeric argument to delete to the
        beginning of the line). Providing a numeric argument means "delete that many lines"
        which is different from typing ``ctrl+k`` that many times.
    * ``ctrl+meta+k``: Delete S-Expression and place on top of the kill ring.
      * Supports emacs universal and numeric arguments.
      * Can pass in a ``direction`` argument set to ``-1`` to delete backward.
    * ``meta+d`` and ``meta+backspace``: Kill word forward and backward and append deleted
      text to the kill ring.
      * Supports emacs universal and numeric arguments.
    * ``ctrl+x ctrl+y``: Displays a Sublime quick panel menu of all the kills and allows you to
      choose which one to yank.
  * *Kill ring implementation details*
    * 64 entries by default, but settable with ``sbp_kill_ring_size`` setting in the
      ``sublemacspro .sublime-settings`` file.
    * Adjacent kill commands (``meta+d``,``ctrl+k``,etc...) are appended to the same entry at
      the top of the kill ring.
    * The yank command will pull from the system clipboard if it finds it is not the same as
      the current kill-ring entry. This means you can go into a different application and copy
      something there. Then, paste it into Sublime using ``ctrl+y``.
    * Anything you kill in Sublime will be placed on the clipboard for other apps to access.
  * *Multi-cursor support*
    * If you had multiple cursors while appending to the kill ring, the kill entry will
      contain and remember those separate cursors. If you try to yank multiple cursors, it
      will work as expected if you still have the same number of cursors. If you have more
      cursors than your kill, the kill will be repeated until you have enough. If you have
      fewer cursors than your kill, it will use just as many as it needs.

#### Emacs-style Mark Ring with Multi-cursor Support
  * *Commands that utilize the kill ring*
    * ``ctrl+space``: Push a new mark onto the ring
    * ``ctrl+x ctrl+x``: Switch point and mark
    * ``ctrl+space ctrl+space``: Push a new mark and activate the mark, which means *highlight
      it as a selection*. It will stay highlighted until ``ctrl+g`` is pressed or certain
      commands are executed.
    * ``ctrl+u ctrl+x ctrl+x``: Toggles the current state of the mark to see the current mark
      selection region. This will highlight the current mark region (activate the mark) if it
      isn't highlighted or remove the highlighting (deactivate the mark) if it is highlighted.
      * Suggested additional binding for this: ``{"keys": ["ctrl+m"], "command":
        "sbp_swap_point_and_mark", "args": {"toggle_active_mark_mode": true}},``
    * ``ctrl+u ctrl+space``: Pop off the mark/s at the top of the mark ring (most recent
      entry). This will move the cursor to the mark and put the current active mark at that
      location.
  * *Kill ring implementation details*
    * Commands such as ``ctrl+y``, ``meta+y``, ``meta+<``, and ``meta+>`` set the mark
      automatically as they do (and must) in emacs.
    * If you use the mouse to make a selection, it will set the mark and it will become the
      emacs region as well.
  * *Multi-cursor support*
    * You can set the mark with multiple cursors and pop off the mark ring to marks with multiple
      cursors. Furthermore, you can kill and copy using those cursors, and then yank them later as
      well. All the above commands for manipulating the mark ring (and kill ring) will continue to
      work with multiple cursors.

#### Emacs-style Incremental Search with History (regular and regex supported)
  * *Commands to initiate a search*
    * ``ctrl+s`` and ``ctrl+r``: Initiate a forward or backward search.
    * ``ctrl+u ctrl+s`` and ``ctrl+u ctrl+r``: Initiate a forward or backward regex search.
    * ``ctrl+s ctrl+s`` and ``ctrl+r ctrl+r``: Initiate a forward or backward search using the
      same search string as the last search.
      * This can be used with a regex search as well.
  * *Commands during an incremental search*
    * ``ctrl+s``: Move to next match.
    * ``ctrl+r``: Move to previous match.
    * ``meta+d``: Keep current match as a future cursor and move to next.
    * ``ctrl+w``: The characters in front of your cursor are appended to your search string.
    * ``meta+a``: Keep all remaining matches from your current position to the end of the file
      (or beginning if you're doing a reverse search) are added to the kept matches.
      * Pressing ``meta+a meta+a`` will wraparound so select all the matches in the whole file.
    * ``backspace``: Move backward in the search history (undo).
      * Will undo any of the above commands moving backwards in the commands run during the
        search one at a time. For example, it will go back to a previous match, delete a
        character from your search string, or remove the last kept match.
      * When undoing a ``ctrl+w`` append from cursor command, the entire set of characters are
        removed at once. However, if you use ``shift+backspace`` instead, it will remove just one
        character at a time.
    * ``ctrl+g``: If your search is currently failing, takes you back to the last point your
      search was succeeding. When your search is succeeding, the search is
      aborted and you go back to the start.
    * ``up``: Access previous history in the search history.
    * ``down``: Access next history in the search history.
    * ``enter``: End your search with all the kept items as multi-cursors.
  * *Incremental search implementation details*
    * If you type any uppercase characters in your search, the search automatically becomes
      case-sensitive.
    * You can end your search by typing any regular emacs commands as well, e.g., ``ctrl+a``,
      ``meta+f``, ``ctrl+l``, ``meta+<``, ``meta+>``, ``ctrl+f``, ``ctrl+n``, etc.... The kept
      items will be intact as multi-cursors.
    * When you complete (as opposed to abort) a search, your mark is set to where you started
      the search from.
    * I-search has support for remembering previous searches. You can access previous searches
      with the up and down arrow keys after you initiate a search.
  * *Find and Replace*
    * ``alt+r``: Not implemented in Sublemacspro so this brings up the default find and
      replace of sublime text.

#### Emacs Frame (Window), Window (Window Pane), and Buffer (View) Commands
  * *Frame (Window) Commands*
    * ``ctrl+x 5 2``: Open a new frame (Window).
    * ``ctrl+x 5 0``: Close the current frame (Window).
  * *Window Pane Commands*
    * ``ctrl+x 1``: Remove all other window panes except this one
    * ``ctrl+x 2``: Split window pane vertically
    * ``ctrl+x 3``: Split window pane horizontally
    * ``ctrl+x d``: Delete current window pane
    * ``ctrl+x o``: Go to next window pane.
    * ``ctrl+x n``: Go to next window pane.
    * ``ctrl+x p``: Go to previous window pane.
    * ``super+shift+[``: Go to previous tab in this window pane (wraps around at edges).
    * ``super+shift+]``: Go to next tab in this window pane (wraps around at edges).
    * ``ctrl+x ^`` or ``ctrl+shift+i``: Make selected window pane taller.
    * ``ctrl+x -`` or ``ctrl+shift+k``: Make selected window pane wider.
    * ``ctrl+x }`` or ``ctrl+shift+j``: Make selected window pane narrower.
    * ``ctrl+x {`` or ``ctrl+shift+l``: Make selected window pane shorter.
      * Resize window pane commands accept universal, numeric, and negative arguments so
        ``alt+5 ctrl+x ^`` will make the selected window taller by 5 times.
  * *View Commands*
    * ``ctrl+x k``: Delete current view from this window pane.
    * ``ctrl+x K``: Delete oldest n views.
      * n is set by default to ``5``. This can be changed by overriding the binding in your
        user bindings file by changing the argument ``n_windows``. The default binding is:
        ``{"keys": ["ctrl+x", "K"], "command": "sbp_close_older_views", "args": {"n_windows":
        5}}``
    * ``ctrl+x b``: Go to next view (keeps scrolling through all the views (tabs to the right
      in each window pane) and ignores window pane boundaries going into the next pane when it
      reaches the last view on the right).
    * ``ctrl+x right``: Go to next view (set to the same command as ``ctrl+x b`` above).
    * ``ctrl+x left``: Go to previous view (keeps scrolling through all the views (tabs to the
      left in each window pane) and ignores window pane boundaries going into the next pane
      when it reaches the last view on the left).

#### Switch to View (Buffer)
  * Commands
    * ``ctrl+x ctrl+b``: Switch to a view (buffer) using the quick panel for selection.
  * Implementation Details
    * Sorted by last used time and skips past the current view in the quick panel to the
      second most recent view.
    * Optional arguments with the default values are ``completion_components=2`` and
      ``display_components=1``.
      * The default configuration displays the view's file name and parent
        directory (the last 2 components of the file path) on the top line and just the last
        component of the file name on the second line. The completion is performed on the
        first line. If you set the value of display_components to 0, the second line will be
        omitted entirely.
    * If creating your own key bindings has optional argument ``current_group_only``, default
      is ``false``, but when set to ``true`` will only use the current window pane for the
      switch to view.

#### Go to File or Symbol
  * ``ctrl+x ctrl+f``: Go to file in a quick panel as implemented by Sublime.
  * ``ctrl+alt+g``: Go to symbol in the quick panel as implemented by Sublime.

#### Change Case Commands
  * ``meta+c``, ``meta+l``, ``meta+u``: capitalize, lower case, upper case words using the
    ``sbp_change_case`` command. They support emacs-style numeric arguments, including
    negative arguments which means "do it to the previous N words".
    * Accepts two arguments ``direction`` (``1`` is forward and ``-1`` is backward) and
      ``mode`` (can be ``title``, ``upper``, or ``lower``).
  * ``ctrl+x ctrl+u`` and ``ctrl+x ctrl+l``: upper case and lower case the highlighted
    region/s or the emacs region/s if nothing is highlighted.
    * This use the same ``sbp_change_case`` command as above with the ``use_region`` argument
      set to ``true``, therefor, no ``direction`` argument is needed.
  * ``ctrl+x ctrl+super+c``, ``ctrl+x ctrl+super+u``: Convert from Underscores to camelCase
    and vice versa. They operate on highlighted region/s or emacs region/s as ``ctrl+x
    ctrl+u`` above and use the same ``sbp_change_case`` command setting the ``mode`` to
    ``camel`` or ``underscore``.

#### Zap/Jump to Char and String
  * *Zap and Jump Commands*
    * ``alt+z``: Zap-to-char, delete from current point to the next occurrence of a character and
      includes deleting the character.
    * ``shift+alt+z`` zap-up-to-char, delete from current point up to but not including the next
      occurrence of a character.
    * ``ctrl+x z`` zap-to-string, delete from current point until next occurrence of the string and
      includes deleting the string.
    * ``ctrl+x Z`` zap-up-to-string, delete from current point up to but not including the next
      occurrence of the string.
    * ``ctrl+x j c`` jump-to-char, move past the next occurrence of a character.
    * ``ctrl+x j C`` jump-up-to-char, move up to the next occurrence of a character.
    * ``ctrl+x j s`` jump-to-string, move past next occurrence of a string.
    * ``ctrl+x j S`` jump-up-to-string, move up to the next occurrence of a string.
  * *Implementation Details*
    * The char jump and zap commands have an optional argument ``include_char`` that is set to
      ``true`` by default.
    * The string jump and zap commands have an optional argument ``include_string`` that is set to
      ``true`` by default.

#### Rectangle and Text/Point Register Commands (not Multi-cursor aware)
  * *Text and Point Register Commands*
    * ``C-x r s [register]``: Store the current emacs region or highlighted region into the register.
    * ``C-x r i [register]``: Insert the selected register at the current cursor position.
    * ``C-x r space [register]``: Store the current point into a register.
    * ``C-x r j [register]``: Jump to the stored point in the selected register.
    * `[register]` can be set as 'a-z/0-9/A-Z'.
    * ``C-x r r``: Choose a text register to insert from the sublime quick panel menu.
    * ``C-x r p``: Choose a point register to jump to from the sublime quick panel menu.
  * *Rectangle Commands*
    * ``C-x r t``: Rectangular cut (as in emacs).
    * ``C-x r d``: Rectangular insert (as in emacs).

#### Emacs Navigation Commands
  * *Word Level*
    * ``meta+f`` and ``meta+b``: Forward and backward words with the same exact behavior of
      emacs in terms of how you move.
    * ``ctrl+meta+f`` and ``ctrl+meta+b``: Forward and backward movement over s-expressions.
      It works for skipping over identifiers, strings, parentheses, braces, square brackets,
      etc...
      * __DEPENDENCY NOTE__: S-expression checks if [Bracket
        Highlighter](https://github.com/facelessuser/BracketHighlighter) is installed, which
        enables it to perform much better movement over s-expressions that are language
        dependent.
      * If [Bracket Highlighter](https://github.com/facelessuser/BracketHighlighter) isn't
        installed, the s-expression falls back to default movement over the modifiers in
        ``sbp_sexpr_separators`` setting in the ``sublemacspro .sublime-settings`` file, but
        this performs much worse than the updated implementation.
  * *Line Level*
    * ``ctrl+n``: Move down a line.
    * ``ctrl+p``: Move up a line.
    * ``ctrl+a``: Go to beginning of line (ignores wrapped lines always goes to very
      beginning).
    * ``alt+m``: Go back to the indentation at the beginning of the line (same as ``ctrl+a``
      except moves back to the indentation instead of the very start of the line).
    * ``ctrl+e``: Go to end of line (ignores wrapped lines always goes to very end).
    * ``alt+a``: Go back to soft beginning of the line (doesn't ignore wrapped lines).
  * *Paragraph Level*
    * ``ctrl+alt+]`` and ``ctrl+alt+[``: Navigate forward and backward paragraphs.
  * *Page Level*
    * ``meta+,`` and ``meta+.``: Move to beginning and end of the current window view,
      respectively.
      * This command allows an optional argument ``always_push_mark`` which by default is set
        to ``true`` and will push the mark before going to the beginning or end of the current
        window view.
    * ``ctrl+v``: Page down.
    * ``alt+v``: Page up.
    * ``ctrl+l``: Center current line in view.
      * Used with numeric arguments, put the current line at the Nth line in the view (E.g. ``meta+5
        ctrl+l`` moves the current line to the 5th line in the view.
  * *File Level*
    * ``meta+<`` and ``meta+>``: Move to beginning and end of file, respectively.
    * ``meta+g`` also bound to ``ctrl+x g``: Goto line via numeric argument or via quick panel
      entry if entered without a numeric argument.
      * Numeric argument e.g., ``meta+4 meta+3 meta+5 meta+g`` goes to line 435.

#### All View Auto Complete
  * Similar to All Autocomplete plugin but fixed two issues with that plugin: the limit of 20 views
    to search and completions not being found due to errors in some syntax definitions.
  * Disabled by default.
  * Enable by setting ``sbp_use_internal_complete_all_buffers`` to ``true`` in the
    ``sublemacspro.sublime-settings`` file.

#### Miscellaneous Commands
  * *Undo/Redo*
    * ``ctrl+backslash``: Undo.
    * ``ctrl+_``: Undo.
    * ``ctrl+x u``: Undo.
    * ``ctrl+shift+/``: Redo.
    * ``ctrl+shift+backslash``: Redo.
  * *Save*
    * ``ctrl+x, ctrl+s``: Save this file.
    * ``ctrl+x, ctrl+m``: Save all files.
    * ``ctrl+x, s``: Save all files.
    * ``ctrl+x, ctrl+w``: Prompt for writing a new file to disk (Save As...).
  * *Selection*
    * ``ctrl+x h``: Select All
  * *Deletion*
    * ``ctrl+d``: Right delete.
    * ``backspace``: Left delete.
  * *Wrap Lines*
    * ``alt+j``: Wrap lines using sublime built in function to 100 characters.
  * *Indent/Unindent*
    * ``ctrl+c, >``: Indent.
    * ``ctrl+c, <``: Unindent.
    * ``alt+i``: Insert tab character at cursor ("\t").
  * *Macros*
    * ``ctrl+x, (``: Toggle macro recording.
    * ``ctrl+x, )``: Toggle macro recording.
    * ``ctrl+x, e``: Execute recorded macro.
  * *Exit*
    * ``ctrl+x, ctrl+c``: Save this file.
  * *Shift Indentation of Regions*
    * ``alt+]``: Shift active mark region or current highlighted region to the right one
    indentation.
    * ``alt+[``: Shift active mark region or current highlighted region to the left one
    indentation.
  * *White Space Removal*
    * ``meta+backslash``: Delete white space around point.
  * *Auto Complete*
    * ``alt+/``: Used to bring up Sublime's Auto Complete window.
    * ``alt+h``: Used to bring up Sublime's Auto Complete window.
  * *Find and Replace*
    * ``alt+r``: Not implemented so brings up default find and replace of sublime.

## Important Settings File Options

#### Kill Ring Size
  * Settable by ``sbp_kill_ring_size``.

#### Use Alt Bindings (as well as alt+ for digits) or Super (Command on Mac) Bindings
  * Default is ``sbp_use_alt_bindings`` set to ``true`` and ``sbp_use_super_bindings`` to false.
    - If you prefer super bindings swap these.
  * To insert digits as their normal characters instead of using Emacs-style numeric arguments,
    change ``sbp_alt+digit_inserts`` to ``true``.

#### Trim Trailing White Space and Ensure New Line at End of File
  * Optional settings that if set to true in the ``sublemacspro.sublime-settings`` will occur on
    saving a file.

#### All View Auto Complete
  * Set ``sbp_use_internal_complete_all_buffers`` to ``true``.

## Known Bugs/Issues

  * If you're running an incremental search and you invoke another command that opens the overlay,
    such as "Goto Anything..." or "Command Palette...", the search can get into a weird state and
    interfere with the overlay. To deal with that, we override the default key bindings for those
    commands and handle them properly. If you have your own bindings for those commands, you should
    copy this:

    ```json
    {"keys": ["super+shift+p"], "command": "sbp_inc_search_escape",
        "args": {"next_cmd": "show_overlay", "next_args": {"overlay": "command_palette"}},
        "context": [ {"key": "i_search_active"}, {"key": "panel_has_focus"} ]
    },
    {"keys": ["super+t"], "command": "sbp_inc_search_escape",
        "args": {"next_cmd": "show_overlay", "next_args": {"overlay": "goto", "show_files": true}},
        "context": [ {"key": "i_search_active"}, {"key": "panel_has_focus"} ]
    },
    ```


## Future

We will try to extend this more and more to provide more features from Emacs to Sublime Text,
and make this a fast and beautiful Emacs replacement.

#### Possible Future Package Additions
  * Supplying a numeric argument to ``ctrl+d`` and ``Backspace`` should append to the kill
    ring.
  * Turn the last n marks into multiple cursors.
  * Switch to view works across windows (frames) and not just within a single window.
  * Make the registers work with multi-cursors.
  * Add a popup window asking how many of the n oldest windows to remove if called with
    popup=true argument to close_older_views command.
  * [Emacs marking of textual objects](https://www.gnu.org/software/emacs/manual/html_node/emacs/Marking-Objects.html)
  * Quick Panel selection to scroll through the mark ring and pop a previous mark like choose
    and yank command for the kill ring.

### Authors and Contributors
2012-2017 Jonathan Payne (@canoeberry), Jeff Spencer (@excetara2), Martin Grund (@grundprinzip),
Brian M. Clapper (@bmc)

* @dustym - focus groups
* @phildopus - for goto-open-file
* @aflc - toggle comment improvements
* @jinschoi - ST3 bugfix
* @mcdonc - inspiration for more Emacs key bindings

[ot]: https://github.com/stiang/EmacsifySublimeText
[ot2]: https://github.com/bmc/ST2EmacsMiscellanea
[ot3]: https://github.com/stiang/EmacsKillRing
[subl]: http://www.sublimetext.com/docs/2/api_reference.html
[bmc]: https://github.com/bmc/
