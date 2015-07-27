# -*- coding: utf-8 -*-

import sys

from meta import wx_minversion

# wxversion will be removed in Phoenix
try:
	import wxversion
except ImportError:
	pass
else:
	if not getattr(sys, "frozen", False):
		wxversion.ensureMinimal("%i.%i" % wx_minversion[:2])
import wx
if wx.VERSION < wx_minversion:
	app = wx.PySimpleApp()
	result = wx.MessageBox("This application requires a version of wxPython "
						   "greater than or equal to %s, but your most recent "
						   "version is %s.\n\n"
						   "Would you like to download a new version of wxPython?\n"
						   % (".".join(str(n) for n in wx_minversion), wx.__version__),
						   "wxPython Upgrade Needed", style=wx.YES_NO)
	if result == wx.YES:
		import webbrowser
		webbrowser.open("http://wxpython.org/")
	app.MainLoop()
	sys.exit()
import wx.grid
from wx.lib.buttons import GenBitmapButton as _GenBitmapButton
from wx.lib.buttons import ThemedGenButton as _ThemedGenButton
from wx.lib.buttons import GenBitmapTextButton as _GenBitmapTextButton
from wx.lib import platebtn


if not hasattr(platebtn, "PB_STYLE_TOGGLE"):
	platebtn.PB_STYLE_TOGGLE = 32


if not hasattr(platebtn, "PB_STYLE_DROPARROW"):
	platebtn.PB_STYLE_DROPARROW = 16


