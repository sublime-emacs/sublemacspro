import unittest
import functools

def cmp_cells(ea,eb):
  a = ea[1]
  b = eb[1]
  if a[1] < b[1]:
    return -1
  elif a[1] == b[1]:
    if a[0] < b[0]:
      return -1
    else:
      return 1
  else:
    return 1


class LayoutManager:
  """ Manages the layout of a sublime window."""

  MAX_COLS = 20
  MAX_ROWS = 20

  def _buildCoordCells(self):
    self.coord_cells = [ [self._col_val(x[0]), self._row_val(x[1]), self._col_val(x[2]), self._row_val(x[3])]  for x in self.grid["cells"]]

  def _col_val(self, index):
    return self.cols()[index]

  def _row_val(self, index):
    return self.rows()[index]

  def _cell(self, index):
    return self.coord_cells[index]

  def _replace(self, index, result):
    """ Takes an input index and removes the cell at this index and injects
    the range given by result into the coord_cells
    """
    left, right = self.coord_cells[0:index], self.coord_cells[index+1:]
    self.coord_cells = left + [result[0]] + right + [result[1]]

  def __init__(self, grid):
    if grid:
      self.grid = grid
      self._buildCoordCells()
      self._col_count = len(self.cols())
      self._row_count = len(self.rows())

  def cols(self):
    return self.grid["cols"]

  def rows(self):
    return self.grid["rows"]

  def split(self, index, mode):
    """Splits a cell identified by index into two.

    The split itself is described by the mode parameter and can be either
    horizontal or vertical

    mode: v | h
    """
    if self._col_count + 1 > LayoutManager.MAX_COLS and mode == "v":
      return False

    if self._row_count +1 > LayoutManager.MAX_ROWS and mode == "h":
      return False

    current = self._cell(index)

    # Depending on the split calculate the new offsets
    if mode == "v":
      self._col_count += 1
      delta = (current[2] - current[0]) / 2.0
      result = [ [current[0], current[1], current[0] + delta, current[3]], [current[0]+delta, current[1], current[2], current[3]] ]
    else:
      self._row_count += 1
      delta = (current[3] - current[1]) / 2.0
      result = [ [current[0], current[1], current[2], current[1] + delta], [current[0], current[1] + delta, current[2], current[3]] ]

    self._replace(index, result)
    return True

  def killSelf(self, index):
    """
    Takes the cell identified by index and removes it from the list of cells.
    While in original emacs the order of created cells are tracked, we need to
    improvise here a bit. We first try to merge clockwise.
    """
    if self._col_count == 2 and self._row_count == 2:
      return

    cell = self.coord_cells[index]
    del(self.coord_cells[index])

    # First check if there are neighbouring cells atop or below
    expand = []

    # Shift top
    expand += [[i, 1] for i, x in enumerate(self.coord_cells) if x[1] == cell[3] and x[0] >= cell[0] and x[2] <= cell[2]]
    # Shift down
    expand += [[i, 3] for i, x in enumerate(self.coord_cells) if x[3] == cell[1] and x[0] >= cell[0] and x[2] <= cell[2]]
    # Shift right
    expand += [[i, 2] for i, x in enumerate(self.coord_cells) if x[2] == cell[0] and x[1] >= cell[1] and x[3] <= cell[3]]
    # Shift left
    expand += [[i, 0] for i, x in enumerate(self.coord_cells) if x[0] == cell[2] and x[1] >= cell[1] and x[3] <= cell[3]]

    # Replace the values with their default
    for match in expand:
      self.coord_cells[match[0]][match[1]] = cell[match[1]]

  def killOther(self, index):
    """
    """
    self.coord_cells = [[0.0, 0.0, 1.0, 1.0],]

  def build(self):
    """
    Based on the cells with absolute coordinates build the structure required
    for sublime text
    """
    col_list = sorted(list(set(sum([[x[0], x[2]] for x in self.coord_cells], []))))
    cols = dict([ [v,k] for k,v in enumerate(col_list)])

    row_list = sorted(list(set(sum([[x[1], x[3]] for x in self.coord_cells], []))))
    rows = dict([ [v,k] for k,v in enumerate(row_list)])

    result = {
      "cols" : sorted(list(cols.keys())),
      "rows" : sorted(list(rows.keys())),
      "cells" : [ [  cols[cell[0]], rows[cell[1]], cols[cell[2]], rows[cell[3]]  ] for cell in self.coord_cells ]
    }
    return result

  def next(self, index, direction=1):
    """
    Find the visually next cell for the given index. This must not necessarily
    be the adjacent cell in the list
    """
    cell = self.grid["cells"][index]
    # Sort the cells
    new_grid = sorted(enumerate(self.grid["cells"]), key=functools.cmp_to_key(cmp_cells), reverse=False)
    new_pos = [i for i, x in enumerate(new_grid) if x[1] == cell].pop()

    # find the position of the old cell and get the new index
    return new_grid[(new_pos + direction) % len(self.grid["cells"])][0]

  def extend(self, index, direction, unit, count):
    """
    Grows / shrinks the cell give the direction. It copies the emacs algorithm
    to do that. Which does the following.

      * growing horizontally goes right first, if not possible go left
      * growing vertically goes down first, if not top
    """

    # figure out which row or col entry we're going to adjust and make sure not to allow any
    # adjascent rows/cols to get too close to each other
    cell = self.grid["cells"][index]
    rows = self.rows()
    cols = self.cols()
    amount = unit * count

    if "s" in direction:
      amount = -amount
    x1,y1,x2,y2 = cell
    if direction in ('g', 's') and (y1 > 0 or y2 < self._row_count - 1):
      # adjust heights
      if y2 == self._row_count - 1:
        # Never adjust top or bottom: they should be 0 and 1.0 always, so when at the top or the
        # bottom move inward.
        y2 = abs(y2 - 1)
        amount = -amount

      # check for too small height
      new_pos = rows[y2] + amount
      min_height = 5 * unit
      if new_pos - rows[y2 - 1] >= min_height and rows[y2 + 1] - new_pos >= min_height:
        rows[y2] = new_pos
    elif direction in ('gh', 'sh') and (x1 > 0 or x2 < self._col_count - 1):
      # adjust widths
      if x2 == self._col_count - 1:
        # Never adjust left or right: they should be 0 and 1.0 always, so when at the left or the
        # right move inward.
        x2 = abs(x2 - 1)
        amount = -amount

      # check for too small width
      min_width = 20 * unit
      new_pos = cols[x2] + amount
      if new_pos - cols[x2 - 1] >= min_width and cols[x2 + 1] - new_pos >= min_width:
        cols[x2] = new_pos

    return self.grid



