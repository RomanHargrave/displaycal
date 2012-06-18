# -*- coding: utf-8 -*-

import os

def get_display():
	""" 
	Parse $DISPLAY and return (hostname, display number, screen number)
	"""
	display = os.getenv("DISPLAY", ":0.0").split(":")
	hostname = display[0]
	if len(display) > 1:
		try:
			display_screen = tuple(int(n) for n in display[1].split("."))
		except ValueError:
			raise ValueError("The DISPLAY environment variable has an unknown "
							 "format: %r" % os.getenv("DISPLAY"))
		display = display_screen[0]
		if len(display_screen) > 1:
			screen = display_screen[1]
		else:
			screen = 0
	else:
		display, screen = 0, 0
	return hostname, display, screen
