#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os

def get_display():
	""" 
	Parse $DISPLAY and return (hostname, display number, screen number)
	"""
	display = os.getenv("DISPLAY", ":0.0").split(":")
	hostname = display[0]
	if len(display) > 1:
		display, screen = tuple(int(n) for n in display[1].split("."))
	else:
		display, screen = 0, 0
	return host, server, display
