import functools as fu
import sublime, sublime_plugin

class SbpOpenLineCommand(sublime_plugin.TextCommand):
    '''
    Emacs-style 'open-line' command: Inserts a newline at the current
    cursor position, without moving the cursor like Sublime's insert
    command does.
    '''
    def run(self, edit):
        sel = self.view.sel()
        if (sel is None) or (len(sel) == 0):
            return

        point = sel[0].end()
        self.view.insert(edit, point, '\n')
        self.view.run_command('move', {'by': 'characters', 'forward': False})


class SbpRecenterInView(sublime_plugin.TextCommand):
    '''
    Reposition the view so that the line containing the cursor is at the
    center of the viewport, if possible. Unlike the corresponding Emacs
    command, recenter-top-bottom, this command does not cycle through
    scrolling positions. It always repositions the view the same way.

    This command is frequently bound to Ctrl-l.
    '''
    def run(self, edit):
        self.view.show_at_center(self.view.sel()[0])

class SbpRectangleDelete(sublime_plugin.TextCommand):
	def run(self, edit, **args):
		sel = self.view.sel()[0]
		b_row, b_col = self.view.rowcol(sel.begin())
		e_row, e_col = self.view.rowcol(sel.end())

		# Create rectangle
		top = b_row
		left = min(b_col, e_col)

		bot = e_row
		right = max(b_col, e_col)
		
		# For each line in the region, replace the contents by what we
		# gathered from the overlay
		current_edit = self.view.begin_edit()
		for l in range(top, bot + 1):
			r = sublime.Region(self.view.text_point(l, left), self.view.text_point(l, right))
			if not r.empty():
				self.view.erase(current_edit, r)
				
		self.view.end_edit(edit)
		self.view.run_command("sbp_cancel_mark")


class SbpRectangleInsert(sublime_plugin.TextCommand):
	def run(self, edit, **args):
		self.view.window().show_input_panel("Content:", "", fu.partial(self.replace, edit), None, None)

	def replace(self, edit, content):

		sel = self.view.sel()[0]
		b_row, b_col = self.view.rowcol(sel.begin())
		e_row, e_col = self.view.rowcol(sel.end())

		# Create rectangle
		top = b_row
		left = min(b_col, e_col)

		bot = e_row
		right = max(b_col, e_col)
		
		# For each line in the region, replace the contents by what we
		# gathered from the overlay
		current_edit = self.view.begin_edit()
		for l in range(top, bot + 1):
			r = sublime.Region(self.view.text_point(l, left), self.view.text_point(l, right))
			if not r.empty():
				self.view.erase(current_edit, r)
			
			self.view.insert(current_edit, self.view.text_point(l, left), content)
		self.view.end_edit(edit)
		self.view.run_command("sbp_cancel_mark")
		

