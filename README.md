# Welcome to SublemacsPro.

The reasoning behind writing these set of functions is that I love Emacs, however, the UI doesn't feel as snappy as other Mac apps. On the other hand I cannot move to another editor since many of those hyped editors is that they don't provide the keybindings I love.

Then, I found Sublime Text 2. A completly customizable editor allowing you to easily modify all default behaviors so that they suit your editing sytle.

So I wrote sublemacspro bringing Emacs keybindings and sugar to Sublime Text 2. Even though Emacs lives from the plugins, I beleive it is way easier to write new plugins in Python and integrate them in an Emacs-ish way to Sublime Text 2 than writing them in Lisp.

## Installation

To install SublemacsPro you have to install [Package Control](http://wbond.net/sublime_packages/package_control) as an automatic package manager for Sublime Text 2. Now you can easily install Sublemacs Pro and your installation will never be outdated. When you installed Package Control, hit ``S-Shift P`` to open up the command palette and type ``install``. Now select "Package Control: Install Package". This will load all packages from the remote repository and you can select ``sublemacspro`` from the drop-down list.

## Features

The following features are supported and merged [from][ot3] [other][ot] [approaches][ot2]
and the base code of the new beta of [Sublime Text 2][subl].

   * Kill line, region ... with kill ring. All the sugar you love with a nice UI with ``M-w``, ``C-w``, ``C-y``
   * Yank with free choice from kill ring using fancy overlay: Just press ``C-Y`` to access the kill ring and search for your last copy and pastie
   * Rectangular cut and insert using ``C-x r t`` and ``C-x r d``
   * Named registers to store data using ``C-x r s [register]`` and ``C-x r i [register]``
   * Open a new line by ``C+o``
   * Find file at point ``M-x f f a p`` opens the file your current cursor points to
   * Automatic mode detection like it's done in Emacs using prefixes ``-*- c++ -*-``
   * And many more ...



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