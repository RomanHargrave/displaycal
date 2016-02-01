#!/usr/bin/env python2
# -*- coding: utf-8 -*-

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from DisplayCAL import ICCProfile as iccp
from DisplayCAL.defaultpaths import iccprofiles, iccprofiles_home
from DisplayCAL.safe_print import safe_print

for p in set(iccprofiles_home + iccprofiles):
	if os.path.isdir(p):
		for f in os.listdir(p):
			try:
				profile = iccp.ICCProfile(os.path.join(p, f))
			except:
				pass
			else:
				curve = None
				for key in ("r", "g", "b", "k"):
					curve = profile.tags.get(key + "TRC")
					if curve:
						break
				if curve and isinstance(curve, iccp.CurveType) and len(curve) == 1 and curve[0] < 1.8:
					safe_print(f)
					safe_print(curve)
					safe_print("")

