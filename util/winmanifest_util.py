# -*- coding: utf-8 -*-

import os
import sys
import tempfile

sys.path.insert(1, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 
								"DisplayCAL"))

from meta import description, name, version_tuple
from winmanifest import ManifestFromXMLFile

def getmanifest(manifest_template_path):
	manifest = ManifestFromXMLFile(manifest_template_path)
	manifest.description = description
	manifest.name = name
	manifest.version = version_tuple
	return manifest

def getmanifestxml(manifest_template_path):
	manifest = getmanifest(manifest_template_path)
	return manifest.toprettyxml()

def mktempmanifest(manifest_template_path):
	tempdir = tempfile.mkdtemp()
	tempmanifest_path = os.path.join(tempdir, "manifest.xml")
	if not os.path.exists(tempdir):
		os.makedirs(tempdir)
	manifest = getmanifest(manifest_template_path)
	manifest.writeprettyxml(tempmanifest_path)
	return tempmanifest_path