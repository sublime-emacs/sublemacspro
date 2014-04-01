# This is Sublime Jove

This is a plugin for Sublime Text 3.

This is my attempt at bringing some of the basic emacs functionality to Sublime Text. Other attempts
have been great but they weren't quite right so I decided to try my own. Along the way I have
learned an awful lot from reading the Sublemacspro plugin and in some places I have stolen
mercilessly from their ideas.

I have been using emacs for over 35 years and in my youth I implemented a version of emacs called
JOVE - Jonathan's Own Version of Emacs. That is where this plugin got its name.

## Installation

This is not in Package Control yet. Just put this folder in your Packages directory for now.

## Sublime Text 2 or 3?

This has been developed using Sublime Text 3. It currently does not work in ST2. There is hope for
much of what I have done and if there's enough desire I will try to get it working.

## Features

Here are the main set of commands I have implemented or adjusted to conform to proper emacs behavior.

   * ``ctrl+u``, ``meta+0`` ... ``meta+9``: Emacs universal argument - you provide a prefix arguments to a command to run it that many times. E.g., ``meta+2`` ``meta+3`` ``ctrl+F`` means go forward 23 characters.
   * ``meta+f`` and ``meta+b``: Forward and backward words with the same exact behavior of emacs in terms of how you move.
   * ``ctrl+meta+f`` and ``ctrl+meta+b``: Forward and backward s-expressions. It works for skipping over identifiers, strings and parentheses, braces and square brackets.
   * ``meta+c``, ``meta+l``, ``meta+u``: capitalize, lower case, upper case words. They support numeric arguments, including negative arguments which means "do it to the previous N words".
   * Full emacs kill ring support:
     * 64 entries - not currently adjustable
     * adjascent kill commands are appended to the same entry
     * ``ctrl+w`` and ``meta+w``: kill and copy to the kill ring.
     * ``ctrl+y`` and ``meta+y``: yank and yank-pop.
     * technically supplying a numeric argument to ``ctrl+d`` and ``Backspace`` should append to the kill ring but I have not done that (yet).
     * The yank command will pull from the clipboard if it finds it is not the same as the current kill-ring entry, meaning you can go into a different app and copy something there and paste it into emacs using ``ctrl+y``. Also, anything you kill in emacs will be placed on the clipboard for other apps to access.
   * ``meta+d`` and ``meta+Backspace``: Delete word forward and backward, placinging the deleted text on the kill ring.
   * ``ctrl+meta+k``: Delete S-Expression and place on the kill ring. (Negative arguments not supported.)
   * ``ctrl+k``: Kill to end of line mimics emacs almost exactly (it does not support a 0 numeric argument to delete to the beginning of the line). Providing a numeric argument means "delete that many lines" which is different from typing ``ctrl+k`` that many times.
   * ``meta+<`` and ``meta+>``: move to beginning and end of file.
   * ``meta+,`` and ``meta+.``: move to beginning and end of window.
   * Support for a emacs-style mark including the mark-ring:
     * ``ctrl+space`` to push a new mark onto the ring
     * ``ctrl+x ctrl+x`` to switch point and mark
     * Commands such as ``ctrl+y``, ``meta+y`` set the mark automatically as they do (and must) in emacs.
     * ``meta+<`` and ``meta+>`` also set the mark.
     * If you type ``ctrl+space`` twice in a row, it will activate the mark, which means "highlight it as a selection". It stays highlighted until you type ``ctrl+g`` or execute certain commands.
     * If you supply a numeric argument, e.g., ``ctrl+u ctrl+x ctrl+x`` or ``ctrl+u ctrl+space``, it will activate the mark without moving the cursor so you can see the current emacs region.
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
     * When you type ``meta+a`` all remaining matches from your current position to the end of the file (or beginning if you're doing a reverse search) are added to the kept matches.
     * When you type ``Backspace`` you are restored you to your previous search state. It will go back to a previous match or delete a character from your search string or remove the last kept match.
     * When you type ``ctrl+w`` while searching, the characters from your buffer are appended to your search string.
     * If your search is currently failing, you can type ``ctrl+g`` to go back to the last point your search was succeeding. If you type ``ctrl+g`` when your search is succeeding, the search is aborted and you go back to the start.
     * Clicking the mouse will end the search at the current location, as will opening an overlay.
     * You can end your search by typing many regular emacs commands, e.g., ``ctrl+a``, ``meta+f``, ``ctrl+l``, ``meta+<``, ``meta+>``.
     * Press ``Return`` to end your search with all the kept items as multi-cursors.
     * When you complete (as opposed to abort) a search your mark is set to where you started from.

## Multiple Cursors

Where possible I tried to make JOVE commands compatible with multiple cursors. So if there are
multiple cursors active it is possible to use the motion commands (word, s-expression, characters)
as well as the delete word, etc. commands. If you run the kill-line command ``ctrl+k`` in multi-
cursor mode, it will do what you expect but the data is not pushed onto the kill-ring because I
think it's hard to explain and understand. I think UNDO is the best approach for this.


## Philosophy

It is my goal to embrace all that is fantastic about Sublime Text and not try to re-implement emacs
in Sublime. But the truth of the matter is, there are many basic things that emacs got exactly right
40 years ago and they are worth preserving. I intend to continue to improve some of those basics
while adopting as many Sublime approaches as possible.

### Author
Jonathan Payne (@canoeberry on twitter)