if u"phoenix" in wx.PlatformInfo:
	# Phoenix compatibility

	from wx.lib.agw import aui
	from wx.lib import embeddedimage
	import wx.adv

	# Deprecated items

	wx.DEFAULT    = wx.FONTFAMILY_DEFAULT
	wx.DECORATIVE = wx.FONTFAMILY_DECORATIVE
	wx.ROMAN      = wx.FONTFAMILY_ROMAN
	wx.SCRIPT     = wx.FONTFAMILY_SCRIPT
	wx.SWISS      = wx.FONTFAMILY_SWISS
	wx.MODERN     = wx.FONTFAMILY_MODERN
	wx.TELETYPE   = wx.FONTFAMILY_TELETYPE

	wx.NORMAL = wx.FONTWEIGHT_NORMAL | wx.FONTSTYLE_NORMAL
	wx.LIGHT  = wx.FONTWEIGHT_LIGHT
	wx.BOLD   = wx.FONTWEIGHT_BOLD

	wx.ITALIC = wx.FONTSTYLE_ITALIC
	wx.SLANT  = wx.FONTSTYLE_SLANT

	wx.SOLID       = wx.PENSTYLE_SOLID | wx.BRUSHSTYLE_SOLID
	wx.DOT         = wx.PENSTYLE_DOT
	wx.LONG_DASH   = wx.PENSTYLE_LONG_DASH
	wx.SHORT_DASH  = wx.PENSTYLE_SHORT_DASH
	wx.DOT_DASH    = wx.PENSTYLE_DOT_DASH
	wx.USER_DASH   = wx.PENSTYLE_USER_DASH
	wx.TRANSPARENT = wx.PENSTYLE_TRANSPARENT | wx.BRUSHSTYLE_TRANSPARENT

	wx.STIPPLE_MASK_OPAQUE = wx.BRUSHSTYLE_STIPPLE_MASK_OPAQUE
	wx.STIPPLE_MASK        = wx.BRUSHSTYLE_STIPPLE_MASK
	wx.STIPPLE             = wx.BRUSHSTYLE_STIPPLE
	wx.BDIAGONAL_HATCH     = wx.BRUSHSTYLE_BDIAGONAL_HATCH
	wx.CROSSDIAG_HATCH     = wx.BRUSHSTYLE_CROSSDIAG_HATCH
	wx.FDIAGONAL_HATCH     = wx.BRUSHSTYLE_FDIAGONAL_HATCH
	wx.CROSS_HATCH         = wx.BRUSHSTYLE_CROSS_HATCH
	wx.HORIZONTAL_HATCH    = wx.BRUSHSTYLE_HORIZONTAL_HATCH
	wx.VERTICAL_HATCH      = wx.BRUSHSTYLE_VERTICAL_HATCH

	embeddedimage.PyEmbeddedImage.getBitmap = embeddedimage.PyEmbeddedImage.GetBitmap
	wx.CursorFromImage = wx.Cursor
	wx.EmptyBitmap = wx.Bitmap
	wx.EmptyIcon = wx.Icon
	wx.ImageFromStream = wx.Image
	wx.ListCtrl.InsertStringItem = lambda self, index, label: self.InsertItem(index, label)
	wx.ListCtrl.SetStringItem = lambda self, index, col, label: self.SetItem(index, col, label)
	wx.Menu.RemoveItem = lambda self, item: self.Remove(item)
	wx.NamedColour = wx.Colour
	wx.PyControl = wx.Control
	wx.PyWindow = wx.Window
	wx.PyPanel = wx.Panel
	wx.StockCursor = wx.Cursor
	wx.Window.SetToolTipString = wx.Window.SetToolTip

	# Moved items

	wx.HL_DEFAULT_STYLE = wx.adv.HL_DEFAULT_STYLE
	wx.HyperlinkCtrl = wx.adv.HyperlinkCtrl
	wx.HyperlinkCtrlNameStr = wx.adv.HyperlinkCtrlNameStr
	wx.SOUND_ASYNC = wx.adv.SOUND_ASYNC
	wx.Sound = wx.adv.Sound

	# Removed items

	wx.DC.BeginDrawing = lambda self: None
	wx.DC.DrawRectangleRect = lambda dc, rect: dc.DrawRectangle(rect)
	wx.DC.DrawRoundedRectangleRect = lambda dc, rect, radius: dc.DrawRoundedRectangle(rect, radius)
	wx.DC.EndDrawing = lambda self: None

	def ContainsRect(self, *args):
		if len(args) > 1:
			rect = wx.Rect(*args)
		else:
			rect = args[0]
		return self.Contains(rect)

	wx.Rect.ContainsRect = ContainsRect
	wx.Rect.ContainsXY = lambda self, x, y: self.Contains((x, y))
	wx.RectPS = wx.Rect
	wx.RegionFromBitmap = wx.Region

	def GetItemIndex(self, window):
		for index, sizeritem in enumerate(self.Children):
			if sizeritem.Window == window:
				return index

	wx.Sizer.GetItemIndex = GetItemIndex
	wx.TopLevelWindow.Restore = lambda self: self.Iconize(False)

	# Renamed items

	wx.OPEN = wx.FD_OPEN
	wx.OVERWRITE_PROMPT = wx.FD_OVERWRITE_PROMPT
	wx.SAVE = wx.FD_SAVE

	wx.SystemSettings_GetColour = wx.SystemSettings.GetColour
	wx.SystemSettings_GetFont = wx.SystemSettings.GetFont
	wx.SystemSettings_GetMetric = wx.SystemSettings.GetMetric
	wx.grid.EVT_GRID_CELL_CHANGE = wx.grid.EVT_GRID_CELL_CHANGED
	wx.grid.Grid.wxGridSelectRows = wx.grid.Grid.GridSelectRows
	wx.grid.PyGridCellEditor = wx.grid.GridCellEditor
	wx.grid.PyGridCellRenderer = wx.grid.GridCellRenderer

	# Bugfixes

	if not hasattr(wx.grid.GridEvent, "CmdDown"):
		# This may be a bug in the current development version of Phoenix
		wx.grid.GridEvent.CmdDown = lambda self: False

	# Not sure if this is a bug, but the PositionToXY signature differs from
	# current Phoenix docs. Actual return value is a 3-tuple, not a 2-tuple:
	# (bool inrange, int col, int line)
	PositionToXY = wx.TextCtrl.PositionToXY
	wx.TextCtrl.PositionToXY = lambda self, pos: PositionToXY(self, pos)[1:]

	def TabFrame__init__(self, parent):
		pre = wx.Window.__init__(self)

		self._tabs = None
		self._rect = wx.Rect(0, 0, 200, 200)
		self._tab_ctrl_height = 20
		self._tab_rect = wx.Rect()
		self._parent = parent

		# With Phoenix, the TabFrame is unintentionally visible in the top left
		# corner (horizontal and vertical lines with a length of 20px each that
		# are lighter than the border color if tabs are at the top, or a
		# 20x20px square if tabs are at the bottom). Setting its size to 0, 0
		# prevents this. Also see https://github.com/RobinD42/Phoenix/pull/91
		self.Create(parent, size=(0, 0))

	aui.TabFrame.__init__ = TabFrame__init__


