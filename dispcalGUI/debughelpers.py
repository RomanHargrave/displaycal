#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys

import config
from config import fs_enc
from log import logbuffer, safe_print
from meta import name as appname
from util_str import safe_unicode

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


def handle_error(error, parent=None, silent=False):
	""" Log an error string and show an error dialog. """
	error = safe_unicode(error)
	safe_print(error)
	if not silent:
		try:
			from wxaddons import wx
			if wx.GetApp() is None and parent is None:
				app = wx.App(redirect=False)
			if parent:
				try:
					parent.IsShownOnScreen()
				except:
					# If the parent is still being constructed, we can't use it
					parent = None
			dlg = wx.MessageDialog(parent if parent not in (False, None) and 
								   parent.IsShownOnScreen() else None, 
								   error, appname, wx.OK | wx.ICON_ERROR)
			dlg.ShowModal()
			dlg.Destroy()
		except Exception, exception:
			safe_print("Warning: handle_error():", safe_unicode(exception))
