#!/usr/bin/env python2
# -*- coding: utf-8 -*-

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from DisplayCAL import ICCProfile as iccp
from DisplayCAL import util_str


def set_profile_desc_to_basename_sans_ext(profile):
	if isinstance(profile, basestring):
		profile = iccp.ICCProfile(profile)
	if isinstance(profile, iccp.ICCProfile):
		name = os.path.splitext(os.path.basename(profile.fileName))[0]
		if isinstance(profile.tags.desc, iccp.TextDescriptionType):
			profile.tags.desc.ASCII = name.encode('ASCII', 'asciize')
			profile.tags.desc.Unicode = name
			profile.tags.desc.Macintosh = name
		else:
			profile.tags.desc = iccp.MultiLocalizedUnicodeType()
			profile.tags.desc.add_localized_string('en', 'US', name)
		profile.write()
	else:
		for item in profile:
			set_profile_desc_to_basename_sans_ext(item)


if __name__ == '__main__':
	import sys
	set_profile_desc_to_basename_sans_ext(sys.argv[1:])
