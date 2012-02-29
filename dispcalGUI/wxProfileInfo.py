#!/usr/bin/env python
# -*- coding: utf-8 -*-

import subprocess as sp
import math
import os
import sys
import tempfile

from config import fs_enc, get_bitmap_as_icon, get_data_path, getcfg, geticon, setcfg
from meta import name as appname
from ordereddict import OrderedDict
from util_str import universal_newlines
from worker import Error, Worker, get_argyll_util, show_result_dialog
from wxaddons import FileDrop, wx
from wxenhancedplot import _Numeric
from wxwindows import InfoDialog
import colormath
import config
import wxenhancedplot as plot
import localization as lang
import ICCProfile as ICCP

BGCOLOUR = "#333333"
FGCOLOUR = "#999999"
GRIDCOLOUR = "#444444"
HILITECOLOUR = "white"

class GamutCanvas(plot.PlotCanvas):

	def __init__(self, *args, **kwargs):
		plot.PlotCanvas.__init__(self, *args, **kwargs)
		self.canvas.Unbind(wx.EVT_LEAVE_WINDOW)
		self.SetBackgroundColour(BGCOLOUR)
		self.SetEnableAntiAliasing(True)
		self.SetEnableHiRes(True)
		self.SetEnableGrid(True)
		self.SetEnablePointLabel(False)
		self.SetFontSizeAxis(8)
		self.SetFontSizeLegend(8)
		self.SetFontSizeTitle(9)
		self.SetForegroundColour(FGCOLOUR)
		self.SetGridColour(GRIDCOLOUR)
		self.setLogScale((False,False))
		self.SetXSpec(3)
		self.SetYSpec(3)
		self.worker = Worker()

	def DrawCanvas(self, title=None, profiles=None, intent="a"):
		if not title:
			title = ""
		
		# Clear
		self.axis = -128, 128
		
		self.center_x = 0
		self.center_y = 0
		self.ratio = 1.0, 1.0
		self._DrawCanvas(plot.PlotGraphics([], title, "a", "b"))
		
		poly = plot.PolyLine
		poly._attributes["width"] = 3
		polys = []
		
		# Setup xicclu
		xicclu = get_argyll_util("xicclu").encode(fs_enc)
		if not xicclu:
			return
		cwd = self.worker.create_tempdir()
		if isinstance(cwd, Exception):
			raise cwd
		if sys.platform == "win32":
			startupinfo = sp.STARTUPINFO()
			startupinfo.dwFlags |= sp.STARTF_USESHOWWINDOW
			startupinfo.wShowWindow = sp.SW_HIDE
		else:
			startupinfo = None
	
		size = 40
		max_abs_x = 0
		max_abs_y = 0
		max_x = 0
		max_y = 0
		min_x = 9999
		min_y = 9999
		
		if not profiles:
			profiles = [ICCP.ICCProfile(get_data_path("ref/sRGB.icm")),
						ICCP.get_display_profile()]
		for i, profile in enumerate(profiles):
			if not profile:
				continue
			
			channels = len(profile.colorSpace)

			# Create input values
			in_triplets = []
			step = 1.0 / (size - 1)
			for j in xrange(3):
				for k in xrange(3):
					in_triplet = [0.0] * channels
					in_triplet[j] = 1.0
					if j != k:
						for l in xrange(size):
							in_triplet[k] = step * l
							in_triplets.append(list(in_triplet))
			# Add white
			if profile.colorSpace == "RGB":
				in_triplets.append([1.0] * channels)
			else:
				in_triplets.append([0.0] * channels)

			# Convert RGB triplets to list of strings
			for j, in_triplet in enumerate(in_triplets):
				in_triplets[j] = " ".join(str(n) for n in in_triplet)

			# Prepare profile
			profile.write(os.path.join(cwd, "profile.icc"))

			# Lookup RGB -> XYZ values through 'input' profile using xicclu
			stderr = tempfile.SpooledTemporaryFile()
			p = sp.Popen([xicclu, "-ff", "-i" + intent, "-pl", "profile.icc"], 
						 stdin=sp.PIPE, stdout=sp.PIPE, stderr=stderr, 
						 cwd=cwd.encode(fs_enc), startupinfo=startupinfo)
			self.worker.subprocess = p
			if p.poll() not in (0, None):
				stderr.seek(0)
				raise Error(stderr.read().strip())
			try:
				odata = p.communicate("\n".join(in_triplets))[0].splitlines()
			except IOError:
				stderr.seek(0)
				raise Error(stderr.read().strip())
			if p.wait() != 0:
				raise IOError(''.join(odata))
			stderr.close()

			# Convert xicclu output to Lab triplets
			Lab_triplets = []
			for line in odata:
				line = "".join(line.strip().split("->")).split()
				Lab_triplets.append([float(n) for n in line[channels + 2:channels + 5]])
			
			xy = []
			for L, a, b in Lab_triplets[:-1]:
				xy.append((a, b))
				#if a < -128 or a > 128 or b < -128 or b > 128:
				if abs(a) > max_abs_x:
					max_abs_x = abs(a)
				if abs(b) > max_abs_y:
					max_abs_y = abs(b)
				if a > max_x:
					max_x = a
				if b > max_y:
					max_y = b
				if a < min_x:
					min_x = a
				if b < min_y:
					min_y = b
				
			xy2 = []
			for j, (x, y) in enumerate(xy):
				xy2.append((x, y))
				if len(xy2) == size:
					xy3 = []
					for k, (x, y) in enumerate(xy2):
						xy3.append((x, y))
						if len(xy3) == 2:
							if i == 0:
								# Draw comparison profile with grey outline
								RGBA = 204, 204, 204, 51
								w = 2
							else:
								RGBA = colormath.Lab2RGB(*Lab_triplets[j - len(xy2) + k], scale=255)
								w = 3
							polys.append(poly(list(xy3), colour=wx.Colour(*RGBA),
											  width=w))
							if i == 0:
								xy3 = []
							else:
								xy3 = xy3[1:]
					xy2 = xy2[size:]
			
			# Add whitepoint
			if i == 0:
				# Draw comparison profile with grey outline
				RGBA = 204, 204, 204, 75
				markersize = 1.25
			else:
				RGBA = colormath.Lab2RGB(*Lab_triplets[-1], scale=255)
				markersize = 1
			polys.append(plot.PolyMarker([Lab_triplets[-1][1:]],
										 colour=wx.Colour(*RGBA),
										 size=markersize))
		
		# Remove temporary files
		self.worker.wrapup(False)
	
		self.axis = (min(min_x, min_y) - poly._attributes["width"] * 2,
					 max(max_x, max_y) + poly._attributes["width"] * 2)
		
		self.center_x = 0 + (min_x + max_x) / 2
		self.center_y = 0 + (min_y + max_y) / 2
		self.ratio = [max(max_abs_x, max_abs_y) /
					  max(max_abs_x + poly._attributes["width"],
					      max_abs_y + poly._attributes["width"])] * 2
		self._DrawCanvas(plot.PlotGraphics(polys, title, "a", "b"))
	
	def _DrawCanvas(self, graphics):
		""" Draw proportionally correct, center and zoom """
		self.Freeze()
		ratio = (float(self.GetSize()[0]) / float(self.GetSize()[1]),
				 float(self.GetSize()[1]) / float(self.GetSize()[0]))
		if ratio[0] > 1:
			ratio = ratio[0]
			self.SetXSpec(3 * ratio)
			axis_x=tuple([v * ratio for v in self.axis])
			axis_y=self.axis
		else:
			ratio = ratio[1]
			self.SetYSpec(3 * ratio)
			axis_x=self.axis
			axis_y=tuple([v * ratio for v in self.axis])
		self.Draw(graphics, axis_x, axis_y)
		self.Zoom((self.center_x, self.center_y), self.ratio)
		self.Thaw()


