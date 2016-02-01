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
				if isinstance(profile.tags.desc, iccp.TextDescriptionType):
					if profile.tags.desc.get("Unicode") or profile.tags.desc.get("Macintosh"):
						safe_print(os.path.join(p, f))
					if profile.tags.desc.get("Unicode"):
						safe_print("Unicode Language Code:", 
								   profile.tags.desc.unicodeLanguageCode)
						safe_print("Unicode Description:", 
								   profile.tags.desc.Unicode)
					if profile.tags.desc.get("Macintosh"):
						safe_print("Macintosh Language Code:", 
								   profile.tags.desc.macScriptCode)
						safe_print("Macintosh Description:", 
								   profile.tags.desc.Macintosh)
					if profile.tags.desc.get("Unicode") or profile.tags.desc.get("Macintosh"):
						safe_print("")
				elif not isinstance(profile.tags.desc, iccp.MultiLocalizedUnicodeType):
					safe_print(os.path.join(p, f))
					safe_print("Warning: 'desc' is invalid type (%s)" %
							   type(profile.tags.desc))
					safe_print("")

