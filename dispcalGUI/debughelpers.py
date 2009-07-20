#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys

import config
from config import fs_enc
from log import logbuffer, safe_print
from meta import name as appname

wxEventTypes = {}

def getevtobjname(event, window = None):
	try:
		event_object = event.GetEventObject()
		if not event_object and window:
			event_object = window.FindWindowById(event.GetId())
		if event_object and hasattr(event_object, "GetName"):
			return event_object.GetName()
	except Exception, exception:
		pass

def getevttype(event):
	if not wxEventTypes:
		if not "wx" in globals():
			global wx
			import wx
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

def handle_error(errstr, parent = None, silent = False):
	if not isinstance(errstr, unicode):
		errstr = unicode(errstr, fs_enc, "replace")
	safe_print(errstr)
	if not silent:
		try:
			if not "wx" in globals():
				global wx
				import wx
			if wx.GetApp() is None and parent is None:
				app = wx.App(redirect = False)
			dlg = wx.MessageDialog(parent if parent not in (False, None) and 
				parent.IsShownOnScreen() else None, errstr, appname, wx.OK | 
				wx.ICON_ERROR)
			dlg.ShowModal()
			dlg.Destroy()
		except Exception, exception:
			safe_print("Warning: handle_error():", str(exception))