wx._ListCtrl = wx.ListCtrl
wx._SpinCtrl = wx.SpinCtrl
wx._StaticText = wx.StaticText
if "gtk3" in wx.PlatformInfo:
	# GTK3 fixes
	from wx import dataview
	DataViewListCtrl = dataview.DataViewListCtrl

	class ListCtrl(DataViewListCtrl):

		# Implement ListCtrl as DataViewListCtrl
		# Works around header rendering ugliness with GTK3

		def __init__(self, parent, id=wx.ID_ANY, pos=wx.DefaultPosition,
					 size=wx.DefaultSize, style=wx.LC_ICON,
					 validator=wx.DefaultValidator, name=wx.ListCtrlNameStr):
			dv_style = 0
			if style & wx.LC_SINGLE_SEL:
				dv_style |= dataview.DV_SINGLE
			DataViewListCtrl.__init__(self, parent, id, pos, size, dv_style,
									  validator)
			self.Name = name
			self._columns = {}
			self._items = {}
			self.Bind(dataview.EVT_DATAVIEW_SELECTION_CHANGED, self.OnEvent)
			self.Bind(dataview.EVT_DATAVIEW_ITEM_ACTIVATED, self.OnEvent)

		def OnEvent(self, event):
			typeId = event.GetEventType()
			if typeId == dataview.EVT_DATAVIEW_SELECTION_CHANGED.typeId:
				if self.GetSelectedRow() != wx.NOT_FOUND:
					typeId = wx.EVT_LIST_ITEM_SELECTED.typeId
				else:
					typeId = wx.EVT_LIST_ITEM_DESELECTED.typeId
				event = wx.ListEvent(typeId, self.Id)
			elif typeId == dataview.EVT_DATAVIEW_ITEM_ACTIVATED.typeId:
				event = wx.ListEvent(wx.EVT_LIST_ITEM_ACTIVATED.typeId, self.Id)
			event.SetEventObject(self)
			self.GetEventHandler().ProcessEvent(event)

		def InsertColumn(self, pos, col):
			self._columns[pos] = col

		def SetColumnWidth(self, pos, width):
			self.AppendTextColumn(self._columns[pos], width=width)

		def InsertStringItem(self, row, label):
			self._items[row] = []
			return row

		def SetStringItem(self, row, col, label):
			self._items[row].append(label)
			if len(self._items[row]) == len(self._columns):
				# Row complete
				DataViewListCtrl.InsertItem(self, row, self._items[row])

		def GetItem(self, row, col=0):
			item = self.RowToItem(row)
			item.GetId = lambda: row
			item.GetText = lambda: self.GetTextValue(row, col)
			return item

		def SetItemState(self, row, state, stateMask):
			if state == stateMask == wx.LIST_STATE_SELECTED:
				self.SelectRow(row)
			else:
				raise NotImplementedError("SetItemState is only implemented for "
										  "selecting a single row")

		def GetNextItem(self, row, geometry=wx.LIST_NEXT_ALL,
						state=wx.LIST_STATE_DONTCARE):
			if (row == -1 and geometry == wx.LIST_NEXT_ALL and
				state == wx.LIST_STATE_SELECTED):
				return self.GetSelectedRow()
			else:
				raise NotImplementedError("GetNextItem is only implemented for "
										  "returning the selected row")

		def GetItemCount(self):
			return len(self._items)

		GetFirstSelected = DataViewListCtrl.__dict__["GetSelectedRow"]

		def GetItemState(self, row, stateMask):
			if stateMask == wx.LIST_STATE_SELECTED:
				if self.GetSelectedRow() == row:
					return wx.LIST_STATE_SELECTED
				else:
					return 0
			else:
				raise NotImplementedError("GetItemState is only implemented to "
										  "check if a row is selected")

		def Select(self, row, on=1):
			if on:
				self.SelectRow(row)
			else:
				self.UnselectRow(row)

	wx.ListCtrl = ListCtrl

	class SpinCtrl(wx._SpinCtrl):

		_spinwidth = 0

		def __init__(self, parent, id=wx.ID_ANY, value="",
					 pos=wx.DefaultPosition, size=wx.DefaultSize,
					 style=wx.SP_ARROW_KEYS, min=0, max=100, initial=0,
					 name="wxSpinCtrl"):
			if size[0] != -1:
				# Adjust initial size for GTK3 to accomodate spin buttons
				if not SpinCtrl._spinwidth:
					spin = wx.SpinCtrl(parent, -1)
					text = wx.TextCtrl(parent, -1)
					SpinCtrl._spinwidth = spin.Size[0] - text.Size[0] + 11
					spin.Destroy()
					text.Destroy()
				size = size[0] + SpinCtrl._spinwidth, size[1]
			wx._SpinCtrl.__init__(self, parent, id, value, pos, size, style,
								  min, max, initial, name)

	wx.SpinCtrl = SpinCtrl

	_StaticText_SetLabel = wx._StaticText.SetLabel

	class StaticText(wx._StaticText):

		def __init__(self, *args, **kwargs):
			wx._StaticText.__init__(self, *args, **kwargs)

		def SetFont(self, font):
			wx.Control.SetFont(self, font)
			self.SetLabel(self.Label)

		def SetLabel(self, label):
			# Fix GTK3 label auto-resize on label change not working
			if not self.WindowStyle & wx.ST_NO_AUTORESIZE:
				self.MaxSize = -1, -1
				self.MinSize = -1, -1
			_StaticText_SetLabel(self, label)
			if not self.WindowStyle & wx.ST_NO_AUTORESIZE:
				# Find widest line
				max_width = 0
				for line in label.splitlines():
					width = self.GetTextExtent(line)[0]
					if width > max_width:
						max_width = width
				self.Size = max_width, -1
				self.MaxSize = self.Size[0], -1

		def Wrap(self, width):
			wx._StaticText.Wrap(self, width)
			self.SetLabel(self.Label)

		Label = property(lambda self: self.GetLabel(), SetLabel)

	wx.StaticText = StaticText


def Property(func):
	return property(**func())


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
		if self._bitmaplabel.IsOk():
			self.SetBitmapLabel(self._bitmaplabel)
	else:
		if self._bitmapdisabled.IsOk():
			self.SetBitmapLabel(self._bitmapdisabled)

def BitmapButtonDisable(self):
	"""
	Replacement for BitmapButton.Disable which circumvents repainting issues
	
	(bitmap does not change on button state change)
	
	"""
	self.Enable(False)

