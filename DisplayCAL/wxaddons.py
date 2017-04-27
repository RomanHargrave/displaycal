# -*- coding: utf-8 -*-

from time import sleep
import os
import sys
import threading
import types

from wxfixes import wx


def AdjustMinMax(self, minvalue=0.0, maxvalue=1.0):
	""" Adjust min/max """
	buffer = self.GetDataBuffer()
	for i, byte in enumerate(buffer):
		buffer[i] = chr(min(int(round(minvalue * 255 + ord(byte) * (maxvalue - minvalue))), 255))

wx.Image.AdjustMinMax = AdjustMinMax


def Blend(self, bitmap, x, y):
	""" Blend the given bitmap over the specified position in this bitmap. """
	dc = wx.MemoryDC(self)
	dc.DrawBitmap(bitmap, x, y)

wx.Bitmap.Blend = Blend


def GetRealClientArea(self):
	""" Return the real (non-overlapping) client area of a display """
	# need to fix overlapping ClientArea on some Linux multi-display setups
	# the client area must be always smaller than the geometry
	clientarea = list(self.ClientArea)
	if self.Geometry[0] > clientarea[0]:
		clientarea[0] = self.Geometry[0]
	if self.Geometry[1] > clientarea[1]:
		clientarea[1] = self.Geometry[1]
	if self.Geometry[2] < clientarea[2]:
		clientarea[2] = self.Geometry[2]
	if self.Geometry[3] < clientarea[3]:
		clientarea[3] = self.Geometry[3]
	return wx.Rect(*clientarea)

wx.Display.GetRealClientArea = GetRealClientArea


def GetAllChildren(self, skip=None):
	""" Get children of window and its subwindows """
	if not isinstance(skip, (list, tuple)):
		skip = [skip]
	children = filter(lambda child: child not in skip, self.GetChildren())
	allchildren = []
	for child in children:
		allchildren.append(child)
		if hasattr(child, "GetAllChildren") and hasattr(child.GetAllChildren,
														"__call__"):
			allchildren += child.GetAllChildren(skip)
	return allchildren

wx.Window.GetAllChildren = GetAllChildren


def GetDisplay(self):
	""" Return the display the window is shown on """
	display_no = wx.Display.GetFromWindow(self)
	if display_no < 0: # window outside visible area
		display_no = 0
	return wx.Display(display_no)

wx.Window.GetDisplay = GetDisplay


def SetMaxFontSize(self, pointsize=11):
	font = self.GetFont()
	if font.GetPointSize() > pointsize:
		font.SetPointSize(pointsize)
		self.SetFont(font)

wx.Window.SetMaxFontSize = SetMaxFontSize


def RealCenterOnScreen(self, dir=wx.BOTH):
	"""
	Center the window on the screen it is on, unlike CenterOnScreen which
	always centers on 1st screen.
	
	"""
	x, y = self.Position
	left, top, w, h = self.GetDisplay().ClientArea
	if dir & wx.HORIZONTAL:
		x = left + w / 2 - self.Size[0] / 2
	if dir & wx.VERTICAL:
		y = top + h / 2 - self.Size[1] / 2
	self.Position = x, y


wx.TopLevelWindow.RealCenterOnScreen = RealCenterOnScreen


def SetSaneGeometry(self, x=None, y=None, w=None, h=None):
	"""
	Set a 'sane' window position and/or size (within visible screen area).
	"""
	if not None in (x, y):
		# First, move to coordinates given
		self.SetPosition((x, y))
	# Returns the first display's client area if the window 
	# is completely outside the client area of all displays
	display_client_rect = self.GetDisplay().ClientArea 
	if sys.platform not in ("darwin", "win32"): # Linux
		safety_margin = 40
	else:
		safety_margin = 20
	if not None in (w, h):
		# Set given size, but resize if needed to fit inside client area
		min_w, min_h = self.MinSize
		self.SetSize((max(min(display_client_rect[2], w), min_w), 
					  max(min(display_client_rect[3] - safety_margin, h),
						  min_h)))
	if not None in (x, y):
		if not display_client_rect.ContainsXY(x, y) or \
		   not display_client_rect.ContainsRect((x, y, 100, 100)):
			# If outside client area or near the borders,
			# move to leftmost / topmost coordinates of client area
			self.SetPosition(display_client_rect[0:2])

