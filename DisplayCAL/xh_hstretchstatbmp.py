# -*- coding: utf-8 -*-

import wx
import wx.xrc as xrc
try:
	from wxwindows import HStretchStaticBitmap
except ImportError:
	HStretchStaticBitmap = wx.StaticBitmap

class HStretchStaticBitmapXmlHandler(xrc.XmlResourceHandler):
	
	def __init__(self):
		xrc.XmlResourceHandler.__init__(self)
		# Standard styles
		self.AddWindowStyles()
		
	def CanHandle(self,node):
		return self.IsOfClass(node, 'HStretchStaticBitmap')
		
	# Process XML parameters and create the object
	def DoCreateResource(self):
		w = HStretchStaticBitmap(self.GetParentAsWindow(),
								 self.GetID(),
								 self.GetBitmap('bitmap'),
								 pos=self.GetPosition(),
								 size=self.GetSize(),
								 style=self.GetStyle(),
								 name=self.GetName())

		self.SetupWindow(w)
		return w