class ProfileInfoFrame(wx.Frame):

	def __init__(self, *args, **kwargs):
	
		if len(args) < 3 and not "title" in kwargs:
			kwargs["title"] = lang.getstr("profile.info")
		
		wx.Frame.__init__(self, *args, **kwargs)
		
		self.SetIcons(config.get_icon_bundle([256, 48, 32, 16], appname))
		
		self.CreateStatusBar(1)
		
		self.profile = None
		
		self.sizer = wx.BoxSizer(wx.VERTICAL)
		self.SetSizer(self.sizer)
		
		self.title_panel = wx.Panel(self)
		self.title_panel.SetBackgroundColour(BGCOLOUR)
		self.sizer.Add(self.title_panel, flag=wx.EXPAND)
		
		self.title_sizer = wx.FlexGridSizer(3, 1)
		self.title_sizer.AddGrowableCol(0)
		self.title_sizer.AddGrowableCol(2)
		self.title_panel.SetSizer(self.title_sizer)
		
		self.title_txt = wx.StaticText(self.title_panel, -1, "")
		self.title_txt.SetForegroundColour(FGCOLOUR)
		font = wx.Font(12, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, 
					   wx.FONTWEIGHT_NORMAL)
		self.title_txt.SetFont(font)
		self.title_sizer.Add((0, 0))
		self.title_sizer.Add(self.title_txt, 1, flag=wx.ALL | wx.ALIGN_CENTER, border=8)
		self.title_sizer.Add((0, 0))
		
		self.hsizer = wx.BoxSizer(wx.HORIZONTAL)
		self.sizer.Add(self.hsizer, 1, flag=wx.EXPAND)
		
		self.bottompanel = wx.Panel(self, -1, size=(-1, 12))
		self.bottompanel.SetBackgroundColour(BGCOLOUR)
		self.sizer.Add(self.bottompanel, flag=wx.EXPAND)
		
		self.canvas_sizer = wx.BoxSizer(wx.VERTICAL)
		self.hsizer.Add(self.canvas_sizer, 4, flag=wx.EXPAND)
		
		self.midpanel = wx.Panel(self, -1, size=(8, -1))
		self.midpanel.SetBackgroundColour(BGCOLOUR)
		self.hsizer.Add(self.midpanel, flag=wx.EXPAND)
		
		self.box_panel = wx.ScrolledWindow(self, -1, style=wx.VSCROLL)
		self.box_panel.SetBackgroundColour(BGCOLOUR)
		self.hsizer.Add(self.box_panel, 7, flag=wx.EXPAND)
		
		self.rightpanel = wx.Panel(self, -1, size=(12, -1))
		self.rightpanel.SetBackgroundColour(BGCOLOUR)
		self.hsizer.Add(self.rightpanel, flag=wx.EXPAND)
		
		self.box_sizer = wx.BoxSizer(wx.HORIZONTAL)
		self.box_panel.SetSizer(self.box_sizer)
		
		self.cbox_sizer = wx.BoxSizer(wx.HORIZONTAL)
		self.box_sizer.Add(self.cbox_sizer, 
						   flag=wx.ALIGN_CENTER | wx.ALIGN_CENTER_VERTICAL |
								wx.ALL, border=5)
		
		font = wx.Font(9, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, 
					   wx.FONTWEIGHT_NORMAL)
		self.label_txt = wx.StaticText(self.box_panel, -1, "Test")
		self.label_txt.SetFont(font)
		self.label_txt.SetForegroundColour(FGCOLOUR)
		self.info_txt = wx.StaticText(self.box_panel, -1, "Test")
		self.info_txt.SetFont(font)
		self.info_txt.SetForegroundColour(FGCOLOUR)
		self.cbox_sizer.Add(self.label_txt, flag=wx.RIGHT, border=12)
		self.cbox_sizer.Add(self.info_txt, 1)

		self.client = GamutCanvas(self)
		self.client.SetMinSize((300, 300))
		self.canvas_sizer.Add(self.client, 1, flag=wx.EXPAND)
		
		self.options_panel = wx.Panel(self)
		self.options_panel.SetBackgroundColour(BGCOLOUR)
		self.options_sizer = wx.FlexGridSizer(0, 4, 4, 4)
		self.options_panel.SetSizer(self.options_sizer)
		self.options_sizer.AddGrowableCol(0)
		self.options_sizer.AddGrowableCol(3)
		
		self.options_sizer.Add((0, 0))
		
		self.rendering_intent_label = wx.StaticText(self.options_panel, -1,
													lang.getstr("rendering_intent"))
		self.rendering_intent_label.SetForegroundColour(FGCOLOUR)
		self.options_sizer.Add(self.rendering_intent_label,
							   flag=wx.ALIGN_CENTER_VERTICAL | wx.LEFT,
							   border=4)
		
		self.rendering_intent_select = wx.Choice(self.options_panel, -1,
												 size=(125, -1), 
												 choices=[lang.getstr("gamap.intents.a"),
														  lang.getstr("gamap.intents.r"),
														  lang.getstr("gamap.intents.p"),
														  lang.getstr("gamap.intents.s")])
		self.options_sizer.Add(self.rendering_intent_select, 
							   flag=wx.ALIGN_CENTER | wx.ALIGN_CENTER_VERTICAL |
									wx.RIGHT, border=4)
		self.rendering_intent_select.Bind(wx.EVT_CHOICE,
										  self.rendering_intent_select_handler)
		self.rendering_intent_select.SetSelection(0)
		
		self.options_sizer.Add((0, 0))
		self.options_sizer.Add((0, 0))
		
		self.comparison_profile_label = wx.StaticText(self.options_panel, -1,
													  lang.getstr("comparison_profile") +
													  " - -")
		self.comparison_profile_label.SetForegroundColour(FGCOLOUR)
		self.options_sizer.Add(self.comparison_profile_label,
							   flag=wx.ALIGN_CENTER_VERTICAL | wx.LEFT,
							   border=4)
		
		self.canvas_sizer.Add(self.options_panel, flag=wx.EXPAND)
		
		self.comparison_profiles = OrderedDict()
		for name in ["sRGB", "ClayRGB1998", "Rec601_525_60", "Rec601_625_50",
					 "Rec709", "SMPTE240M"]:
			path = get_data_path("ref/%s.icm" % name)
			if path:
				profile = ICCP.ICCProfile(path)
				self.comparison_profiles[name] = profile
		for path in ["AdobeRGB1998.icc",
					 "ECI-RGB.V1.0.icc",
					 "eciRGB_v2.icc",
					 "GRACoL2006_Coated1v2.icc",
					 "ISOcoated.icc",
					 "ISOcoated_v2_eci.icc",
					 #"ISOnewspaper26v4.icc",
					 #"ISOuncoated.icc",
					 #"ISOuncoatedyellowish.icc",
					 "ISOwebcoated.icc",
					 "LStar-RGB.icc",
					 "LStar-RGB-v2.icc",
					 "ProPhoto.icc",
					 "PSO_Coated_300_NPscreen_ISO12647_eci.icc",
					 "PSO_Coated_NPscreen_ISO12647_eci.icc",
					 "PSO_LWC_Improved_eci.icc",
					 "PSO_LWC_Standard_eci.icc",
					 "PSO_MFC_Paper_eci.icc",
					 #"PSO_Uncoated_ISO12647_eci.icc",
					 #"PSO_Uncoated_NPscreen_ISO12647_eci.icc",
					 #"PSO_SNP_Paper_eci.icc",
					 "SC_paper_eci.icc",
					 "SWOP2006_Coated3v2.icc",
					 "SWOP2006_Coated5v2.icc"]:
			try:
				profile = ICCP.ICCProfile(path)
			except IOError:
				pass
			else:
				self.comparison_profiles[profile.getDescription()] = profile
		
		self.comparison_profile_select = wx.Choice(self.options_panel, -1,
												   size=(125, -1), 
												   choices=self.comparison_profiles.keys())
		self.options_sizer.Add(self.comparison_profile_select, 
							   flag=wx.ALIGN_CENTER | wx.ALIGN_CENTER_VERTICAL |
									wx.RIGHT, border=4)
		self.comparison_profile_select.Bind(wx.EVT_CHOICE,
											self.comparison_profile_select_handler)
		self.comparison_profile_select.SetSelection(0)
		
		self.options_sizer.Add((0, 0))

		self.client.canvas.Bind(wx.EVT_MOTION, self.OnMotion)
		
		self.droptarget = FileDrop()
		self.droptarget.drophandlers = {
			".icc": self.drop_handler,
			".icm": self.drop_handler
		}
		self.droptarget.unsupported_handler = self.drop_unsupported_handler
		self.SetDropTarget(self.droptarget)
		
		self.SetSaneGeometry(
			getcfg("position.profile_info.x"), 
			getcfg("position.profile_info.y"), 
			getcfg("size.profile_info.w"), 
			getcfg("size.profile_info.h"))
		
		self.Bind(wx.EVT_MOVE, self.OnMove)
		self.Bind(wx.EVT_SIZE, self.OnSize)
	
	def comparison_profile_select_handler(self, event):
		self.DrawCanvas()

	def rendering_intent_select_handler(self, event):
		self.DrawCanvas()
	
	def drop_handler(self, path):
		"""
		Drag'n'drop handler for .cal/.icc/.icm files.
		
		"""
		self.LoadProfile(path)

	def drop_unsupported_handler(self):
		"""
		Drag'n'drop handler for unsupported files. 
		
		Shows an error message.
		
		"""
		files = self.droptarget._filenames
		InfoDialog(self, msg=lang.getstr("error.file_type_unsupported") +
							 "\n\n" + "\n".join(files), 
				   ok=lang.getstr("ok"), 
				   bitmap=geticon(32, "dialog-error"))

	def LoadProfile(self, profile):
		if not isinstance(profile, ICCP.ICCProfile):
			try:
				profile = ICCP.ICCProfile(profile)
			except ICCP.ICCProfileInvalidError, exception:
				InfoDialog(self, msg=lang.getstr("profile.invalid") + 
									 "\n" + path, 
						   ok=lang.getstr("ok"), 
						   bitmap=geticon(32, "dialog-error"))
				return
			if (profile.profileClass not in ("abst", "mntr", "prtr", "scnr", "spac") or
				profile.colorSpace not in ("RGB", "CMYK")):
				show_result_dialog(Error(lang.getstr("profile.unsupported",
													 (profile.profileClass,
													  profile.colorSpace))), self)
				return
		self.profile = profile
		
		self.title_txt.SetLabel(profile.getDescription())
		self.title_sizer.Layout()
		
		labels = []
		infos = []
		
		for label, value in profile.get_info():
			label = label.replace("&", "&&").replace("\0", "")
			value = universal_newlines(value.strip()).replace("&", "&&").replace("\0", "").split("\n")
			#if (label in ("Device", "Manufacturer ID", "Model ID", "Attributes") or
				#value in ("Yes", "No") or label.startswith("Description") or
				#value.startswith("[")):
			linecount = len(value)
			for i, line in enumerate(value):
				value[i] = line.strip()
			if label.startswith("Meta"):
				labels.append(label)
				infos.append("")
				for line in value:
					line = line.split(":", 1)
					labels.append("    " + line[0].strip())
					infos.append(line[1].strip())
			else:
				label = universal_newlines(label).split("\n")
				while len(label) < linecount:
					label.append("")
				label = "\n".join(label)
				labels.append(label)
				value = "\n".join(value)
				infos.append(value)
		
		self.label_txt.SetLabel("\n".join(labels))
		self.info_txt.SetLabel("\n".join(infos))
		self.box_panel.Layout()
		self.box_panel.FitInside()
		self.box_panel.SetScrollbars(0, 20, 0, 0)
		self.DrawCanvas()

	def DrawCanvas(self, event=None):
		self.SetStatusText('')
		try:
			self.client.DrawCanvas("a*b* " + lang.getstr("gamut"),
								   [self.comparison_profiles.values()[self.comparison_profile_select.GetSelection()],
									self.profile],
								   intent={0: "a",
										   1: "r",
										   2: "p",
										   3: "s"}.get(self.rendering_intent_select.GetSelection()))
		except Exception, exception:
			show_result_dialog(exception, self)

	def OnMotion(self, event):
		if isinstance(event, wx.MouseEvent):
			xy = self.client._getXY(event)
		else:
			xy = event
			legend = legend.split(", ")
		self.SetStatusText("a = %.2f, b = %.2f" % xy)
		if isinstance(event, wx.MouseEvent):
			event.Skip() # Go to next handler

	def OnMove(self, event=None):
		if self.IsShownOnScreen() and not \
		   self.IsMaximized() and not self.IsIconized():
			x, y = self.GetScreenPosition()
			setcfg("position.profile_info.x", x)
			setcfg("position.profile_info.y", y)
		if event:
			event.Skip()
	
	def OnSize(self, event=None):
		wx.CallAfter(self.Zoom)
		if self.IsShownOnScreen() and not \
		   self.IsMaximized() and not self.IsIconized():
			w, h = self.GetSize()
			setcfg("size.profile_info.w", w)
			setcfg("size.profile_info.h", h)
		if event:
			event.Skip()
	
	def Zoom(self):
		if self.client.last_draw:
			self.client._DrawCanvas(self.client.last_draw[0])


class GamutViewer(wx.App):

	def OnInit(self):
		self.frame = ProfileInfoFrame(None, -1)
		return True


def main(profile=None):
	config.initcfg()
	lang.init()
	lang.update_defaults()
	app = GamutViewer(0)
	app.frame.Fit()
	app.frame.SetSize((app.frame.GetSize()[0] -
					   app.frame.client.GetSize()[0] +
					   app.frame.client.GetSize()[1],
					   getcfg("size.profile_info.h") - 1))
	app.frame.SetMinSize(app.frame.GetSize())
	app.frame.LoadProfile(profile or ICCP.get_display_profile())
	app.frame.Show(True)
	app.frame.SetSize((app.frame.GetSize()[0],
					   app.frame.GetSize()[1] + 1))  # To make scrollbars show
	app.MainLoop()

if __name__ == '__main__':
    main(*sys.argv[1:2])