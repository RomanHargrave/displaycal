#!/usr/bin/env python2
# -*- coding: utf-8 -*-

from copy import deepcopy
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from DisplayCAL import ICCProfile as ICCP
from DisplayCAL.colormath import get_rgb_space


def create_rendering_intent_test_profile(filename):
	srgb = get_rgb_space("sRGB")
	clutres = 9
	p = ICCP.create_synthetic_clut_profile(srgb,
										   "Rendering Intent Test Profile",
										   clutres=clutres)
	p.tags.B2A0.clut = []
	for tagname in ("A2B", "B2A"):
		tag0 = p.tags[tagname + "0"]
		for i in xrange(1, 3):
			tag = p.tags[tagname + "%i" % i] = ICCP.LUT16Type()
			for component_name in ("matrix", "input", "clut", "output"):
				component = getattr(tag0, component_name)
				if component_name == "clut":
					component = deepcopy(component)
				setattr(tag, component_name, component)
	for i in xrange(3):
		for tagname in ("A2B", "B2A"):
			tag = p.tags[tagname + "%i" % i]
			if i == 0:
				# Perceptual
				RGB = (2, 2, 0)
			elif i == 1:
				# Colorimetric
				RGB = (0, 2, 2)
			else:
				# Saturation
				RGB = (0, 2, 0)
			block = 0
			for R in xrange(clutres):
				for G in xrange(clutres):
					if tagname == "B2A":
						tag.clut.append([])
					for B in xrange(clutres):
						if tagname == "B2A":
							tag.clut[block].append([v / (clutres - 1.0) * 65535
													for v in (R, G, B)])
						if R == G == B:
							gray = (R, G, B)
						else:
							gray = None
						if (R, G, B) in ((2, 2, 0),
										 (0, 2, 2),
										 (0, 2, 0)):
							if (R, G, B) != RGB:
								triplet = [0, 0, 0]
							else:
								if tagname == "B2A":
									# White RGB
									triplet = [65535] * 3
								else:
									# White XYZ
									triplet = [31595, 32768, 27030]
						elif (R, G, B) in ((2, 0, 2),
										   (clutres - 1, 0, 0)):
							triplet = [0, 0, 0]
						else:
							triplet = None
						if triplet:
							tag.clut[block][B] = triplet
					block += 1
	# Add matrix tags
	srgb_icc = ICCP.ICCProfile.from_rgb_space(srgb, "sRGB")
	p.tags.rTRC = srgb_icc.tags.rTRC
	p.tags.gTRC = srgb_icc.tags.gTRC
	p.tags.bTRC = srgb_icc.tags.bTRC
	for i in xrange(1, len(p.tags.gTRC)):
		p.tags.rTRC[i] = i
		p.tags.gTRC[i] = i
		p.tags.bTRC[i] = 65535
	# Swap RGB -> GBR
	p.tags.rXYZ = ICCP.XYZType()
	p.tags.gXYZ = ICCP.XYZType()
	p.tags.bXYZ = srgb_icc.tags.wtpt.pcs
	p.calculateID()
	p.write(filename)


if __name__ == "__main__":
	create_rendering_intent_test_profile(sys.argv[1])