wx.Window.SetSaneGeometry = SetSaneGeometry


def GridGetSelectedRowsFromSelection(self):
	"""
	Return the number of fully selected rows.
	
	Unlike GetSelectedRows, include rows that have been selected
	by chosing individual cells.
	
	"""
	numcols = self.GetNumberCols()
	rows = []
	i = -1
	for cell in self.GetSelection():
		row, col = cell
		if row > i:
			i = row
			rownumcols = 0
		rownumcols += 1
		if rownumcols == numcols:
			rows.append(row)
	return rows

wx.grid.Grid.GetSelectedRowsFromSelection = GridGetSelectedRowsFromSelection


def GridGetSelectionRows(self):
	"""
	Return the selected rows, even if not all cells in a row are selected.
	"""
	rows = []
	i = -1
	for row, col in self.GetSelection():
		if row > i:
			i = row
			rows.append(row)
	return rows

wx.grid.Grid.GetSelectionRows = GridGetSelectionRows


def IsSizer(self):
	""" Check if the window is a sizer """
	return isinstance(self, wx.Sizer)

wx.Window.IsSizer = IsSizer


def get_platform_window_decoration_size():
	if sys.platform in ("darwin", "win32"):
		# Size includes windows decoration
		if sys.platform == "win32":
			border = 8  # Windows 7
			titlebar = 30  # Windows 7
		else:
			border = 0  # Mac OS X 10.7 Lion
			titlebar = 22  # Mac OS X 10.7 Lion
	else:
		# Linux. Size does not include window decoration
		border = 0
		titlebar = 0
	return border, titlebar


def draw_granger_rainbow(dc, x=0, y=0, width=1920, height=1080):
	""" Draw a granger rainbow to a DC """
	if not isinstance(dc, wx.GCDC):
		raise NotImplementedError("%s lacks alpha transparency support" % dc.__class__)

	# Widths
	column_width = int(162.0 / 1920.0 * width)
	rainbow_width = width - column_width * 2
	strip_width = int(rainbow_width / 7.0)
	rainbow_width = strip_width * 7
	column_width = (width - rainbow_width) / 2

	# Gray columns left/right
	dc.GradientFillLinear(wx.Rect(x, y, width, height),
						  wx.Colour(0, 0, 0),
						  wx.Colour(255, 255, 255),
						  wx.UP)

	# Granger rainbow
	rainbow = [(255, 0, 255), (0, 0, 255), (0, 255, 255),
			   (0, 255, 0), (255, 255, 0), (255, 0, 0), (255, 0, 255)]
	start = rainbow[-2]
	for i, end in enumerate(rainbow):
		dc.GradientFillLinear(wx.Rect(x + column_width + strip_width * i, y,
									  strip_width, height),
							  wx.Colour(*start),
							  wx.Colour(*end),
							  wx.RIGHT)
		start = end

	# White-to-black gradient with transparency for shading
	# Top half - white to transparent
	dc.GradientFillLinear(wx.Rect(x + column_width, y,
								  rainbow_width, height / 2),
						  wx.Colour(0, 0, 0, 0),
						  wx.Colour(255, 255, 255, 255),
						  wx.UP)
	# Bottom half - transparent to black
	dc.GradientFillLinear(wx.Rect(x + column_width, y + height / 2,
								  rainbow_width, height / 2),
						  wx.Colour(0, 0, 0, 255),
						  wx.Colour(255, 255, 255, 0),
						  wx.UP)


def create_granger_rainbow_bitmap(width=1920, height=1080, filename=None):
	""" Create a granger rainbow bitmap """
	# Main bitmap
	bmp = wx.EmptyBitmap(width, height)
	mdc = wx.MemoryDC(bmp)
	dc = wx.GCDC(mdc)

	draw_granger_rainbow(dc, 0, 0, width, height)

	mdc.SelectObject(wx.NullBitmap)

	if filename:
		name, ext = os.path.splitext(filename)
		ext = ext.lower()
		bmp_type = {".bmp": wx.BITMAP_TYPE_BMP,
					".jpe": wx.BITMAP_TYPE_JPEG,
					".jpg": wx.BITMAP_TYPE_JPEG,
					".jpeg": wx.BITMAP_TYPE_JPEG,
					".jfif": wx.BITMAP_TYPE_JPEG,
					".pcx": wx.BITMAP_TYPE_PCX,
					".png": wx.BITMAP_TYPE_PNG,
					".tga": wx.BITMAP_TYPE_TGA,
					".tif": wx.BITMAP_TYPE_TIFF,
					".tiff": wx.BITMAP_TYPE_TIFF,
					".xpm": wx.BITMAP_TYPE_XPM}.get(ext, wx.BITMAP_TYPE_PNG)
		bmp.SaveFile(filename, bmp_type)
	else:
		return bmp