if not u"phoenix" in wx.PlatformInfo:
	wx.BitmapButton.Enable = BitmapButtonEnable
	wx.BitmapButton.Disable = BitmapButtonDisable


def FindMenuItem(self, label):
	""" Replacement for wx.Menu.FindItem """
	label = GTKMenuItemGetFixedLabel(label)
	for menuitem in self.GetMenuItems():
		if GTKMenuItemGetFixedLabel(menuitem.Label) == label:
			return menuitem.GetId()

wx.Menu.FindItem = FindMenuItem


def GTKMenuItemGetFixedLabel(label):
	if sys.platform not in ("darwin", "win32"):
		# The underscore is a special character under GTK, like the 
		# ampersand on Mac OS X and Windows
		# Recent wxPython versions already do the right thing, but we need
		# this workaround for older releases
		if "__" in label:
			label = label.replace("__", "_")
		while label and label[0] == "_":
			label = label[1:]
	return label


if not hasattr(wx.Sizer, "GetItemIndex"):
	def GetItemIndex(self, item):
		for i, child in enumerate(self.GetChildren()):
			if child.GetWindow() is item:
				return i
		return -1

	wx.Sizer.GetItemIndex = GetItemIndex


if sys.platform == "darwin":
	# wxMac seems to loose foreground color of StaticText
	# when enabled again

	@Property
	def StaticTextEnabled():
		def fget(self):
			return self.IsEnabled()

		def fset(self, enable=True):
			self.Enable(enable)

		return locals()

	wx.StaticText.Enabled = StaticTextEnabled


	def StaticTextDisable(self):
		self.Enable(False)

	wx.StaticText.Disable = StaticTextDisable


	def StaticTextEnable(self, enable=True):
		enable = bool(enable)
		if self.Enabled is enable:
			return
		self._enabled = enable
		if not hasattr(self, "_fgcolor"):
			self._fgcolor = self.ForegroundColour
		color = self._fgcolor
		if not enable:
			bgcolor = self.Parent.BackgroundColour
			bgblend = .5
			blend = .5
			color = wx.Colour(int(round(bgblend * bgcolor.Red() +
										blend * color.Red())),
							  int(round(bgblend * bgcolor.Green() +
										blend * color.Green())),
							  int(round(bgblend * bgcolor.Blue() +
										blend * color.Blue())))
		self.ForegroundColour = color

	wx.StaticText.Enable = StaticTextEnable


	def StaticTextIsEnabled(self):
		return getattr(self, "_enabled", True)

	wx.StaticText.IsEnabled = StaticTextIsEnabled


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
		for i in xrange(numcols):
			sel.append((row, i))
	# cols
	cols = self.GetSelectedCols()
	for col in cols:
		for i in xrange(numrows):
			sel.append((i, col))
	# block
	tl = self.GetSelectionBlockTopLeft()
	br = self.GetSelectionBlockBottomRight()
	if tl and br:
		for n in xrange(min(len(tl), len(br))):
			for i in xrange(tl[n][0], br[n][0] + 1): # rows
				for j in xrange(tl[n][1], br[n][1] + 1): # cols
					sel.append((i, j))
	# single selected cells
	sel.extend(self.GetSelectedCells())
	sel = list(set(sel))
	sel.sort()
	return sel

wx.grid.Grid.GetSelection = GridGetSelection


def adjust_font_size_for_gcdc(font):
	font.SetPointSize(get_gcdc_font_size(font.PointSize))
	return font


def get_dc_font_size(size, dc):
	""" Get correct font size for DC """
	pointsize = (1.0, 1.0)
	if isinstance(dc, wx.GCDC):
		pointsize = tuple(1.0 / scale for scale in dc.GetLogicalScale())
	if (sys.platform in ("darwin", "win32") or not isinstance(dc, wx.GCDC) or
		wx.VERSION >= (2, 9)):
		return size * (sum(pointsize) / 2.0)
	else:
		# On Linux, we need to correct the font size by a certain factor if
		# wx.GCDC is used, to make text the same size as if wx.GCDC weren't used
		screenppi = map(float, wx.ScreenDC().GetPPI())
		ppi = dc.GetPPI()
		return size * ((screenppi[0] / ppi[0] * pointsize[0] + screenppi[1] / ppi[1] * pointsize[1]) / 2.0)


def get_gcdc_font_size(size):
	dc = wx.MemoryDC(wx.EmptyBitmap(1, 1))
	try:
		dc = wx.GCDC(dc)
	except:
		pass
	return get_dc_font_size(size, dc)


