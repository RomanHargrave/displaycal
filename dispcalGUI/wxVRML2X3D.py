# -*- coding: utf-8 -*-

import os
import sys

from meta import name as appname
from safe_print import safe_print
from util_os import launch_file, waccess
from worker import Worker, show_result_dialog
from wxaddons import FileDrop, wx
import config
import localization as lang
import x3dom


def main(vrmlpath=None):
	if "--help" in sys.argv[1:]:
		safe_print("Usage: %s [--embed] [--no-gui] [--view] [FILE]" % sys.argv[0])
		safe_print("Convert VRML file to X3D embedded in HTML")
		safe_print("The output is written to FILENAME.x3d.html")
		safe_print("")
		safe_print("  --embed    Embed X3DOM runtime instead of referencing it")
		safe_print("  --no-gui   Don't show GUI (terminal mode)")
		safe_print("  --view     View the generated HTML file (if --no-gui)")
		safe_print("  FILE       Filename of VRML file to convert")
		return
	config.initcfg()
	lang.init()
	if "--no-gui" in sys.argv[1:]:
		vrmlfile2x3dhtmlfile(vrmlpath, embed="--embed" in sys.argv,
							 view="--view" in sys.argv)
	else:
		app = wx.App(0)
		frame = wx.Frame(None, wx.ID_ANY, lang.getstr("vrml_to_x3d_converter"),
						 style=wx.DEFAULT_FRAME_STYLE & ~(wx.MAXIMIZE_BOX |
														  wx.RESIZE_BORDER))
		frame.SetIcons(config.get_icon_bundle([256, 48, 32, 16],
											  appname +
											  "-VRML-to-X3D-converter"))
		worker = Worker(frame)
		sizer = wx.BoxSizer(wx.HORIZONTAL)
		frame.SetSizer(sizer)
		panel = wx.Panel(frame)
		sizer.Add(panel)
		panelsizer = wx.BoxSizer(wx.HORIZONTAL)
		panel.SetSizer(panelsizer)
		btn = wx.BitmapButton(panel, wx.ID_ANY,
							  config.geticon(256, "document-open"), 
							  style=wx.NO_BORDER)
		btn.SetToolTipString(lang.getstr("file.select"))
		btn.Bind(wx.EVT_BUTTON, lambda event:
								vrmlfile2x3dhtmlfile(None,
													 embed="--embed" in sys.argv,
													 view=True,
													 worker=worker))
		droptarget = FileDrop()
		vrml_drop_handler = lambda vrmlpath: vrmlfile2x3dhtmlfile(vrmlpath,
																  embed="--embed" in sys.argv,
																  view=True,
																  worker=worker)
		droptarget.drophandlers = {
			".vrml": vrml_drop_handler,
			".vrml.gz": vrml_drop_handler,
			".wrl": vrml_drop_handler,
			".wrl.gz": vrml_drop_handler,
			".wrz": vrml_drop_handler
		}
		droptarget.unsupported_handler = lambda: show_result_dialog(lang.getstr("error.file_type_unsupported") +
																	"\n\n" +
																	"\n".join(droptarget._filenames),
																	frame)
		btn.SetDropTarget(droptarget)
		panelsizer.Add(btn, flag=wx.ALL, border=12)
		frame.Fit()
		frame.SetMinSize(frame.GetSize())
		frame.SetMaxSize(frame.GetSize())
		frame.Show()
		if vrmlpath:
			wx.CallAfter(vrmlfile2x3dhtmlfile, vrmlpath,
						 embed="--embed" in sys.argv, view=True,
						 worker=worker)
		app.MainLoop()


def vrmlfile2x3dhtmlfile(vrmlpath=None, htmlpath=None, embed=False, view=False,
						 worker=None):
	""" Convert VRML to HTML. Output is written to <vrmlfilename>.x3d.html
	unless you set htmlpath to desired output path, or False to be prompted
	for an output path. """
	while not vrmlpath or not os.path.isfile(vrmlpath):
		if "--no-gui" in sys.argv[1:]:
			if not vrmlpath or vrmlpath.startswith("--"):
				safe_print("No filename given.")
			else:
				safe_print("%r is not a file." % vrmlpath)
			sys.exit(1)
		if not wx.GetApp():
			app = wx.App(0)
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
		config.writecfg()
	filename, ext = os.path.splitext(vrmlpath)
	if htmlpath is None:
		htmlpath = filename + ".x3d.html"
	if htmlpath:
		dirname = os.path.dirname(htmlpath)
	while not htmlpath or not waccess(dirname, os.W_OK):
		if "--no-gui" in sys.argv[1:]:
			if not htmlpath:
				safe_print("No HTML output filename given.")
			else:
				safe_print("%r is not writable." % dirname)
			sys.exit(1)
		if not wx.GetApp():
			app = wx.App(0)
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
	if worker:
		worker.clear_cmd_output()
		worker.start(lambda result:
					 show_result_dialog(result, wx.GetApp().GetTopWindow())
					 if isinstance(result, Exception)
					 else result and view and launch_file(htmlpath),
					 x3dom.vrmlfile2x3dhtmlfile,
					 wargs=(vrmlpath, htmlpath, embed, worker),
					 progress_title=lang.getstr("vrml_to_x3d_converter"),
					 resume=worker.progress_wnd and
							worker.progress_wnd.IsShownOnScreen())
	else:
		result = x3dom.vrmlfile2x3dhtmlfile(vrmlpath, htmlpath, embed)
		if not isinstance(result, Exception) and result and view:
			launch_file(htmlpath)
		else:
			sys.exit(1)


if __name__ == "__main__":
	main(*sys.argv[max(len(sys.argv) - 1, 1):])
