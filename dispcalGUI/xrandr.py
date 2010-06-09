#!/usr/bin/env python
# -*- coding: utf-8 -*-

from ctypes import POINTER, c_int, c_long, c_ubyte, c_ulong, cdll, pointer, util

try:
	libx11 = cdll.LoadLibrary(util.find_library("X11"))
except OSError:
	raise ImportError("Couldn't load X11")
try:
	libxrandr = cdll.LoadLibrary(util.find_library("Xrandr"))
except OSError:
	raise ImportError("Couldn't load Xrandr")

libxrandr.XRRGetOutputProperty.restype = c_int
libxrandr.XRRGetOutputProperty.argtypes = [c_ulong, c_ulong, c_ulong, c_long, 
										   c_long, c_int, c_int, c_ulong, 
										   POINTER(c_ulong), POINTER(c_int), 
										   POINTER(c_ulong), POINTER(c_ulong), 
										   POINTER(POINTER(c_ubyte))]

import os
import sys

import RealDisplaySizeMM as RDSMM
from options import debug

XA_CARDINAL = 6


def get_output_property(display_no=0, property_name=None, 
							   property_type=XA_CARDINAL):
	display = os.getenv("DISPLAY")
	x_display = libx11.XOpenDisplay(display)

	x_atom = libx11.XInternAtom(x_display, property_name, False)

	ret_type, ret_format, ret_len, ret_togo, atomv = (c_ulong(), 
													  c_int(), 
													  c_ulong(), 
													  c_ulong(), 
													  pointer(c_ubyte()))
	
	xrandr_output_xid = RDSMM.GetXRandROutputXID(display_no)
	if not xrandr_output_xid:
		raise ValueError("Invalid display_no specified or XrandR unsupported")

	if libxrandr.XRRGetOutputProperty(x_display, 
									  xrandr_output_xid, 
									  x_atom, 0, 0x7ffffff, False, False, 
									  property_type, ret_type, ret_format, 
									  ret_len, ret_togo, atomv) == 0 and \
	   ret_len.value > 0:
		if debug:
			print "ret_type:", ret_type.value
			print "ret_format:", ret_format.value
			print "ret_len:", ret_len.value
			print "ret_togo:", ret_togo.value
		return [atomv[i] for i in xrange(ret_len.value)]

	return None


if __name__ == "__main__":
	property = get_output_property(int(sys.argv[1]), sys.argv[2], 
								   int(sys.argv[3]))
	print "%s for display %s: %r" % (sys.argv[2], sys.argv[1], property)
