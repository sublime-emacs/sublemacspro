# sublemacspro makes Sublime Text 2 your Emacs replacement

The reasoning behind writing these set of functions is that I love Emacs;
however, the UI doesn't feel as snappy as other Mac apps. On the other hand, 
I cannot move to another editor, since many of those *hyped* editors is 
that they don't provide the keybindings I love.

Then, I found Sublime Text 2, a completely customizable editor allowing you
to easily modify all default behaviors so that they suit your editing style.

So I wrote *sublemacspro*, bringing Emacs keybindings and sugar to Sublime Text
2. Even though Emacs lives from the plugins, I beleive it is way easier to
write new plugins in Python and integrate them in an Emacs-ish way to Sublime
Text 2, than writing them in Lisp.

## Features

The following features are supported and merged [from][ot3] [other][ot] [approaches][ot2]
and the base code of the new beta of [Sublime Text 2][subl].

* Kill line, region ... with kill ring. All the sugar you love with a nice UI
  with `M-w`, `C-w`, `C-y`
* Yank with free choice from kill ring using fancy overlay: Just press ``C-Y``
  to access the kill ring and search for your last copy and pastie
* Rectangular cut and insert using `C-x r t` and `C-x r d`
* Named registers to store data using `C-x r s [register]` and
  `C-x r i [register]`

## Key Map

The key bindings are strictly oriented on their original Emacs counterpart,
however, sometimes the action might be a little different due to other
semantics.

## Future

I will try to extend this more and more to provide more features from Emacs to
Sublime Text 2 and make this my fast and beautiful Emacs replacement.

## Contributors

* [Brian M. Clapper][bmc] provided lots of inspiration and code for this
  [plugin.

[ot]: https://github.com/stiang/EmacsifySublimeText
[ot2]: https://github.com/bmc/ST2EmacsMiscellanea
[ot3]: https://github.com/stiang/EmacsKillRing
[subl]: http://www.sublimetext.com/docs/2/api_reference.html
[bmc]: https://github.com/bmc/
