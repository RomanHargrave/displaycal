# -*- coding: utf-8 -*-

import wx
import wx.xrc as xrc
try:
	import floatspin
except ImportError:
	import wx.lib.agw.floatspin as floatspin

class FloatSpinCtrlXmlHandler(xrc.XmlResourceHandler):
	
	def __init__(self):
		xrc.XmlResourceHandler.__init__(self)
		# Standard styles
		self.AddWindowStyles()
		
	def CanHandle(self,node):
		return self.IsOfClass(node, 'FloatSpin')
		
	# Process XML parameters and create the object
	def DoCreateResource(self):
		try:
			min_val = float(self.GetText('min_val'))
		except:
			min_val = None
		try:
			max_val = float(self.GetText('max_val'))
		except:
			max_val = None
		try:
			increment = float(self.GetText('increment'))
		except:
			increment = 1.0
		is_spinctrldbl = (hasattr(wx, 'SpinCtrlDouble') and
						  issubclass(floatspin.FloatSpin, wx.SpinCtrlDouble))
		if is_spinctrldbl:
			defaultstyle = wx.SP_ARROW_KEYS | wx.ALIGN_RIGHT
		else:
			defaultstyle = 0
		w = floatspin.FloatSpin(parent=self.GetParentAsWindow(),
								id=self.GetID(),
								pos=self.GetPosition(),
								size=self.GetSize(),
								style=self.GetStyle(defaults=defaultstyle),
								min_val=min_val,
								max_val=max_val,
								increment=increment,
								name=self.GetName())

		try:
			w.SetValue(float(self.GetText('value')))
		except:
			pass

		try:
			w.SetDigits(int(self.GetText('digits')))
		except:
			pass

		self.SetupWindow(w)
		return w
