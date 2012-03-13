# sublemacspro makes Sublime Text 2 your Emacs replacement

The reasoning behind writing these set of functions is that I love Emacs,
however, I don't like the UI and I feel that sometimes it just feels slow. My
biggest problem with current "hyped" editors is that they don't support my
native way of interacting with text requiring to use the mouse too often.

But, now there is sublemacs pro that brings Emacs feeling to your editor

## Features

The following features are supported and merged from [other][ot] approaches
and the base code of the new beta of [Sublime Text 2][subl].

   * Kill line, region ... with kill ring
   * Yank with free choice from kill ring using fancy overlay
   * Rectangular cut and insert using ``C-x r t`` and ``C-x r d``
   * Named registers to store data using ``C-x r s [register]`` and ``C-x r i [register]``


## Key Map

The key bindings are strictly oriented on their original Emacs counterpart,
however, sometimes the action might be a little different due to other
semantics.


## Future

I will try to extend this more and more to provide more features from Emacs to
Sublime Text 2 and make this my fast and beautiful Emacs replacement.


[ot]: https://github.com/stiang/EmacsifySublimeText
[subl]: http://www.sublimetext.com/docs/2/api_reference.html
