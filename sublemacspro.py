import functools as fu
import sublime, sublime_plugin


class EmacsRectangleDelete(sublime_plugin.TextCommand):
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
		self.view.run_command("cancel_mark")


class EmacsRectangleInsert(sublime_plugin.TextCommand):
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
		self.view.run_command("cancel_mark")
		

