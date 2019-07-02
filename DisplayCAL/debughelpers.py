# -*- coding: utf-8 -*-

import sys
import traceback

import config
from config import fs_enc
from log import logbuffer, safe_print
from meta import name as appname, wx_recversion
from options import debug
from util_str import box, safe_unicode

wxEventTypes = {}

def getevtobjname(event, window=None):
	""" Get and return the event object's name. """
	try:
		event_object = event.GetEventObject()
		if not event_object and window:
			event_object = window.FindWindowById(event.GetId())
		if event_object and hasattr(event_object, "GetName"):
			return event_object.GetName()
	except Exception, exception:
		pass


def getevttype(event):
	""" Get and return the event object's type. """
	if not wxEventTypes:
		from wxaddons import wx
		try:
			for name in dir(wx):
				if name.find("EVT_") == 0:
					attr = getattr(wx, name)
					if hasattr(attr, "evtType"):
						wxEventTypes[attr.evtType[0]] = name
		except Exception, exception:
			pass
	typeId = event.GetEventType()
	if typeId in wxEventTypes:
		return wxEventTypes[typeId]


def handle_error(error, parent=None, silent=False, tb=True):
	""" Log an error string and show an error dialog. """
	if isinstance(error, tuple):
		# We got a tuple. Assume (etype, value, tb)
		tbstr = "".join(traceback.format_exception(*error))
		error = error[1]
	else:
		tbstr = traceback.format_exc()
	if (tb and tbstr.strip() != "None" and isinstance(error, Exception) and
		(debug or not isinstance(error, EnvironmentError) or
		 not getattr(error, "filename", None))):
		# Print a traceback if in debug mode, for non environment errors, and
		# for environment errors not related to files
		errstr, tbstr = (safe_unicode(v) for v in (error, tbstr))
		msg = "\n\n".join((errstr, tbstr))
		if msg.startswith(errstr):
			safe_print(box(tbstr))
		else:
			safe_print(box(msg))
	else:
		msg = safe_unicode(error)
		safe_print(box(msg))
	if not silent:
		try:
			from wxaddons import wx
			if wx.VERSION < wx_recversion:
				msg += ("\n\nWARNING: Your version of wxPython (%s) is outdated "
						"and no longer supported. You should consider updating "
						"to wxPython %s or newer." %
						(wx.__version__, 
						 ".".join(str(n) for n in wx_recversion)))
			app = wx.GetApp()
			if app is None and parent is None:
				app = wx.App(redirect=False)
				# wxPython 3 bugfix: We also need a toplevel window
				frame = wx.Frame(None)
				parent = False
			else:
				frame = None
			if parent is None:
				parent = wx.GetActiveWindow()
			if parent:
				try:
					parent.IsShownOnScreen()
				except:
					# If the parent is still being constructed, we can't use it
					parent = None
			icon = wx.ICON_INFORMATION
			if not isinstance(error, Info):
				if isinstance(error, Warning):
					icon = wx.ICON_WARNING
				elif isinstance(error, Exception):
					icon = wx.ICON_ERROR
			dlg = wx.MessageDialog(parent if parent not in (False, None) and 
								   parent.IsShownOnScreen() else None, 
								   msg, app.AppName, wx.OK | icon)
			if frame:
				# wxPython 3 bugfix: We need to use CallLater and MainLoop
				wx.CallLater(1, dlg.ShowModal)
				wx.CallLater(1, frame.Close)
				app.MainLoop()
			else:
				dlg.ShowModal()
				dlg.Destroy()
		except Exception, exception:
			safe_print("Warning: handle_error():", safe_unicode(exception))


def print_callstack():
	""" Print call stack """
	import inspect
	stack = inspect.stack()
	indent = ""
	for frame, filename, linenum, funcname, line, exc in reversed(stack[1:]):
		safe_print(indent, funcname, filename, linenum,
				   repr("".join(line).strip()))
		indent += " "


class ResourceError(Exception):
	pass


class Error(Exception):
	pass


class Info(UserWarning):
	pass


class UnloggedError(Error):
	pass


class UnloggedInfo(Info):
	pass


class UnloggedWarning(UserWarning):
	pass


class DownloadError(Error):

	def __init__(self, *args):
		Error.__init__(self, *args[:-1])
		self.url = args[1]


class UntracedError(Error):
	pass


class Warn(UserWarning):
	pass
