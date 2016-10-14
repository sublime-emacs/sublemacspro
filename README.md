# Welcome to SublemacsPro.

The reasoning behind writing these set of functions is that we love Emacs,
however, the UI doesn't feel as snappy as other Mac apps. On the other hand we
cannot move to another editor since many of those hyped editors share that they
don't provide the keybindings we love and embraced over time.

Then, we found Sublime Text. A completely customizable editor allowing you to
easily modify all default behaviors so that they suit your editing style.

So, we wrote sublemacspro bringing Emacs keybindings and sugar to Sublime Text.
Even though Emacs lives from the plugins, we believe it is way easier to write
new plugins in Python and integrate them in an Emacs-ish way to Sublime Text
than writing them in Lisp.

## Installation

To install SublemacsPro you have to install [Package
Control](http://wbond.net/sublime_packages/package_control) as an automatic
package manager for Sublime Text. Now you can easily install Sublemacs Pro and
your installation will never be outdated. When you installed Package Control,
hit ``[CMD]-Shift P`` to open up the command palette and type ``install``. Now
select "Package Control: Install Package". This will load all packages from the
remote repository and you can select ``sublemacspro`` from the drop-down list.

## Sublime Text 2 and 3 Support

The main development for Sublemacs is now Sublime Text 3 only. However, there
is still the branch using the earlier codebase for ST2.

https://github.com/grundprinzip/sublemacspro/tree/st2

If you encounter bugs or issues in the ST2 version, please report them, and
we'll be happy to fix them.

## Features

The following features are supported and merged [from][ot3] [other][ot] [approaches][ot2]
and the base code of the new beta of [Sublime Text 2][subl].

  * ``ctrl+u``, ``meta+0`` ... ``meta+9``: Emacs universal argument - you provide a prefix arguments to a command to run it that many times. E.g., ``meta+2`` ``meta+3`` ``ctrl+F`` means go forward 23 characters.
  * ``meta+f`` and ``meta+b``: Forward and backward words with the same exact behavior of emacs in terms of how you move.
  * ``ctrl+meta+f`` and ``ctrl+meta+b``: Forward and backward s-expressions. It works for skipping over identifiers, strings and parentheses, braces and square brackets.
  * ``meta+c``, ``meta+l``, ``meta+u``: capitalize, lower case, upper case words. They support numeric arguments, including negative arguments which means "do it to the  previous N words".
  * Full emacs kill ring support:
    * 64 entries - not currently adjustable
    * adjascent kill commands are appended to the same entry
    * ``ctrl+w`` and ``meta+w``: kill and copy to the kill ring.
    * ``ctrl+y`` and ``meta+y``: yank and yank-pop.
    * technically supplying a numeric argument to ``ctrl+d`` and ``Backspace`` should append to the kill ring but I have not done that (yet).
    * The yank command will pull from the clipboard if it finds it is not the same as the current kill-ring entry, meaning you can go into a different app and copy  something there and paste it into emacs using ``ctrl+y``. Also, anything you kill in emacs will be placed on the clipboard for other apps to access.
  * ``meta+d`` and ``meta+Backspace``: Delete word forward and backward, placinging the deleted text on the kill ring.
  * ``ctrl+meta+k``: Delete S-Expression and place on the kill ring. (Negative arguments not supported.)
  * ``ctrl+k``: Kill to end of line mimics emacs almost exactly (it does not support a 0 numeric argument to delete to the beginning of the line). Providing a numeric  argument means "delete that many lines" which is different from typing ``ctrl+k`` that many times.
  * ``meta+<`` and ``meta+>``: move to beginning and end of file.
  * ``meta+,`` and ``meta+.``: move to beginning and end of window.
  * Support for a emacs-style mark including the mark-ring:
    * ``ctrl+space`` to push a new mark onto the ring
    * ``ctrl+x ctrl+x`` to switch point and mark
    * Commands such as ``ctrl+y``, ``meta+y`` set the mark automatically as they do (and must) in emacs.
    * ``meta+<`` and ``meta+>`` also set the mark.
    * If you type ``ctrl+space`` twice in a row, it will activate the mark, which means "highlight it as a selection". It stays highlighted until you type ``ctrl+g`` or  execute certain commands.
    * If you supply a numeric argument, e.g., ``ctrl+u ctrl+x ctrl+x`` or ``ctrl+u ctrl+space``, it will activate the mark without moving the cursor so you can see the  current emacs region.
    * If you use the mouse to make a selection, it will set the mark and it will become the emacs region as well.
  * ``ctrl+o``: Open line.
  * ``meta+g``: Goto line via numeric argument, e.g., ``meta+4 meta+3 meta+5 meta+g`` goes to line 435. (meta+g is not a great choice on Mac OS X I realize.)
  * ``ctrl+l``: Center current line in view. With numeric argument, put the current line at the Nth line on the screen.
  * ``meta+backslash``: Delete white space around point.
  * ``ctrl+x 2``, ``ctrl+x 1``, ``ctrl+x d``, ``ctrl+x-o``: split window, delete all other windows, delete current window, go to other window.
  * ``ctrl+s`` and ``ctrl+r``: proper emacs-style incremental search with Sublime Text multi-cursor extensions.
    * With a numeric argument ``ctrl+u ctrl+s`` does a regex search instead.
    * When you press ``ctrl+s`` immediately after the first ``ctrl+s`` it will use the same search string as last time.
    * If you type any uppercase characters in your search, the search automatically becomes case-sensitive.
    * While searching, each time you type ``ctrl+s`` you will skip ahead to the next match.
    * While searching, ``meta+d`` is like ``ctrl+s`` except the current match is kept as a future cursor (for when you finish the search).
    * If you change your mind about a ``meta+d`` or ``ctrl+s``, you can press ``Backspace`` to undo it.
    * When you type ``meta+a`` all remaining matches from your current position to the end of the file (or beginning if you're doing a reverse search) are added to the  kept matches.
    * When you type ``Backspace`` you are restored you to your previous search state. It will go back to a previous match or delete a character from your search string  or remove the last kept match.
    * When you type ``ctrl+w`` while searching, the characters from your buffer are appended to your search string.
    * If your search is currently failing, you can type ``ctrl+g`` to go back to the last point your search was succeeding. If you type ``ctrl+g`` when your search is  succeeding, the search is aborted and you go back to the start.
    * Clicking the mouse will end the search at the current location, as will opening an overlay.
    * You can end your search by typing many regular emacs commands, e.g., ``ctrl+a``, ``meta+f``, ``ctrl+l``, ``meta+<``, ``meta+>``.
    * Press ``Return`` to end your search with all the kept items as multi-cursors.
    * When you complete (as opposed to abort) a search your mark is set to where you started from.
  * Rectangular cut and insert using ``C-x r t`` and ``C-x r d``
  * ``alt+/`` is used for tab completion since ``tab`` is bound to reindent
  * ``alt+z`` zap-to-char, delete from current point until next occurrence of character
  * ``ctrl+x, ctrl+b`` will present a list of open buffers
  * ``ctrl+x, (`` and ``ctrl+x, )`` will toggle macro recording and execution is done by ``ctrl+x, e``
  * ``ctrl+alt+[`` and ``ctrl+alt+]`` for paragraph navigation
  * Named registers to store data using ``C-x r s [register]`` and ``C-x r i
     [register]``
  * ``ctrl+x r SPC r`` for point-to-register
  * ``ctrl+x r j r`` for jump to point in register
  * ``ctrl+x r s r`` for text-to-register
  * ``ctrl+x r i r`` for insert text from register
  * And many more, most likely a key binding that you expect from Emacs will
    work as well in sublemacs


## Key Map

The key bindings are strictly oriented on their original Emacs counterpart,
however, sometimes the action might be a little different due to other
semantics.

## Future

We will try to extend this more and more to provide more features from Emacs to
Sublime Text and make this my fast and beautiful Emacs replacement.


### Authors and Contributors
2012-2014 Martin Grund (@grundprinzip), Brian M. Clapper (@bmc), Jonathan Payne (@canoeberry)

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