def set_bitmap_labels(btn, disabled=True, focus=True, pressed=True):
	bitmap = btn.BitmapLabel
	if not bitmap.IsOk():
		size = btn.MinSize
		if -1 in size:
			size = (16, 16)
		bitmap = wx.ArtProvider.GetBitmap(wx.ART_MISSING_IMAGE,
										  size=size)

	# Disabled
	if disabled:
		# Use Rec. 709 luma coefficients to convert to grayscale
		image = bitmap.ConvertToImage().ConvertToGreyscale(.2126, .7152, .0722)
		if image.HasMask() and not image.HasAlpha():
			image.InitAlpha()
		if image.HasAlpha():
			alphabuffer = image.GetAlphaBuffer()
			for i, byte in enumerate(alphabuffer):
				if byte > "\0":
					alphabuffer[i] = chr(int(round(ord(byte) * .3)))
		btn.SetBitmapDisabled(image.ConvertToBitmap())

	# Focus/Hover
	if sys.platform != "darwin" and focus:
		# wxMac applies hover state also to disabled buttons...
		image = bitmap.ConvertToImage()
		if image.HasMask() and not image.HasAlpha():
			image.InitAlpha()
		databuffer = image.GetDataBuffer()
		for i, byte in enumerate(databuffer):
			if byte > "\0":
				databuffer[i] = chr(int(round(min(ord(byte) * 1.15, 255))))
		bmp = image.ConvertToBitmap()
		btn.SetBitmapFocus(bmp)
		if hasattr(btn, "SetBitmapCurrent"):
			# Phoenix
			btn.SetBitmapCurrent(bmp)
		else:
			# Classic
			btn.SetBitmapHover(bmp)

	# Selected
	if pressed:
		image = bitmap.ConvertToImage()
		if image.HasMask() and not image.HasAlpha():
			image.InitAlpha()
		databuffer = image.GetDataBuffer()
		for i, byte in enumerate(databuffer):
			if byte > "\0":
				databuffer[i] = chr(int(round(ord(byte) * .6)))
		bmp = image.ConvertToBitmap()
		if hasattr(btn, "SetBitmapPressed"):
			# Phoenix
			btn.SetBitmapPressed(bmp)
		else:
			# Classic
			btn.SetBitmapSelected(bmp)


# wx.DirDialog and wx.FileDialog are normally not returned by
# wx.GetTopLevelWindows, do some trickery to work around

_DirDialog = wx.DirDialog
_FileDialog = wx.FileDialog

class PathDialogBase(wx.Dialog):

	def __init__(self, name):
		wx.Dialog.__init__(self, None, -1, name=name)
		self._ismodal = False
		self._isshown = False
		self.Bind(wx.EVT_WINDOW_DESTROY, self.OnDestroy)

	def __getattr__(self, name):
		return getattr(self.filedialog, name)

	def IsModal(self):
		return self._ismodal

	def IsShown(self):
		return self._isshown

	def OnDestroy(self, event):
		self.filedialog.Destroy()
		event.Skip()

	def Show(self, show=True):
		self._isshown = show
		self.filedialog.Show(show)

	def ShowModal(self):
		self._isshown = True
		self._ismodal = True
		returncode = self.filedialog.ShowModal()
		self._ismodal = False
		self._isshown = False
		return returncode

class DirDialog(PathDialogBase):

	def __init__(self, *args, **kwargs):
		PathDialogBase.__init__(self, name="dirdialog")
		self.filedialog = _DirDialog(*args, **kwargs)

class FileDialog(PathDialogBase):

	def __init__(self, *args, **kwargs):
		PathDialogBase.__init__(self, name="filedialog")
		self.filedialog = _FileDialog(*args, **kwargs)

wx.DirDialog = DirDialog
wx.FileDialog = FileDialog


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


class GenButton(object):

	"""
	A generic button, based on wx.lib.buttons.GenButton.
	
	Fixes wx.lib.buttons.ThemedGenButton not taking into account backgroun
	color when pressed.
	
	"""

	def __init__(self):
		self.bezelWidth = 2
		self.hasFocus = False
		self.up = True
		self.useFocusInd = True

	def OnPaint(self, event):
		(width, height) = self.ClientSize
		x1 = y1 = 0
		x2 = width
		y2 = height

		dc = wx.PaintDC(self)
		brush = self.GetBackgroundBrush(dc)
		if brush is not None:
			brush.SetColour(self.Parent.BackgroundColour)
			dc.SetBackground(brush)
			dc.Clear()

		self.DrawBezel(dc, x1, y1, x2, y2)
		self.DrawLabel(dc, width, height)
		if self.hasFocus and self.useFocusInd:
			self.DrawFocusIndicator(dc, width, height)


if not "gtk3" in wx.PlatformInfo:
	# GTK3 doesn't respect NO_BORDER in hovered state when using wx.BitmapButton
	_GenBitmapButton = wx.BitmapButton

