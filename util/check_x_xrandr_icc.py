#!/usr/bin/env python2

from binascii import hexlify
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from DisplayCAL import ICCProfile as ICCP, xrandr
from DisplayCAL.safe_print import safe_print
from DisplayCAL.RealDisplaySizeMM import RealDisplaySizeMM as RDSMM

for i in xrange(5):
	# Show ICC info for first five screens / outputs
	try:
		x_icc_c = xrandr.get_atom("_ICC_PROFILE" if i < 1 else 
								  "_ICC_PROFILE_%i" % i)
	except ValueError:
		x_icc_c = None
	if x_icc_c:
		safe_print("Root window %s" % ("_ICC_PROFILE" if i < 1 else 
									   "_ICC_PROFILE_%i" % i))
		x_icc = ICCP.ICCProfile("".join(chr(n) for n in x_icc_c))
		safe_print("Description:", x_icc.getDescription())
		safe_print("Checksum ID:", hexlify(x_icc.calculateID()))
		safe_print("")
	try:
		xrr_icc_c = xrandr.get_output_property(i, "_ICC_PROFILE")
	except ValueError:
		xrr_icc_c = None
	if xrr_icc_c:
		safe_print("XRandR Output %i _ICC_PROFILE:" % i)
		xrr_icc = ICCP.ICCProfile("".join(chr(n) for n in xrr_icc_c))
		safe_print("Description:", xrr_icc.getDescription())
		safe_print("Checksum ID:", hexlify(xrr_icc.calculateID()))
		safe_print("")
