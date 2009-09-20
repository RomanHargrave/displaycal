#!/usr/bin/env python
# -*- coding: utf-8 -*-

import wx
import wx.grid

wx.BitmapButton._SetBitmapLabel = wx.BitmapButton.SetBitmapLabel

def SetBitmapLabel(self, bitmap):
	""" Replacement for SetBitmapLabel which avoids flickering """
	if self.GetBitmapLabel() != bitmap:
		self._SetBitmapLabel(bitmap)

wx.BitmapButton.SetBitmapLabel = SetBitmapLabel


def BitmapButtonEnable(self, enable = True):
	"""
	Replacement for BitmapButton.Enable which circumvents repainting issues
	
	(bitmap does not change on button state change)
	
	"""
	wx.Button.Enable(self, enable)
	if not hasattr(self, "_bitmaplabel"):
		self._bitmaplabel = self.GetBitmapLabel()
	if not hasattr(self, "_bitmapdisabled"):
		self._bitmapdisabled = self.GetBitmapDisabled()
	if enable:
		if not self._bitmaplabel.IsNull():
			self.SetBitmapLabel(self._bitmaplabel)
	else:
		if not self._bitmapdisabled.IsNull():
			self.SetBitmapLabel(self._bitmapdisabled)

def BitmapButtonDisable(self):
	"""
	Replacement for BitmapButton.Disable which circumvents repainting issues
	
	(bitmap does not change on button state change)
	
	"""
	self.Enable(False)

wx.BitmapButton.Enable = BitmapButtonEnable
wx.BitmapButton.Disable = BitmapButtonDisable


def FindMenuItem(self, label):
	""" Replacement for wx.Menu.FindItem """
	for menuitem in self.GetMenuItems():
		if menuitem.Label == label:
			return menuitem.GetId()

wx.Menu.FindItem = FindMenuItem


wx.Window._SetToolTipString = wx.Window.SetToolTipString

def SetToolTipString(self, string):
	""" Replacement for SetToolTipString which updates correctly """
	wx.Window.SetToolTip(self, None)
	wx.Window._SetToolTipString(self, string)

wx.Window.SetToolTipString = SetToolTipString


def GridGetSelection(self):
	""" Return selected rows, cols, block and cells """
	sel = []
	numrows = self.GetNumberRows()
	numcols = self.GetNumberCols()
	# rows
	rows = self.GetSelectedRows()
	for row in rows:
		if row > -1 and row < numrows:
			for i in range(numcols):
				if not (row, i) in sel:
					sel += [(row, i)]
	# cols
	cols = self.GetSelectedCols()
	for col in cols:
		if col > -1 and col < numcols:
			for i in range(numrows):
				if not (i, col) in sel:
					sel += [(i, col)]
	# block
	tl = self.GetSelectionBlockTopLeft()
	br = self.GetSelectionBlockBottomRight()
	if tl and br:
		for n in range(min(len(tl), len(br))):
			for i in range(tl[n][0], br[n][0] + 1): # rows
				if i > -1 and i < numrows:
					for j in range(tl[n][1], br[n][1] + 1): # cols
						if j > -1 and j < numcols and not (i, j) in sel:
							sel += [(i, j)]
	# single selected cells
	cells = self.GetSelectedCells()
	for cell in cells:
		if not -1 in cell and cell[0] < numrows and cell[1] < numcols and \
		   cell not in sel:
			sel += [cell]
	sel.sort()
	return sel

wx.grid.Grid.GetSelection = GridGetSelection


wx._ScrolledWindow = wx.ScrolledWindow

class ScrolledWindow(wx._ScrolledWindow):

	"""
	ScrolledWindow that scrolls child controls into view on focus.
	
	OnChildFocus and ScrollChildIntoView borrowed from wx.lib.scrolledpanel.
	"""

	def __init__(self, *args, **kwargs):
		wx._ScrolledWindow.__init__(self, *args, **kwargs)
		self.Bind(wx.EVT_CHILD_FOCUS, self.OnChildFocus)

	def OnChildFocus(self, evt):
		# If the child window that gets the focus is not visible,
		# this handler will try to scroll enough to see it.
		evt.Skip()
		child = evt.GetWindow()
		self.ScrollChildIntoView(child)

	def ScrollChildIntoView(self, child):
		"""
		Scrolls the panel such that the specified child window is in view.
		"""        
		sppu_x, sppu_y = self.GetScrollPixelsPerUnit()
		vs_x, vs_y   = self.GetViewStart()
		cr = child.GetRect()
		clntsz = self.GetClientSize()
		new_vs_x, new_vs_y = -1, -1

		# is it before the left edge?
		if cr.x < 0 and sppu_x > 0:
			new_vs_x = vs_x + (cr.x / sppu_x)

		# is it above the top?
		if cr.y < 0 and sppu_y > 0:
			new_vs_y = vs_y + (cr.y / sppu_y)

		# For the right and bottom edges, scroll enough to show the
		# whole control if possible, but if not just scroll such that
		# the top/left edges are still visible

		# is it past the right edge ?
		if cr.right > clntsz.width and sppu_x > 0:
			diff = (cr.right - clntsz.width) / sppu_x
			if cr.x - diff * sppu_x > 0:
				new_vs_x = vs_x + diff + 1
			else:
				new_vs_x = vs_x + (cr.x / sppu_x)
				
		# is it below the bottom ?
		if cr.bottom > clntsz.height and sppu_y > 0:
			diff = (cr.bottom - clntsz.height) / sppu_y
			if cr.y - diff * sppu_y > 0:
				new_vs_y = vs_y + diff + 1
			else:
				new_vs_y = vs_y + (cr.y / sppu_y)

		# if we need to adjust
		if new_vs_x != -1 or new_vs_y != -1:
			#print "%s: (%s, %s)" % (self.GetName(), new_vs_x, new_vs_y)
			self.Scroll(new_vs_x, new_vs_y)

wx.ScrolledWindow = ScrolledWindow
