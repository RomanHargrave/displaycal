#!/usr/bin/env python
# -*- coding: utf-8 -*-

import subprocess as sp
from time import sleep

try:
	import appscript
except ImportError: # we can fall back to osascript shell command
	appscript = None

from log import safe_print
from meta import name as appname
from options import verbose

def mac_app_activate(delay=0, mac_app_name="Finder"):
	"""
	Activate (show & bring to front) an application if it is running.
	"""
	applescript = [
		'on appIsRunning(appName)',
			'tell application "System Events" to (name of processes) contains '
			'appName',
		'end appIsRunning',
		'if appIsRunning("%s") then' % mac_app_name,
			'tell app "%s" to activate' % mac_app_name,
		'end if'
	]
	args = []
	for line in applescript:
		args += ['-e', line]
	try:
		if delay: sleep(delay)
		if appscript is None or mac_app_name == appname:
			# Do not use the appscript method to give focus back to 
			# dispcalGUI, it doesn't work reliably. The osascript method works.
			sp.call(['osascript'] + args)
		else:
			mac_app = appscript.app(mac_app_name)
			if mac_app.isrunning():
				# Only activate if already running
				appscript.app(mac_app_name).activate()
	except Exception, exception:
		if verbose >= 1:
			safe_print("Warning - mac_app_activate() failed:", exception)


def mac_terminal_do_script(script=None, do=True):
	"""
	Run a script in Terminal.
	"""
	applescript = [
		'on appIsRunning(appName)',
			'tell application "System Events" to (name of processes) contains '
			'appName',
		'end appIsRunning',
		'if appIsRunning("Terminal") then',
			'tell app "Terminal"',
				'activate',
				'do script ""',  # Terminal is already running, open a new 
								 # window to make sure it is not blocked by 
								 # another process
			'end tell',
		'else',
			'tell app "Terminal" to activate',  # Terminal is not yet running, 
											    # launch & use first window
		'end if'
	]
	if script:
		applescript += [
			'tell app "Terminal"',
				'do script "%s" in first window' % script.replace('"', '\\"'),
			'end tell'
		]
	args = []
	for line in applescript:
		args += ['-e', line]
	if script and do:
		retcode = -1
		try:
			if appscript is None:
				retcode = sp.call(['osascript'] + args)
			else:
				terminal = appscript.app("Terminal")
				if terminal.isrunning():
					# Terminal is already running, use a new window to make 
					# sure it is not blocked by another process
					terminal.activate()
					terminal.do_script(script)
				else:
					# Terminal is not yet running, launch & use first window
					terminal.do_script(script, in_=appscript.app.windows[1])
				retcode = 0
		except Exception, exception:
			if verbose >= 1:
				safe_print("Error - mac_terminal_do_script() failed:", 
						   exception)
		return retcode
	else:
		return args


def mac_terminal_set_colors(background="black", cursor="gray", text="gray", 
							text_bold="gray", do=True):
	"""
	Set Terminal colors.
	"""
	applescript = [
		'tell app "Terminal"',
		'set background color of first window to "%s"' % background,
		'set cursor color of first window to "%s"' % cursor,
		'set normal text color of first window to "%s"' % text,
		'set bold text color of first window to "%s"' % text_bold,
		'end tell'
	]
	args = []
	for line in applescript:
		args += ['-e', line]
	if do:
		retcode = -1
		try:
			if appscript is None:
				retcode = sp.call(['osascript'] + args)
			else:
				tw = appscript.app("Terminal").windows[1]
				tw.background_color.set(background)
				tw.cursor_color.set(cursor)
				tw.normal_text_color.set(text)
				tw.bold_text_color.set(text_bold)
				retcode = 0
		except Exception, exception:
			if verbose >= 1:
				safe_print("Info - mac_terminal_set_colors() failed:", 
						   exception)
		return retcode
	else:
		return args