# Test Code below
class TestLayoutManager(unittest.TestCase):

  def setUp(self):
    self.base = {'cols': [0.0, 1.0], 'rows': [0.0, 1.0], 'cells': [[0, 0, 1, 1]]}
    self.hbase = {'cols': [0.0, 1.0], 'rows': [0.0, 0.5, 1.0], 'cells': [[0, 0, 1, 1], [0, 1, 1, 2]]}
    self.vbase = {'cols': [0.0, 0.5, 1.0], 'rows': [0.0, 1.0], 'cells': [[0, 0, 1, 1], [1,0,2,1]]}
    self.vhbase = {'cols': [0.0, 0.5, 1.0], 'rows': [0.0, 0.5, 1.0], 'cells': [[0, 0, 1, 1], [1,0,2,1],[0, 1, 1, 2], [1,1,2,2]]}


  def testKillSelfComplicated(self):
    lm = LayoutManager(self.base)
    lm.split(0, 'v')
    lm.split(0, 'h')
    lm.killSelf(2)
    self.assertEqual(self.hbase, lm.build())

    lm.killOther(0)
    lm.split(0, 'v')
    lm.split(1, 'h')
    lm.killSelf(0)
    self.assertEqual(self.hbase, lm.build())



  def testKillSelf(self):
    lm = LayoutManager(self.base)
    lm.killSelf(0)
    self.assertEqual(self.base, lm.build())

    lm.split(0, 'h')
    self.assertEqual(self.hbase, lm.build())
    lm.killSelf(1)
    self.assertEqual(self.base, lm.build())

    lm.split(0, 'h')
    self.assertEqual(self.hbase, lm.build())
    lm.killSelf(0)
    self.assertEqual(self.base, lm.build())

    lm.split(0, 'v')
    self.assertEqual(self.vbase, lm.build())
    lm.killSelf(0)
    self.assertEqual(self.base, lm.build())

    lm.split(0, 'v')
    self.assertEqual(self.vbase, lm.build())
    lm.killSelf(1)
    self.assertEqual(self.base, lm.build())

  def testBasicValues(self):
    lm = LayoutManager(self.base)
    self.assertEqual(2, len(lm.cols()))
    self.assertEqual(2, len(lm.rows()))

  def testCreateMapping(self):
    lm = LayoutManager(self.hbase)
    self.assertEqual([[0.0, 0.0, 1.0, 0.5],[0.0, 0.5, 1.0, 1.0]], lm.coord_cells)

  def testReplaceCells(self):
    lm = LayoutManager(self.hbase)
    new_split = [[0.0, 0.0, 0.5, 0.5], [0.5, 0.0, 1.0, 0.5]]
    lm._replace(0, new_split)
    self.assertEqual(new_split[0], lm.coord_cells[0])
    self.assertEqual(new_split[1], lm.coord_cells[1])


  def testSplitVertical(self):
    lm = LayoutManager(self.hbase)
    lm.split(0, 'v')
    new_split = [[0.0, 0.0, 0.5, 0.5], [0.5, 0.0, 1.0, 0.5], [0.0, 0.5, 1.0, 1.0]]
    self.assertEqual(new_split, lm.coord_cells)

    lm = LayoutManager(self.vbase)
    lm.split(1, 'v')
    new_split = [[0.0, 0.0, 0.5, 1.0], [0.5, 0.0, 0.75, 1], [0.75, 0.0, 1.0, 1.0]]
    self.assertEqual(new_split, lm.coord_cells)


  def testSplitHorizontal(self):
    lm = LayoutManager(self.hbase)
    lm.split(0, 'h')
    new_split = [[0.0, 0.0, 1.0, 0.25], [0.0, 0.25, 1.0, 0.5], [0.0, 0.5, 1.0, 1.0]]
    self.assertEqual(new_split, lm.coord_cells)

    lm = LayoutManager(self.vbase)
    lm.split(1, 'h')
    new_split = [[0.0, 0.0, 0.5, 1.0], [0.5, 0.0, 1.0, 0.5], [0.5, 0.5, 1.0, 1.0]]
    self.assertEqual(new_split, lm.coord_cells)


  def testKillOther(self):
    pass

  def testBuild(self):
    lm = LayoutManager(self.base)
    lm.split(0, 'v')
    result = lm.build()
    #print(result)


  def testShouldNotCreateMoreColsThanMax(self):
    lm = LayoutManager(self.base)
    self.assertEqual(2, lm._col_count)
    lm.split(0, 'v')
    self.assertEqual(3, lm._col_count)
    lm.split(0, 'v')
    self.assertEqual(4, lm._col_count)
    lm.split(0, 'v')
    self.assertEqual(5, lm._col_count)
    lm.split(0, 'v')
    self.assertEqual(6, lm._col_count)

  def testMixMaxCount(self):
    lm = LayoutManager(self.base)
    self.assertEqual(2, lm._col_count)
    self.assertEqual(2, lm._row_count)
    lm.split(0, 'v')
    lm.split(0, 'h')
    lm.split(0, 'v')
    lm.split(0, 'h')
    lm.split(0, 'v')
    lm.split(0, 'h')
    self.assertEqual(5, lm._col_count)
    self.assertEqual(5, lm._row_count)


  def testShouldNotCreateMoreRowsThanMax(self):
    lm = LayoutManager(self.base)
    self.assertEqual(2, lm._row_count)
    lm.split(0, 'h')
    self.assertEqual(3, lm._row_count)
    lm.split(0, 'h')
    self.assertEqual(4, lm._row_count)
    lm.split(0, 'h')
    self.assertEqual(5, lm._row_count)
    lm.split(0, 'h')
    self.assertEqual(6, lm._row_count)


if __name__ == '__main__':
    unittest.main()
