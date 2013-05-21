#!/usr/bin/env python2
# -*- coding: utf-8 -*-

from ctypes import POINTER, Structure, c_int, c_long, c_ubyte, c_ulong, cdll, pointer, util

libx11pth = util.find_library("X11")
if not libx11pth:
	raise ImportError("Couldn't find libX11")
try:
	libx11 = cdll.LoadLibrary(libx11pth)
except OSError:
	raise ImportError("Couldn't load libX11")
libxrandrpth = util.find_library("Xrandr")
if not libxrandrpth:
	raise ImportError("Couldn't find libXrandr")
try:
	libxrandr = cdll.LoadLibrary(libxrandrpth)
except OSError:
	raise ImportError("Couldn't load libXrandr")

import os
import sys

import RealDisplaySizeMM as RDSMM
from options import debug
from util_x import get_display

XA_CARDINAL = 6
XA_INTEGER = 19

Atom = c_ulong

class Display(Structure):
	__slots__ = []

Display._fields_ = [('_opaque_struct', c_int)]

try:
	libx11.XInternAtom.restype = Atom
	libx11.XOpenDisplay.restype = POINTER(Display)
	libx11.XRootWindow.restype = c_ulong
	libx11.XGetWindowProperty.restype = c_int
	libx11.XGetWindowProperty.argtypes = [POINTER(Display), c_ulong, Atom, c_long, 
										  c_long, c_int, c_ulong, 
										  POINTER(c_ulong), POINTER(c_int), 
										  POINTER(c_ulong), POINTER(c_ulong), 
										  POINTER(POINTER(c_ubyte))]
except AttributeError, exception:
	raise ImportError("libX11: %s" % exception)

try:
	libxrandr.XRRGetOutputProperty.restype = c_int
	libxrandr.XRRGetOutputProperty.argtypes = [POINTER(Display), c_ulong, Atom, c_long, 
											   c_long, c_int, c_int, c_ulong, 
											   POINTER(c_ulong), POINTER(c_int), 
											   POINTER(c_ulong), POINTER(c_ulong), 
											   POINTER(POINTER(c_ubyte))]
except AttributeError, exception:
	raise ImportError("libXrandr: %s" % exception)


def get_atom(atom_name=None, atom_type=XA_CARDINAL, x_hostname="", 
			 x_display_no=0, x_screen_no=0):
	display = get_display()
	if not x_hostname:
		x_hostname = display[0]
	if not x_display_no:
		x_display_no = display[1]
	if not x_screen_no:
		x_screen_no = display[2]
	display = "%s:%i.%i" % (x_hostname, x_display_no, x_screen_no)
	x_display = libx11.XOpenDisplay(display)
	if not x_display:
		libx11.XCloseDisplay(x_display)
		raise ValueError("Invalid X display %r" % display)
	
	x_window = libx11.XRootWindow(x_display, x_screen_no)
	if not x_window:
		libx11.XCloseDisplay(x_display)
		raise ValueError("Invalid X screen %r" % x_screen_no)
	
	x_atom = libx11.XInternAtom(x_display, atom_name, True)
	if not x_atom:
		libx11.XCloseDisplay(x_display)
		raise ValueError("Invalid atom name %r" % atom_name)

	ret_type, ret_format, ret_len, ret_togo, atomv = (c_ulong(), 
													  c_int(), 
													  c_ulong(), 
													  c_ulong(), 
													  pointer(c_ubyte()))
	
	property = None
	if libx11.XGetWindowProperty(x_display, x_window, 
								 x_atom, 0, 0x7ffffff, False, atom_type, 
								 ret_type, ret_format, ret_len, ret_togo,
								 atomv) == 0 and ret_len.value > 0:
		if debug:
			print "ret_type:", ret_type.value
			print "ret_format:", ret_format.value
			print "ret_len:", ret_len.value
			print "ret_togo:", ret_togo.value
		property = [atomv[i] for i in xrange(ret_len.value)]
	
	libx11.XCloseDisplay(x_display)
	
	return property


def get_output_property(display_no=0, property_name=None, 
						property_type=XA_CARDINAL, x_hostname="", 
						x_display_no=0, x_screen_no=0):
	xrandr_output_xid = RDSMM.GetXRandROutputXID(display_no)
	if not xrandr_output_xid:
		raise ValueError("Invalid display number %r specified or XrandR "
						 "unsupported" % display_no)
	
	display = get_display()
	if not x_hostname:
		x_hostname = display[0]
	if not x_display_no:
		x_display_no = display[1]
	if not x_screen_no:
		x_screen_no = display[2]
	display = "%s:%i.%i" % (x_hostname, x_display_no, x_screen_no)
	x_display = libx11.XOpenDisplay(display)
	if not x_display:
		libx11.XCloseDisplay(x_display)
		raise ValueError("Invalid X display %r" % display)

	x_atom = libx11.XInternAtom(x_display, property_name, False)
	if not x_atom:
		libx11.XCloseDisplay(x_display)
		raise ValueError("Invalid property name %r" % property_name)

	ret_type, ret_format, ret_len, ret_togo, atomv = (c_ulong(), 
													  c_int(), 
													  c_ulong(), 
													  c_ulong(), 
													  pointer(c_ubyte()))

	property = None
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
		property = [atomv[i] for i in xrange(ret_len.value)]
	
	libx11.XCloseDisplay(x_display)

	return property


if __name__ == "__main__":
	property = get_output_property(int(sys.argv[1]), sys.argv[2], 
								   int(sys.argv[3]))
	print "%s for display %s: %r" % (sys.argv[2], sys.argv[1], property)