class CustomEvent(wx.PyEvent):

	def __init__(self, typeId, object, window=None):
		wx.PyEvent.__init__(self, object.GetId(), typeId)
		self.evtType = [typeId]
		self.typeId = typeId
		self.object = object
		self.window = window

	def GetEventObject(self):
		return self.object

	def GetEventType(self):
		return self.typeId

	def GetWindow(self):
		return self.window


_global_timer_lock = threading.Lock()


wxEVT_BETTERTIMER = wx.NewEventType()
EVT_BETTERTIMER = wx.PyEventBinder(wxEVT_BETTERTIMER, 1)


class BetterTimerEvent(wx.PyCommandEvent):

	def __init__(self, id=wx.ID_ANY, ms=0):
		wx.PyCommandEvent.__init__(self, wxEVT_BETTERTIMER, id)
		self._ms = ms

	def GetInterval(self):
		return self._ms

	Interval = property(GetInterval)


class BetterTimer(wx.Timer):

	"""
	A wx.Timer replacement.
	
	Doing GUI updates using regular timers can be incredibly segfaulty under
	wxPython Phoenix when several timers run concurrently.
	
	This approach uses a global lock to work around the issue.
	
	"""

	def __init__(self, owner=None, timerid=wx.ID_ANY):
		wx.Timer.__init__(self, None, timerid)
		self._owner = owner

	def Notify(self):
		if self._owner and _global_timer_lock.acquire(False):
			try:
				wx.PostEvent(self._owner, BetterTimerEvent(self.Id,
														   self.Interval))
			finally:
				_global_timer_lock.release()


class BetterCallLater(wx.CallLater):

	def __init__(self, millis, callableObj, *args, **kwargs):
		wx.CallLater.__init__(self, millis, callableObj, *args, **kwargs)

	def Notify(self):
		if _global_timer_lock.acquire(True):
			try:
				wx.CallLater.Notify(self)
			finally:
				_global_timer_lock.release()


class ThreadedTimer(object):

	""" A wx.Timer replacement that uses threads instead of actual timers
	which are a limited resource """

	def __init__(self, owner=None, timerid=wx.ID_ANY):
		self._owner = owner
		if timerid < 0:
			timerid = wx.NewId()
		self._id = timerid
		self._ms = 0
		self._oneshot = False
		self._keep_running = False
		self._thread = None

	def _notify(self):
		if _global_timer_lock.acquire(self._oneshot):
			try:
				self.Notify()
			finally:
				_global_timer_lock.release()

	def _timer(self):
		self._keep_running = True
		while self._keep_running:
			sleep(self._ms / 1000.0)
			if self._keep_running:
				wx.CallAfter(self._notify)
				if self._oneshot:
					self._keep_running = False

	def Destroy(self):
		pass

	def GetId(self):
		return self._id

	def GetInterval(self):
		return self._ms

	def GetOwner(self):
		return self._owner

	def SetOwner(self, owner):
		self._owner = owner

	Id = property(GetId)
	Interval = property(GetInterval)
	Owner = property(GetOwner, SetOwner)

	def IsOneShot(self):
		return self._oneshot

	def IsRunning(self):
		return self._keep_running

	def Notify(self):
		if self._owner:
			self._owner.ProcessEvent(BetterTimerEvent(self._id, self._ms))

	def Start(self, milliseconds=-1, oneShot=False):
		if self._thread and self._thread.isAlive():
			self._keep_running = False
			self._thread.join()
		if milliseconds > -1:
			self._ms = milliseconds
		self._oneshot = oneShot
		self._thread = threading.Thread(target=self._timer)
		self._thread.start()

	def Stop(self):
		self._keep_running = False