class GenBitmapButton(GenButton, _GenBitmapButton):

	def __init__(self, *args, **kwargs):
		GenButton.__init__(self)
		_GenBitmapButton.__init__(self, *args, **kwargs)
		self.hover = False
		set_bitmap_labels(self)
		if _GenBitmapButton is not wx.BitmapButton:
			self.Bind(wx.EVT_ENTER_WINDOW, self.OnMouseEnter)
			self.Bind(wx.EVT_LEAVE_WINDOW, self.OnMouseLeave)

	@Property
	def BitmapFocus():
		def fget(self):
			return self.GetBitmapFocus()

		def fset(self, bitmap):
			self.SetBitmapFocus(self, bitmap)

		return locals()

	@Property
	def BitmapDisabled():
		def fget(self):
			return self.GetBitmapDisabled()

		def fset(self, bitmap):
			self.SetBitmapDisabled(self, bitmap)

		return locals()

	@Property
	def BitmapHover():
		def fget(self):
			return self.GetBitmapHover()

		def fset(self, bitmap):
			self.SetBitmapHover(self, bitmap)

		return locals()

	@Property
	def BitmapSelected():
		def fget(self):
			return self.GetBitmapSelected()

		def fset(self, bitmap):
			self.SetBitmapSelected(self, bitmap)

		return locals()

	@Property
	def BitmapLabel():
		def fget(self):
			return self.GetBitmapLabel()

		def fset(self, bitmap):
			self.SetBitmapLabel(self, bitmap)

		return locals()

	def DrawLabel(self, dc, width, height, dx=0, dy=0):
		bmp = self.BitmapLabel
		if self.BitmapDisabled and not self.IsEnabled():
			bmp = self.BitmapDisabled
		elif self.BitmapSelected and not self.up:
			bmp = self.BitmapSelected
		elif self.BitmapHover and self.hover:
			bmp = self.BitmapHover
		elif self.BitmapFocus and self.hasFocus:
			bmp = self.BitmapFocus
		bw, bh = bmp.GetWidth(), bmp.GetHeight()
		hasMask = bmp.GetMask() != None
		dc.DrawBitmap(bmp, (width-bw)/2+dx, (height-bh)/2+dy, hasMask)

	def GetBitmapHover(self):
		return self.bmpHover

	def OnMouseEnter(self, event):
		if not self.IsEnabled():
			return
		if not self.hover:
			self.hover = True
			self.Refresh()
		event.Skip()

	def OnMouseLeave(self, event):
		if not self.IsEnabled():
			return
		if self.hover:
			self.hover = False
			self.Refresh()
		event.Skip()

	def SetBitmapHover(self, bitmap):
		self.bmpHover = bitmap


class ThemedGenButton(GenButton, _ThemedGenButton):

	"""
	A themed generic button, based on wx.lib.buttons.ThemedGenButton.

	Fixes wx.lib.buttons.ThemedGenButton sometimes not reflecting enabled
	state correctly as well as not taking into account background color when
	pressed, and mimics a default button under Windows more closely by
	not drawing a focus outline and not shifting the label when pressed.
	
	Also implements state for SetDefault.

	"""

	_reallyenabled = True
	labelDelta = 1

	def __init__(self, *args, **kwargs):
		GenButton.__init__(self)
		_ThemedGenButton.__init__(self, *args, **kwargs)
		self._default = False

	def Disable(self):
		self.Enable(False)

	def DoGetBestSize(self):
		"""
		Overridden base class virtual.  Determines the best size of the
		button based on the label and bezel size.
		"""
		w, h, useMin = self._GetLabelSize()
		if self.style & wx.BU_EXACTFIT:
			width = w + 2 + 2 * self.bezelWidth + 4 * int(self.useFocusInd)
			height = h + 2 + 2 * self.bezelWidth + 4 * int(self.useFocusInd)
		else:
			defSize = wx.Button.GetDefaultSize()
			width = 12 + w
			if useMin and width < defSize.width:
				width = defSize.width
			height = 11 + h
			if useMin and height < defSize.height:
				height = defSize.height
			width = width + self.bezelWidth - 2
			height = height + self.bezelWidth - 2
		return (width, height)

	def DrawBezel(self, dc, x1, y1, x2, y2):
		rect = wx.Rect(x1, y1, x2, y2)
		if self.up:
			state = 0
		else:
			state = wx.CONTROL_PRESSED | wx.CONTROL_SELECTED
		if not self.IsEnabled():
			state = wx.CONTROL_DISABLED
		elif self._default:
			state |= wx.CONTROL_ISDEFAULT
		pt = self.ScreenToClient(wx.GetMousePosition())
		if self.GetClientRect().Contains(pt):
			state |= wx.CONTROL_CURRENT
		wx.RendererNative.Get().DrawPushButton(self, dc, rect, state)

	def DrawLabel(self, dc, width, height, dx=0, dy=0):
		dc.SetFont(self.GetFont())
		if self.Enabled:
			dc.SetTextForeground(self.ForegroundColour)
		else:
			dc.SetTextForeground(wx.SystemSettings.GetColour(wx.SYS_COLOUR_GRAYTEXT))
		label = self.Label
		tw, th = dc.GetTextExtent(label)
		if sys.platform != "win32" and not self.up:
			dx = dy = self.labelDelta
		dc.DrawText(label, (width-tw)/2+dx, (height-th)/2+dy)

	def Enable(self, enable=True):
		if enable != self.Enabled:
			self.Enabled = enable
			wx.PyControl.Enable(self, enable)
			self.Refresh()

	@Property
	def Enabled():
		def fget(self):
			return self._reallyenabled
		
		def fset(self, enabled):
			self._reallyenabled = enabled
		
		return locals()

	def IsEnabled(self):
		return self.Enabled

	def OnLeftDown(self, event):
		if not self.Enabled:
			return
		self.up = False
		self.CaptureMouse()
		self.SetFocus()
		self.useFocusInd = False
		self.Refresh()
		event.Skip()

	def OnGainFocus(self, event):
		self.hasFocus = True
		self.useFocusInd = bool(self.bezelWidth)
		self.Refresh()
		self.Update()

	def SetDefault(self):
		self._default = True
		_ThemedGenButton.SetDefault(self)



