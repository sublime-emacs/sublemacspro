# Welcome to SublemacsPro.

The reasoning behind writing these set of functions is that I love Emacs,
however, the UI doesn't feel as snappy as other Mac apps. On the other hand I
cannot move to another editor since many of those hyped editors is that they
don't provide the keybindings I love.

Then, I found Sublime Text 2. A completely customizable editor allowing you to
easily modify all default behaviors so that they suit your editing style.

So I wrote sublemacspro bringing Emacs keybindings and sugar to Sublime Text 2.
Even though Emacs lives from the plugins, I believe it is way easier to write
new plugins in Python and integrate them in an Emacs-ish way to Sublime Text 2
than writing them in Lisp.

## Installation

To install SublemacsPro you have to install [Package
Control](http://wbond.net/sublime_packages/package_control) as an automatic
package manager for Sublime Text 2. Now you can easily install Sublemacs Pro and
your installation will never be outdated. When you installed Package Control,
hit ``S-Shift P`` to open up the command palette and type ``install``. Now
select "Package Control: Install Package". This will load all packages from the
remote repository and you can select ``sublemacspro`` from the drop-down list.

## Sublime Text 3 Support

Currently, we are working on Sublime Text 3 support. Most of the features should
work and some bugs with regard to Python 3 are already fixed. So feel free to
try the Package Control Beta for ST3 and install sublemacspro. If there are any
issues feel free to report them.

## Features

The following features are supported and merged [from][ot3] [other][ot] [approaches][ot2]
and the base code of the new beta of [Sublime Text 2][subl].

   * Kill line, region ... with kill ring. All the sugar you love with a nice UI
     with ``M-w``, ``C-w``, ``C-y``
   * Yank with free choice from kill ring using fancy overlay: Just press
     ``C-Y`` to access the kill ring and search for your last copy and pastie
   * Rectangular cut and insert using ``C-x r t`` and ``C-x r d``
   * Named registers to store data using ``C-x r s [register]`` and ``C-x r i
     [register]``
   * Open a new line by ``C+o``
   * Automatic mode detection like it's done in Emacs using prefixes ``-*- c++ -*-``
   * ``ctrl+a`` and ``ctrl+e`` find the hard EOL / BOL
   * ``alt+a`` will go to soft BOL
   * ``ctrl+s`` and ``ctrl+r`` work like expected from Emacs with repeatedly
     pressing ``ctrl+s`` for navigating to the next occurrence
   * ``ctrl+g`` will try to exit any kind of overlays, exit snippet mode etc
   * ``alt+/`` is used for tab completion since ``tab`` is bound to reindent
   * ``alt+z`` zap-to-char, delete from current point until next occurrence of character
   * ``ctrl+x, ctrl+b`` will present a list of open buffers
   * ``ctrl+x, (`` and ``ctrl+x, )`` will toggle macro recording and execution is done by ``ctrl+x, e``
   * ``ctrl+alt+[`` and ``ctrl+alt+]`` for paragraph navigation
   * And many more, most likely a key binding that you expect from Emacs will
     work as well in sublemacs


## Key Map

The key bindings are strictly oriented on their original Emacs counterpart,
however, sometimes the action might be a little different due to other
semantics.

## Future

We will try to extend this more and more to provide more features from Emacs to
Sublime Text 2 and make this my fast and beautiful Emacs replacement.


### Authors and Contributors
2012 Martin Grund (@grundprinzip), Brian M. Clapper (@bmc)

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
