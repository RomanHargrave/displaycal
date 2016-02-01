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
				if "clrt" in profile.tags:
					safe_print(f)
					safe_print(profile.connectionColorSpace)
					for name in profile.tags.clrt:
						safe_print(name, profile.tags.clrt[name])
					safe_print("")