class ThreadedCallLater(ThreadedTimer):

	def __init__(self, millis, callableObj, *args, **kwargs):
		ThreadedTimer.__init__(self)
		self._oneshot = True
		self._callable = callableObj
		self._has_run = False
		self._result = None
		self.SetArgs(*args, **kwargs)
		self.Start(millis)

	def GetResult(self):
		return self._result

	Result = property(GetResult)

	def HasRun(self):
		return self._has_run

	def Notify(self):
		self._result = self._callable(*self._args, **self._kwargs)
		self._has_run = True

	def SetArgs(self, *args, **kwargs):
		self._args = args
		self._kwargs = kwargs

	def Start(self, millis=None, *args, **kwargs):
		if args:
			self._args = args
		if kwargs:
			self._kwargs = kwargs
		ThreadedTimer.Start(self, millis, True)

	Restart = Start


class BetterWindowDisabler(object):
	
	""" Also disables child windows instead of only top level windows. This is
	actually needed under Mac OS X where disabling a top level window will
	not prevent interaction with its children. """
	
	windows = set()

	def __init__(self, skip=None):
		self._windows = []
		self.skip = skip
		self.disable()

	def __del__(self):
		self.enable()
		
	def disable(self):
		self.enable(False)
	
	def enable(self, enable=True):
		if not enable:
			skip = self.skip or []
			if skip:
				if not isinstance(skip, (list, tuple)):
					skip = [skip]
			toplevel = list(wx.GetTopLevelWindows())
			for w in toplevel:
				if (w and w not in skip and "Inspection" not in "%s" % w and
					w not in BetterWindowDisabler.windows):
					self._windows.append(w)
					for child in w.GetAllChildren(skip + toplevel):
						if (child and not isinstance(child, (wx.Panel,
															 wx.PyPanel)) and
							child not in BetterWindowDisabler.windows):
							# Don't disable panels, this can have weird side
							# effects for contained controls
							self._windows.append(child)
			def Enable(w, enable=True):
				w._BetterWindowDisabler_enabled = enable
			def Disable(w):
				w._BetterWindowDisabler_enabled = False
			for w in reversed(self._windows):
				BetterWindowDisabler.windows.add(w)
				enabled = w.IsEnabled()
				w.Disable()
				w._BetterWindowDisabler_Disable = w.Disable
				w.Disable = types.MethodType(Disable, w, type(w))
				w._BetterWindowDisabler_Enable = w.Enable
				w.Enable = types.MethodType(Enable, w, type(w))
				w.Enable(enabled)
			return
		for w in self._windows:
			BetterWindowDisabler.windows.remove(w)
			if w:
				if hasattr(w, "_BetterWindowDisabler_Disable"):
					w.Disable = w._BetterWindowDisabler_Disable
				if hasattr(w, "_BetterWindowDisabler_Enable"):
					w.Enable = w._BetterWindowDisabler_Enable
				if hasattr(w, "_BetterWindowDisabler_enabled"):
					w.Enable(w._BetterWindowDisabler_enabled)


class CustomGridCellEvent(CustomEvent):
	def __init__(self, typeId, object, row=-1, col=-1, window=None):
		CustomEvent.__init__(self, typeId, object, window)
		self.row = row
		self.col = col

	@property
	def Col(self):
		return self.col

	def GetRow(self):
		return self.row

	def GetCol(self):
		return self.col

	@property
	def Row(self):
		return self.row


class FileDrop(wx.FileDropTarget):

	def __init__(self, drophandlers=None):
		wx.FileDropTarget.__init__(self)
		if drophandlers is None:
			drophandlers = {}
		self.drophandlers = drophandlers
		self.unsupported_handler = None

	def OnDropFiles(self, x, y, filenames):
		self._files = []
		self._filenames = filenames

		for filename in filenames:
			name, ext = os.path.splitext(filename)
			if ext.lower() in self.drophandlers:
				self._files.append((ext.lower(), filename))

		if self._files:
			self._files.reverse()
			wx.CallLater(1, wx.CallAfter, self.process)
		elif self.unsupported_handler:
			wx.CallLater(1, wx.CallAfter, self.unsupported_handler)
		return False

	def process(self):
		ms = 1.0 / 60
		while self._files:
			if hasattr(self, "parent") and hasattr(self.parent, "worker"):
				while self.parent.worker.is_working():
					wx.Yield()
					sleep(ms)
					if self.parent.worker.thread_abort:
						return
			ext, filename = self._files.pop()
			self.drophandlers[ext](filename)
