# -*- coding: utf-8 -*-

import wx
import wx.xrc as xrc
import wx.lib.filebrowsebutton as filebrowse

class FileBrowseButtonXmlHandler(xrc.XmlResourceHandler):
	
	def __init__(self):
		xrc.XmlResourceHandler.__init__(self)
		# Standard styles
		self.AddWindowStyles()
		
	def CanHandle(self,node):
		return self.IsOfClass(node, 'FileBrowseButton')
		
	# Process XML parameters and create the object
	def DoCreateResource(self):
		w = filebrowse.FileBrowseButton(parent=self.GetParentAsWindow(),
										id=self.GetID(),
										pos=self.GetPosition(),
										size=self.GetSize(),
										style=self.GetStyle(),
										labelText=self.GetText('labelText') or 'File Entry:',
										buttonText=self.GetText('buttonText') or 'Browse',
										toolTip=self.GetText('toolTip') or 'Type filename or click browse to choose file',
										dialogTitle=self.GetText('dialogTitle') or 'Choose a file',
										startDirectory=self.GetText('startDirectory') or '.',
										initialValue=self.GetText('initialValue') or '',
										fileMask=self.GetText('fileMask') or '*.*',
										fileMode=self.GetLong('fileMode') or wx.OPEN,
										labelWidth=self.GetLong('labelWidth') or 0,
										name=self.GetName())

		self.SetupWindow(w)
		return w

class FileBrowseButtonWithHistoryXmlHandler(FileBrowseButtonXmlHandler):
	
	def __init__(self):
		FileBrowseButtonXmlHandler.__init__(self)
		
	def CanHandle(self,node):
		return self.IsOfClass(node, 'FileBrowseButtonWithHistory')
		
	# Process XML parameters and create the object
	def DoCreateResource(self):
		w = filebrowse.FileBrowseButtonWithHistory(parent=self.GetParentAsWindow(),
												   id=self.GetID(),
												   pos=self.GetPosition(),
												   size=self.GetSize(),
												   style=self.GetStyle(),
												   labelText=self.GetText('labelText') or 'File Entry:',
												   buttonText=self.GetText('buttonText') or 'Browse',
												   toolTip=self.GetText('toolTip') or 'Type filename or click browse to choose file',
												   dialogTitle=self.GetText('dialogTitle') or 'Choose a file',
												   startDirectory=self.GetText('startDirectory') or '.',
												   initialValue=self.GetText('initialValue') or '',
												   fileMask=self.GetText('fileMask') or '*.*',
												   fileMode=self.GetLong('fileMode') or wx.OPEN,
												   labelWidth=self.GetLong('labelWidth') or 0,
												   name=self.GetName())

		self.SetupWindow(w)
		return w
