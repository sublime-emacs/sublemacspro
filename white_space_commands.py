###################################
# delete blank lines around point #
###################################

import os, re

import sublime, sublime_plugin

from .lib.misc import *

#
# Emacs delete-white-space command.
#
class SbpDeleteWhiteSpaceCommand(SbpTextCommand):
    def run_cmd(self, util, keep_spaces=0):
        if util.has_prefix_arg():
            keep_spaces = util.get_count()
        util.for_each_cursor(self.delete_white_space, util, can_modify=True, keep_spaces=keep_spaces)

    def delete_white_space(self, cursor, util, keep_spaces=0):
        view = self.view
        line = view.line(cursor.a)
        data = view.substr(line)
        row,col = view.rowcol(cursor.a)
        start = col
        while start - 1 >= 0 and data[start-1: start] in (" \t"):
            start -= 1
        end = col
        limit = len(data)
        while end < limit and data[end:end+1] in (" \t"):
            end += 1

        if end - start > keep_spaces:
            end -= keep_spaces
            if end > start:
                view.erase(util.edit, sublime.Region(line.begin() + start, line.begin() + end))
                if keep_spaces > 0:
                    # this is more expensive so we only do it if keep_spaces > 0, in which case we
                    # want the cursor to be on the right side of the kept spaces
                    return sublime.Region(line.begin() + start + keep_spaces)

        return None

#
# From emacs:
#
# On blank line, delete all surrounding blank lines, leaving just one.
# On isolated blank line, delete that one.
# On nonblank line, delete any immediately following blank lines.
#
class SbpDeleteBlankLinesCommand(SbpTextCommand):
    def run_cmd(self, util, **kwargs):
        util.for_each_cursor(self.delete_blank_lines, util, can_modify=True, **kwargs)

    def delete_blank_lines(self, cursor, util, keep_lines=0):
        view = self.view

        # initialize we don't plan on leaving one line blank
        leave_one = False

        # if current line is blank, delete surrounding blank lines
        region = self.is_blank(cursor.b)
        if region is not None:
            leave_one = True
        else:
            # check the next line
            line = self.view.line(cursor.b)
            region = self.is_blank(line.b + 1)
            if region is None:
                # nothing to do - this line and the next are not blank
                return None

        # Region now contains one line that needs deleting. Now we expand in both directions as long
        # as there are blank lines.
        view_size = view.size()

        # do lines below first
        while region.end() < view_size:
            line = self.is_blank(region.end())
            if line is not None:
                region = region.cover(line)
            else:
                break

        # now lines above
        while region.begin() - 1 > 0:
            line = self.is_blank(region.begin() - 1)
            if line is not None:
                region = region.cover(line)
            else:
                break

        # end of buffer is special case (line looks blank because it's the end of buffer)
        if region.end() == view_size:
            leave_one = False
        view.replace(util.edit, region, "\n" if leave_one else "")
        return None

    def is_blank(self, pos):
        view = self.view
        view_size = view.size()
        if pos > view_size:
            return None
        region = view.line(pos)
        text = view.substr(region)
        if re.match(r'^[ \t]*$', text):
            # extend region over the newline
            if region.b < view_size:
                region.b += 1
            return region
        return None
