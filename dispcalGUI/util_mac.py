#!/usr/bin/env python
# -*- coding: utf-8 -*-

import subprocess as sp
from time import sleep

from log import safe_print
from meta import name as appname
from options import verbose


def get_osascript_args(applescript):
	""" Return arguments ready to use for osascript """
	if isinstance(applescript, basestring):
		applescript = applescript.splitlines()
	args = []
	for line in applescript:
		args += ['-e', line]
	return args


def get_osascript_args_or_run(applescript, run=True):
	""" Return arguments ready to use for osascript or run the AppleScript """
	if run:
		return osascript(applescript)
	else:
		return get_osascript_args(applescript)


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
	if delay:
		sleep(delay)
	return osascript(applescript)


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
	return get_osascript_args_or_run(applescript, script and do)


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
	return get_osascript_args_or_run(applescript, do)


def osascript(applescript):
	"""
	Run AppleScript with the 'osascript' command
	
	Return osascript's exit code.
	
	"""
	args = get_osascript_args(applescript)
	p = sp.Popen(['osascript'] + args, stdin=sp.PIPE, stdout=sp.PIPE, 
				 stderr=sp.PIPE)
	output, errors = p.communicate()
	retcode = p.wait()
	return retcode, output, errors
