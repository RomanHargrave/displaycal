#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dispcalGUI import ICCProfile as iccp
from dispcalGUI.defaultpaths import iccprofiles, iccprofiles_home
from dispcalGUI.safe_print import safe_print

for p in set(iccprofiles_home + iccprofiles):
	if os.path.isdir(p):
		for f in os.listdir(p):
			try:
				profile = iccp.ICCProfile(os.path.join(p, f))
			except:
				pass
			else:
				if "chad" in profile.tags:
					safe_print(f)
					safe_print(profile.tags.chad)
					safe_print("")

