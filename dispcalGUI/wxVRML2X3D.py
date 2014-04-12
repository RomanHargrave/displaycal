# -*- coding: utf-8 -*-

import os
import sys

from safe_print import safe_print
from util_os import launch_file, waccess
from wxaddons import wx
import config
import localization as lang
import x3dom


def main(vrmlpath=None):
	if "--help" in sys.argv[1:]:
		safe_print("Usage: %s [--embed] [--view] [FILE]" % sys.argv[0])
		safe_print("Convert VRML file to X3D embedded in HTML")
		safe_print("The output is written to FILENAME.x3d.html")
		safe_print("")
		safe_print("  --embed    Embed X3DOM runtime instead of referencing it")
		safe_print("  --view     View the HTML file after conversion")
		safe_print("  FILE       Filename of VRML file to convert")
		return
	app = wx.App(0)
	config.initcfg()
	lang.init()
	vrmlfile2x3dhtmlfile(vrmlpath, embed="--embed" in sys.argv,
						 view="--view" in sys.argv or not vrmlpath)


def vrmlfile2x3dhtmlfile(vrmlpath=None, htmlpath=None, embed=False, view=False):
	""" Convert VRML to HTML. Output is written to <vrmlfilename>.x3d.html
	unless you set htmlpath to desired output path, or False to be prompted
	for an output path. """
	while not vrmlpath or not os.path.isfile(vrmlpath):
		defaultDir, defaultFile = config.get_verified_path("last_vrml_path")
		dlg = wx.FileDialog(None, lang.getstr("file.select"),
							defaultDir=defaultDir, 
							defaultFile=defaultFile, 
							wildcard=lang.getstr("filetype.vrml") +
									 "|*.vrml;*.vrml.gz;*.wrl.gz;*.wrl;*.wrz", 
							style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST)
		dlg.Center(wx.BOTH)
		result = dlg.ShowModal()
		if result != wx.ID_OK:
			return
		vrmlpath = dlg.GetPath()
		dlg.Destroy()
		config.setcfg("last_vrml_path", vrmlpath)
	filename, ext = os.path.splitext(vrmlpath)
	if htmlpath is None:
		htmlpath = filename + ".x3d.html"
	if htmlpath:
		dirname = os.path.dirname(htmlpath)
	while not htmlpath or not waccess(dirname, os.W_OK):
		if htmlpath:
			defaultDir, defaultFile = os.path.split(htmlpath)
		else:
			defaultFile = os.path.basename(filename) + ".x3d.html"
		dlg = wx.FileDialog(None, lang.getstr("error.access_denied.write",
											  dirname),
							defaultDir=defaultDir, 
							defaultFile=defaultFile, 
							wildcard=lang.getstr("filetype.html") +
									 "|*.html", 
							style=wx.SAVE | wx.FD_OVERWRITE_PROMPT)
		dlg.Center(wx.BOTH)
		result = dlg.ShowModal()
		dlg.Destroy()
		if result != wx.ID_OK:
			return
		htmlpath = dlg.GetPath()
		dirname = os.path.dirname(htmlpath)
	x3dom.vrmlfile2x3dhtmlfile(vrmlpath, htmlpath, embed)
	if view:
		launch_file(htmlpath)
	return htmlpath


if __name__ == "__main__":
	main(*sys.argv[max(len(sys.argv) - 1, 1):])
