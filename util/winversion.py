# -*- coding: utf-8 -*-

import os
import sys
import tempfile

sys.path.insert(1, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 
								"DisplayCAL"))

from meta import author, description, domain, name, version, version_tuple

def mktempver(version_template_path, name=name, description=description,
			  encoding="UTF-8"):
	version_template = open(version_template_path, "rb")
	tempver_str = version_template.read().decode(encoding, "replace") % {
			"filevers": str(version_tuple),
			"prodvers": str(version_tuple),
			"CompanyName": domain,
			"FileDescription": description,
			"FileVersion": version,
			"InternalName": name,
			"LegalCopyright": u"© " + author,
			"OriginalFilename": name + ".exe",
			"ProductName": name,
			"ProductVersion": version
		}
	version_template.close()
	tempdir = tempfile.mkdtemp()
	tempver_path = os.path.join(tempdir, "winversion.txt")
	if not os.path.exists(tempdir):
		os.makedirs(tempdir)
	tempver = open(tempver_path, "wb")
	tempver.write(tempver_str.encode(encoding, "replace"))
	tempver.close()
	return tempver_path