class PlateButton(platebtn.PlateButton):

	"""
	Fixes wx.lib.platebtn.PlateButton sometimes not reflecting enabled state
	correctly aswelll as other quirks
	
	"""

	_reallyenabled = True

	def __init__(self, *args, **kwargs):
		platebtn.PlateButton.__init__(self, *args, **kwargs)
		self.Unbind(wx.EVT_LEAVE_WINDOW)
		self.Bind(wx.EVT_LEAVE_WINDOW,
				  lambda evt: wx.CallLater(80, self.__LeaveWindow))

	def DoGetBestSize(self):
		"""Calculate the best size of the button
		
		:return: :class:`Size`

		"""
		# A liitle more padding left + right
		width = 24
		height = 6
		if self.Label:
			# NOTE: Should measure with a GraphicsContext to get right
			#       size, but due to random segfaults on linux special
			#       handling is done in the drawing instead...
			lsize = self.GetFullTextExtent(self.Label)
			width += lsize[0]
			height += lsize[1]
			
		if self._bmp['enable'] is not None:
			bsize = self._bmp['enable'].Size
			width += (bsize[0] + 10)
			if height <= bsize[1]:
				height = bsize[1] + 6
			else:
				height += 3
		else:
			width += 10

		if self._menu is not None or self._style & platebtn.PB_STYLE_DROPARROW:
			width += 12

		best = wx.Size(width, height)
		self.CacheBestSize(best)
		return best

	def GetBitmapLabel(self):
		"""Get the label bitmap
		
		:return: :class:`Bitmap` or None

		"""
		return self._bmp["enable"]

	def __DrawBitmap(self, gc):
		"""Draw the bitmap if one has been set

		:param GCDC `gc`: :class:`GCDC` to draw with
		:return: x cordinate to draw text at

		"""
		if self.IsEnabled():
			bmp = self._bmp['enable']
		else:
			bmp = self._bmp['disable']

		xpos = 16
		if bmp is not None and bmp.IsOk():
			bw, bh = bmp.GetSize()
			ypos = (self.GetSize()[1] - bh) // 2
			gc.DrawBitmap(bmp, xpos, ypos, bmp.GetMask() != None)
			return bw + xpos
		else:
			return xpos

	def __DrawButton(self):
		"""Draw the button"""
		# TODO using a buffered paintdc on windows with the nobg style
		#      causes lots of weird drawing. So currently the use of a
		#      buffered dc is dissabled for this style.
		if platebtn.PB_STYLE_NOBG & self._style:
			dc = wx.PaintDC(self)
		else:
			dc = wx.AutoBufferedPaintDCFactory(self)
			dc.SetBackground(wx.Brush(self.Parent.BackgroundColour))
			dc.Clear()

		gc = wx.GCDC(dc)

		# Setup
		gc.SetFont(adjust_font_size_for_gcdc(self.GetFont()))
		gc.SetBackgroundMode(wx.TRANSPARENT)

		# Calc Object Positions
		width, height = self.GetSize()
		tw, th = gc.GetTextExtent(self.Label)
		txt_y = max((height - th) // 2, 1)

		# The background needs some help to look transparent on
		# on Gtk and Windows
		if wx.Platform in ['__WXGTK__', '__WXMSW__']:
			gc.SetBrush(self.GetBackgroundBrush(gc))
			gc.SetPen(wx.TRANSPARENT_PEN)
			gc.DrawRectangle(0, 0, width, height)

		gc.SetBrush(wx.TRANSPARENT_BRUSH)

		if self._state['cur'] == platebtn.PLATE_HIGHLIGHT and self.IsEnabled():
			gc.SetTextForeground(self._color['htxt'])
			gc.SetPen(wx.TRANSPARENT_PEN)
			self.__DrawHighlight(gc, width, height)

		elif self._state['cur'] == platebtn.PLATE_PRESSED and self.IsEnabled():
			gc.SetTextForeground(self._color['htxt'])
			pen = wx.Pen(platebtn.AdjustColour(self._color['press'], -80, 220), 1)
			gc.SetPen(pen)

			self.__DrawHighlight(gc, width, height)
			txt_x = self.__DrawBitmap(gc)
			t_x = max((width - tw - (txt_x + 2)) // 2, txt_x + 2)
			gc.DrawText(self.Label, t_x, txt_y)
			self.__DrawDropArrow(gc, width - 10, (height // 2) - 2)

		else:
			if self.IsEnabled():
				gc.SetTextForeground(self.GetForegroundColour())
			else:
				txt_c = wx.SystemSettings.GetColour(wx.SYS_COLOUR_GRAYTEXT)
				gc.SetTextForeground(txt_c)

		# Draw bitmap and text
		if self._state['cur'] != platebtn.PLATE_PRESSED or not self.IsEnabled():
			txt_x = self.__DrawBitmap(gc)
			t_x = max((width - tw - (txt_x + 2)) // 2, txt_x + 2)
			gc.DrawText(self.Label, t_x, txt_y)
			self.__DrawDropArrow(gc, width - 10, (height // 2) - 2)

	def __LeaveWindow(self):
		"""Handle updating the buttons state when the mouse cursor leaves"""
		if (self._style & platebtn.PB_STYLE_TOGGLE) and self._pressed:
			self._SetState(platebtn.PLATE_PRESSED) 
		else:
			self._SetState(platebtn.PLATE_NORMAL)
			self._pressed = False

	def __PostEvent(self):
		"""Post a button event to parent of this control"""
		if self._style & platebtn.PB_STYLE_TOGGLE:
			etype = wx.wxEVT_COMMAND_TOGGLEBUTTON_CLICKED
		else:
			etype = wx.wxEVT_COMMAND_BUTTON_CLICKED
		bevt = wx.CommandEvent(etype, self.GetId())
		bevt.SetEventObject(self)
		bevt.SetString(self.GetLabel())
		self.GetEventHandler().ProcessEvent(bevt)

	Disable = ThemedGenButton.__dict__["Disable"]
	Enable = ThemedGenButton.__dict__["Enable"]
	Enabled = ThemedGenButton.__dict__["Enabled"]
	IsEnabled = ThemedGenButton.__dict__["IsEnabled"]
	Label = property(lambda self: self.GetLabel(),
                     lambda self, label: self.SetLabel(label))

if not hasattr(PlateButton, "_SetState"):
	PlateButton._SetState = PlateButton.SetState


class ThemedGenBitmapTextButton(ThemedGenButton, _GenBitmapTextButton):
	"""A themed generic bitmapped button with text label"""
	def __init__(self, parent, id=-1, bitmap=wx.NullBitmap, label='',
				 pos=wx.DefaultPosition, size=wx.DefaultSize, style=0,
				 validator=wx.DefaultValidator, name="genbutton"):
		GenButton.__init__(self)
		_GenBitmapTextButton.__init__(self, parent, id, bitmap, label, pos, size, style, validator, name)
		self._default = False

	def DrawLabel(self, dc, width, height, dx=0, dy=0):
		bmp = self.bmpLabel
		if bmp is not None:     # if the bitmap is used
			if self.bmpDisabled and not self.IsEnabled():
				bmp = self.bmpDisabled
			if self.bmpFocus and self.hasFocus:
				bmp = self.bmpFocus
			if self.bmpSelected and not self.up:
				bmp = self.bmpSelected
			bw,bh = bmp.GetWidth(), bmp.GetHeight()
			if sys.platform != "win32" and not self.up:
				dx = dy = self.labelDelta
			hasMask = bmp.GetMask() is not None
		else:
			bw = bh = 0     # no bitmap -> size is zero

		dc.SetFont(self.GetFont())
		if self.IsEnabled():
			dc.SetTextForeground(self.GetForegroundColour())
		else:
			dc.SetTextForeground(wx.SystemSettings.GetColour(wx.SYS_COLOUR_GRAYTEXT))

		label = self.GetLabel()
		tw, th = dc.GetTextExtent(label)        # size of text
		sw, sh = dc.GetTextExtent(" ")   # extra spacing from bitmap
		if sys.platform != "win32" and not self.up:
			dx = dy = self.labelDelta

		pos_x = (width-bw-sw-tw)/2+dx      # adjust for bitmap and text to centre
		if bmp is not None:
			dc.DrawBitmap(bmp, pos_x, (height-bh)/2+dy, hasMask) # draw bitmap if available
			pos_x = pos_x + sw   # extra spacing from bitmap

		dc.DrawText(label, pos_x + dx+bw, (height-th)/2+dy)      # draw the text


class BitmapWithThemedButton(wx.BoxSizer):

	def __init__(self, parent, id=-1, bitmap=wx.NullBitmap, label="",
				 pos=wx.DefaultPosition, size=wx.DefaultSize, style=0,
				 validator=wx.DefaultValidator, name="button"):
		wx.BoxSizer.__init__(self, wx.HORIZONTAL)
		self._bmp = wx.StaticBitmap(parent, -1, bitmap)
		self.Add(self._bmp, flag=wx.ALIGN_CENTER_VERTICAL)
		if wx.Platform == "__WXMSW__":
			btncls = ThemedGenButton
		else:
			btncls = wx.Button
		self._btn = btncls(parent, id, label, pos, size, style, validator, name)
		self.Add(self._btn, flag=wx.ALIGN_CENTER_VERTICAL | wx.LEFT, border=8)

	def __getattr__(self, name):
		return getattr(self._btn, name)

	def Bind(self, event, handler):
		self._btn.Bind(event, handler)

	def SetBitmapLabel(self, bitmap):
		self._bmp.SetBitmap(bitmap)
		self.Layout()
