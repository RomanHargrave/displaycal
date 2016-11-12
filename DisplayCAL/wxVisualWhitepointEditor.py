"""
Visual whitepoint editor

Based on wx.lib.agw.cubecolourdialog 0.4 by Andrea Gavana @ 26 Feb 2012

License: wxPython license

"""

import colorsys
import sys
from math import pi, sin, cos, sqrt, atan2

from wxfixes import wx, wx_Panel, GenBitmapButton as BitmapButton
from config import (defaults, getbitmap, getcfg, get_default_dpi,
                    get_icon_bundle, geticon, initcfg, setcfg)
from meta import name as appname
from wxMeasureFrame import get_default_size
import localization as lang


# Define a translation string
_ = wx.GetTranslation

colourAttributes = ["r", "g", "b", "h", "s", "v"]
colourMaxValues = [255, 255, 255, 359, 255, 255]
checkColour = wx.Colour(200, 200, 200)


def rad2deg(x):
    """
    Transforms radians into degrees.

    :param `x`: a float representing an angle in radians.    
    """
    
    return 180.0*x/pi


def deg2rad(x):
    """
    Transforms degrees into radians.

    :param `x`: a float representing an angle in degrees.    
    """

    return x*pi/180.0


def s(i):
    """
    Scale for HiDPI if necessary
    
    """
    return i * max(getcfg("app.dpi") / get_default_dpi(), 1)


def Distance(pt1, pt2):
    """
    Returns the distance between 2 points.

    :param `pt1`: an instance of :class:`Point`;
    :param `pt2`: another instance of :class:`Point`.    
    """

    distance = sqrt((pt1.x - pt2.x)**2.0 + (pt1.y - pt2.y)**2.0)
    return int(round(distance))


def AngleFromPoint(pt, center):
    """
    Returns the angle between the x-axis and the line connecting the center and
    the point `pt`.

    :param `pt`: an instance of :class:`Point`;
    :param `center`: a float value representing the center.
    """

    y = -1*(pt.y - center.y)
    x = pt.x - center.x
    if x == 0 and y == 0:
    
        return 0.0
    
    else:
    
        return atan2(y, x)


def RestoreOldDC(dc, oldPen, oldBrush, oldMode):
    """
    Restores the old settings for a :class:`DC`.

    :param `dc`: an instance of :class:`DC`;
    :param `oldPen`: an instance of :class:`Pen`;
    :param `oldBrush`: an instance of :class:`Brush`;
    :param `oldMode`: the :class:`DC` drawing mode bit.
    """

    dc.SetPen(oldPen)
    dc.SetBrush(oldBrush)
    dc.SetLogicalFunction(oldMode)


def DrawCheckerBoard(dc, rect, checkColour, box=5):
    """
    Draws a checkerboard on a :class:`DC`.

    :param `dc`: an instance of :class:`DC`;
    :param `rect`: the client rectangle on which to draw the checkerboard;
    :param `checkColour`: the colour used for the dark checkerboards;
    :param `box`: the checkerboards box sizes.
    
    :note: Used for the Alpha channel control and the colour panels.
    """

    y = rect.y
    checkPen = wx.Pen(checkColour)
    checkBrush = wx.Brush(checkColour)

    dc.SetPen(checkPen) 
    dc.SetBrush(checkBrush)
    dc.SetClippingRect(rect)
    
    while y < rect.height: 
        x = box*((y/box)%2) + 2
        while x < rect.width: 
            dc.DrawRectangle(x, y, box, box) 
            x += box*2 
        y += box
        


class Colour(wx.Colour):
    """
    This is a subclass of :class:`Colour`, which adds Hue, Saturation and Brightness
    capability to the base class. It contains also methods to convert RGB triplets
    into HSB triplets and vice-versa.
    """

    def __init__(self, colour):
        """
        Default class constructor.

        :param `colour`: a standard :class:`Colour`.
        """

        wx.Colour.__init__(self)

        self.r = colour.Red()
        self.g = colour.Green()
        self.b = colour.Blue()
        self._alpha = colour.Alpha()
        
        self.ToHSV()

        
    def ToRGB(self):
        """ Converts a HSV triplet into a RGB triplet. """
    
        maxVal = self.v
        delta = (maxVal*self.s)/255.0
        minVal = maxVal - delta

        hue = float(self.h)

        if self.h > 300 or self.h <= 60:
        
            self.r = maxVal
            
            if self.h > 300:
            
                self.g = int(round(minVal))
                hue = (hue - 360.0)/60.0
                self.b = int(round(-(hue*delta - minVal)))
            
            else:
            
                self.b = int(round(minVal))
                hue = hue/60.0
                self.g = int(round(hue*delta + minVal))
            
        elif self.h > 60 and self.h < 180:
        
            self.g = int(round(maxVal))
            
            if self.h < 120:
            
                self.b = int(round(minVal))
                hue = (hue/60.0 - 2.0)*delta
                self.r = int(round(minVal - hue))
            
            else:
            
                self.r = int(round(minVal))
                hue = (hue/60.0 - 2.0)*delta
                self.b = int(round(minVal + hue))
            
        
        else:
        
            self.b = int(round(maxVal))
            
            if self.h < 240:
            
                self.r = int(round(minVal))
                hue = (hue/60.0 - 4.0)*delta
                self.g = int(round(minVal - hue))
            
            else:
            
                self.g = int(round(minVal))
                hue = (hue/60.0 - 4.0)*delta
                self.r = int(round(minVal + hue))
        

    def ToHSV(self):
        """ Converts a RGB triplet into a HSV triplet. """

        minVal = float(min(self.r, min(self.g, self.b)))
        maxVal = float(max(self.r, max(self.g, self.b)))
        delta = maxVal - minVal
        
        self.v = int(round(maxVal))
        
        if abs(delta) < 1e-6:
        
            self.h = self.s = 0
        
        else:
        
            temp = delta/maxVal
            self.s = int(round(temp*255.0))

            if self.r == int(round(maxVal)):
            
                temp = float(self.g-self.b)/delta
            
            elif self.g == int(round(maxVal)):
            
                temp = 2.0 + (float(self.b-self.r)/delta)
            
            else:
            
                temp = 4.0 + (float(self.r-self.g)/delta)
            
            temp *= 60
            if temp < 0:
            
                temp += 360
            
            elif temp >= 360.0:
            
                temp = 0

            self.h = int(round(temp))


    def GetPyColour(self):
        """ Returns the wxPython :class:`Colour` associated with this instance. """

        return wx.Colour(self.r, self.g, self.b, self._alpha)


class BasePyControl(wx.PyControl):
    """
    Base class used to hold common code for the HSB colour wheel and the RGB
    colour cube.
    """

    def __init__(self, parent, bitmap=None):
        """
        Default class constructor.
        Used internally. Do not call it in your code!

        :param `parent`: the control parent;
        :param `bitmap`: the background bitmap for this custom control.
        """

        wx.PyControl.__init__(self, parent, style=wx.NO_BORDER)
        self.SetBackgroundStyle(wx.BG_STYLE_CUSTOM)

        self._bitmap = bitmap
        
        self._mainFrame = wx.GetTopLevelParent(self)

        self.Bind(wx.EVT_SIZE, self.OnSize)
        self.Bind(wx.EVT_PAINT, self.OnPaint)
        self.Bind(wx.EVT_ERASE_BACKGROUND, self.OnEraseBackground)
        self.Bind(wx.EVT_LEFT_DOWN, self.OnLeftDown)
        self.Bind(wx.EVT_LEFT_UP, self.OnLeftUp)
        self.Bind(wx.EVT_MOTION, self.OnMotion)


    def OnPaint(self, event):
        """
        Handles the ``wx.EVT_PAINT`` for :class:`BasePyControl`.

        :param `event`: a :class:`PaintEvent` event to be processed.
        """

        dc = wx.AutoBufferedPaintDC(self)
        self.Draw(dc)

        if self._mainFrame._initOver:
            self.DrawMarkers(dc)


    def Draw(self, dc):
        dc.SetBackground(wx.Brush(self.GetParent().GetBackgroundColour()))
        
        dc.Clear()
        dc.DrawBitmap(self._bitmap, 0, 0, True)
        

    def OnEraseBackground(self, event):
        """
        Handles the ``wx.EVT_ERASE_BACKGROUND`` for :class:`BasePyControl`.

        :param `event`: a :class:`EraseEvent` event to be processed.

        :note: This is intentionally empty to reduce flicker.        
        """

        pass

    
    def DrawMarkers(self, dc=None):
        """
        Draws the markers on top of the background bitmap.

        :param `dc`: an instance of :class:`DC`.
        
        :note: This method must be overridden in derived classes.
        """

        pass


    def DrawLines(self, dc):
        """
        Draws the lines connecting the markers on top of the background bitmap.

        :param `dc`: an instance of :class:`DC`.
        
        :note: This method must be overridden in derived classes.
        """

        pass
    

    def AcceptsFocusFromKeyboard(self):
        """
        Can this window be given focus by keyboard navigation? If not, the
        only way to give it focus (provided it accepts it at all) is to click
        it.

        :note: This method always returns ``False`` as we do not accept focus from
         the keyboard.

        :note: Overridden from :class:`PyControl`.
        """

        return False


    def AcceptsFocus(self):
        """
        Can this window be given focus by mouse click?

        :note: This method always returns ``False`` as we do not accept focus from
         mouse click.

        :note: Overridden from :class:`PyControl`.
        """

        return False

    
    def OnLeftDown(self, event):
        """
        Handles the ``wx.EVT_LEFT_DOWN`` for :class:`BasePyControl`.

        :param `event`: a :class:`MouseEvent` event to be processed.
        
        :note: This method must be overridden in derived classes.
        """

        pass


    def OnLeftUp(self, event):
        """
        Handles the ``wx.EVT_LEFT_UP`` for :class:`BasePyControl`.

        :param `event`: a :class:`MouseEvent` event to be processed.
        
        :note: This method must be overridden in derived classes.
        """

        pass


    def OnMotion(self, event):
        """
        Handles the ``wx.EVT_MOTION`` for :class:`BasePyControl`.

        :param `event`: a :class:`MouseEvent` event to be processed.
        
        :note: This method must be overridden in derived classes.
        """

        pass
    
    
    def OnSize(self, event):
        """
        Handles the ``wx.EVT_SIZE`` for :class:`BasePyControl`.

        :param `event`: a :class:`SizeEvent` event to be processed.        
        """

        self.Refresh()
        

    def DoGetBestSize(self):
        """
        Overridden base class virtual. Determines the best size of the
        control based on the bitmap size.

        :note: Overridden from :class:`PyControl`.
        """

        return wx.Size(self._bitmap.GetWidth(), self._bitmap.GetHeight())
        
    
class HSVWheel(BasePyControl):
    """
    Implements the drawing, mouse handling and sizing routines for the HSV
    colour wheel.
    """

    def __init__(self, parent):
        """
        Default class constructor.
        Used internally. Do not call it in your code!

        :param `parent`: the control parent window.
        """

        BasePyControl.__init__(self, parent, bitmap=getbitmap("theme/colorwheel"))
        self._mouseIn = False


    def DrawMarkers(self, dc=None):
        """
        Draws the markers on top of the background bitmap.

        :param `dc`: an instance of :class:`DC`.
        """

        if dc is None:
            dc = wx.ClientDC(self)
            if sys.platform != "darwin":
                dc = wx.BufferedDC(dc)
        self.Draw(dc)

        #oldPen, oldBrush, oldMode = dc.GetPen(), dc.GetBrush(), dc.GetLogicalFunction()
        brightMark = self._mainFrame._currentRect
        darkMarkOuter = wx.Rect(brightMark.x-1, brightMark.y-1,
                                brightMark.width+2, brightMark.height+2)
        darkMarkInner = wx.Rect(brightMark.x+1, brightMark.y+1,
                                brightMark.width-2, brightMark.height-2)
        dc.SetBrush(wx.TRANSPARENT_BRUSH)

        for pencolour, rect in ((wx.BLACK, darkMarkOuter),
                                (wx.WHITE, brightMark),
                                (wx.BLACK, darkMarkInner)):
            dc.SetPen(wx.Pen(pencolour, 1))
            #dc.SetLogicalFunction(wx.XOR)
            
            dc.DrawRectangleRect(rect)
        #RestoreOldDC(dc, oldPen, oldBrush, oldMode)
        

    def OnLeftDown(self, event):
        """
        Handles the ``wx.EVT_LEFT_DOWN`` for :class:`HSVWheel`.

        :param `event`: a :class:`MouseEvent` event to be processed.
        """

        point = wx.Point(event.GetX(), event.GetY())
        self._mouseIn = False

        if self.InCircle(point):
            self._mouseIn = True

        if self._mouseIn:
            self.CaptureMouse()
            self.TrackPoint(point)


    def OnLeftUp(self, event):
        """
        Handles the ``wx.EVT_LEFT_UP`` for :class:`HSVWheel`.

        :param `event`: a :class:`MouseEvent` event to be processed.
        """

        if self.GetCapture():
            self.ReleaseMouse()
            self._mouseIn = False


    def OnMotion(self, event):
        """
        Handles the ``wx.EVT_MOTION`` for :class:`HSVWheel`.

        :param `event`: a :class:`MouseEvent` event to be processed.
        """

        point = wx.Point(event.GetX(), event.GetY())

        if self.GetCapture() and self._mouseIn:
            self.TrackPoint(point)
        

    def InCircle(self, pt):
        """
        Returns whether a point is inside the HSV wheel or not.

        :param `pt`: an instance of :class:`Point`.
        """

        return Distance(pt, self._mainFrame._centre) <= (self._bitmap.Size[0]) / 2


    def TrackPoint(self, pt):
        """
        Track a mouse event inside the HSV colour wheel.

        :param `pt`: an instance of :class:`Point`.
        """

        if not self._mouseIn:
            return

        dc = wx.ClientDC(self)
        self.DrawMarkers(dc)
        mainFrame = self._mainFrame
        colour = mainFrame._colour
                
        colour.h = int(round(rad2deg(AngleFromPoint(pt, mainFrame._centre))))
        if colour.h < 0:
            colour.h += 360

        colour.s = int(round(Distance(pt, mainFrame._centre)*255.0/((self._bitmap.Size[0] - s(12)) / 2)*0.2))
        if colour.s > 255:
            colour.s = 255

        mainFrame.CalcRects()
        self.DrawMarkers(dc)
        colour.ToRGB()
        mainFrame.SetSpinVals()
        
        mainFrame.DrawBright()


class BaseLineCtrl(wx.PyControl):
    """
    Base class used to hold common code for the Alpha channel control and the
    brightness palette control.
    """

    def __init__(self, parent):
        """
        Default class constructor.
        Used internally. Do not call it in your code!

        :param `parent`: the control parent window.
        """

        wx.PyControl.__init__(self, parent, size=(s(20), s(102)),
                              style=wx.NO_BORDER)
        self.SetBackgroundStyle(wx.BG_STYLE_CUSTOM)    

        self._mainFrame = wx.GetTopLevelParent(self)
        
        self.Bind(wx.EVT_SIZE, self.OnSize)
        self.Bind(wx.EVT_ERASE_BACKGROUND, self.OnEraseBackground)
        self.Bind(wx.EVT_LEFT_DOWN, self.OnLeftDown)
        self.Bind(wx.EVT_LEFT_UP, self.OnLeftUp)
        self.Bind(wx.EVT_MOTION, self.OnMotion)


    def OnEraseBackground(self, event):
        """
        Handles the ``wx.EVT_ERASE_BACKGROUND`` for :class:`BaseLineCtrl`.

        :param `event`: a :class:`EraseEvent` event to be processed.

        :note: This is intentionally empty to reduce flicker.        
        """

        pass

    
    def OnLeftDown(self, event):
        """
        Handles the ``wx.EVT_LEFT_DOWN`` for :class:`BaseLineCtrl`.

        :param `event`: a :class:`MouseEvent` event to be processed.
        """

        point = wx.Point(event.GetX(), event.GetY())
        theRect = self.GetClientRect()

        if not theRect.Contains(point):
            event.Skip()
            return
        
        self.CaptureMouse()
        self.TrackPoint(point)


    def OnLeftUp(self, event):
        """
        Handles the ``wx.EVT_LEFT_UP`` for :class:`BaseLineCtrl`.

        :param `event`: a :class:`MouseEvent` event to be processed.
        """

        if self.GetCapture():
            self.ReleaseMouse()
            

    def OnMotion(self, event):
        """
        Handles the ``wx.EVT_MOTION`` for :class:`BaseLineCtrl`.

        :param `event`: a :class:`MouseEvent` event to be processed.
        """

        point = wx.Point(event.GetX(), event.GetY())

        if self.GetCapture():
            self.TrackPoint(point)


    def OnSize(self, event):
        """
        Handles the ``wx.EVT_SIZE`` for :class:`BaseLineCtrl`.

        :param `event`: a :class:`SizeEvent` event to be processed.
        """

        self.Refresh()


    def DoGetBestSize(self):
        """
        Overridden base class virtual. Determines the best size of the control.

        :note: Overridden from :class:`PyControl`.
        """

        return wx.Size(s(24), s(104))    


    def BuildRect(self):
        """ Internal method. """

        brightRect = wx.Rect(*self.GetClientRect())
        brightRect.x += s(2)
        brightRect.y += s(2)
        brightRect.width -= s(4)
        brightRect.height -= s(4)

        return brightRect


    def AcceptsFocusFromKeyboard(self):
        """
        Can this window be given focus by keyboard navigation? If not, the
        only way to give it focus (provided it accepts it at all) is to click
        it.

        :note: This method always returns ``False`` as we do not accept focus from
         the keyboard.

        :note: Overridden from :class:`PyControl`.
        """

        return False


    def AcceptsFocus(self):
        """
        Can this window be given focus by mouse click? 

        :note: This method always returns ``False`` as we do not accept focus from
         mouse click.

        :note: Overridden from :class:`PyControl`.
        """

        return False



class BrightCtrl(BaseLineCtrl):
    """
    Implements the drawing, mouse handling and sizing routines for the brightness
    palette control.
    """

    def __init__(self, parent, colour=None):
        """
        Default class constructor.
        Used internally. Do not call it in your code!

        :param `parent`: the control parent window.
        """

        BaseLineCtrl.__init__(self, parent)
        self.Bind(wx.EVT_PAINT, self.OnPaint)
        self._colour = colour or self._mainFrame._colour

        
    def OnPaint(self, event):
        """
        Handles the ``wx.EVT_PAINT`` for :class:`BrightCtrl`.

        :param `event`: a :class:`PaintEvent` event to be processed.
        """

        dc = wx.AutoBufferedPaintDC(self)
        self.Draw(dc)
        
        self.DrawMarkers(dc)


    def Draw(self, dc):
        dc.SetBackground(wx.Brush(self.GetParent().GetBackgroundColour()))
        dc.Clear()
        
        colour = self._colour.GetPyColour()
        brightRect = self.BuildRect()
        
        target_red = colour.Red()
        target_green = colour.Green()
        target_blue = colour.Blue()

        h, s, v = colorsys.rgb_to_hsv(target_red / 255.0, target_green / 255.0,
                                      target_blue / 255.0)
        v = 1.0
        vstep = 1.0/(brightRect.height-1)
        
        for y_pos in range(brightRect.y, brightRect.height+brightRect.y):
            r, g, b = [round(c * 255.0) for c in colorsys.hsv_to_rgb(h, s, v)]
            colour = wx.Colour(int(r), int(g), int(b))
            dc.SetPen(wx.Pen(colour, 1, wx.SOLID))
            dc.DrawRectangle(brightRect.x, y_pos, brightRect.width, 1)
            v = v - vstep

        dc.SetPen(wx.BLACK_PEN)
        dc.SetBrush(wx.TRANSPARENT_BRUSH)
        dc.DrawRectangleRect(brightRect)
        
        
    def TrackPoint(self, pt):
        """
        Tracks a mouse action inside the palette control.

        :param `pt`: an instance of :class:`Point`.
        """

        brightRect = self.BuildRect()
        d = brightRect.GetBottom() - pt.y
        d *= 255
        d /= brightRect.height
        if d < 0:
           d = 0
        if d > 255:
            d = 255;
        
        mainFrame = self._mainFrame
        colour = self._colour

        mainFrame.DrawMarkers()        
        colour.v = int(round(d))

        colour.ToRGB()
        mainFrame.SetSpinVals()

        #mainFrame.DrawMarkers()


    def DrawMarkers(self, dc=None):
        """
        Draws square markers used with mouse gestures.

        :param `dc`: an instance of :class:`DC`.
        """

        if dc is None:
            dc = wx.ClientDC(self)
            if sys.platform != "darwin":
                dc = wx.BufferedDC(dc)
        self.Draw(dc)
            
        colour = self._colour
        brightRect = self.BuildRect()
        
        y = int(round(colour.v/255.0*(brightRect.height-s(6))))
        y = brightRect.height-s(4)-1 - y
        h = s(8)
        darkMarkOuter = wx.Rect(brightRect.x-2, y-1, brightRect.width+4, h)
        brightMark = wx.Rect(brightRect.x-1, y, brightRect.width+2, h-2)
        darkMarkInner = wx.Rect(brightRect.x, y+1, brightRect.width, h-4)

        #oldPen, oldBrush, oldMode = dc.GetPen(), dc.GetBrush(), dc.GetLogicalFunction()
        dc.SetBrush(wx.TRANSPARENT_BRUSH)
        for pencolour, rect in ((wx.BLACK, darkMarkOuter),
                                (wx.WHITE, brightMark),
                                (wx.BLACK, darkMarkInner)):
            dc.SetPen(wx.Pen(pencolour, 1))
            #dc.SetLogicalFunction(wx.XOR)
            
            dc.DrawRectangleRect(rect)
        #RestoreOldDC(dc, oldPen, oldBrush, oldMode)
        

class VisualWhitepointEditor(wx.Frame):
    """
    This is the VisualWhitepointEditor main class implementation.
    """

    def __init__(self, parent, colourData=None):
        """
        Default class constructor.

        :param `colourData`: a standard :class:`ColourData` (as used in :class:`ColourFrame`);
         to hide the alpha channel control or not.
        """

        wx.Frame.__init__(self, parent, id=wx.ID_ANY,
                          title=lang.getstr("whitepoint.visual_editor"),
                          pos=wx.DefaultPosition, style=wx.DEFAULT_FRAME_STYLE,
                          name="VisualWhitepointEditor")
        self.SetIcons(get_icon_bundle([256, 48, 32, 16], appname))

        if colourData:
            self._colourData = colourData
        else:
            self._colourData = wx.ColourData()
            RGB = []
            for attribute in "rgb":
                RGB.append(getcfg("whitepoint.visual_editor." + attribute))
            self._colourData.SetColour(wx.Colour(*RGB))

        self._colour = Colour(self._colourData.GetColour())
        self._bgcolour = Colour(self._colourData.GetColour())
        self._bgcolour.v = getcfg("whitepoint.visual_editor.bg_v")
        self._bgcolour.ToRGB()
        
        self._inMouse = False
        self._initOver = False
        self._inDrawAll = False

        self.mainPanel = wx.Panel(self, -1)
        self.bgPanel = wx_Panel(self, -1)

        self.hsvBitmap = HSVWheel(self.mainPanel)
        self.brightCtrl = BrightCtrl(self.mainPanel)
        self.bgBrightCtrl = BrightCtrl(self.mainPanel, self._bgcolour)
        if sys.platform == "win32" and sys.getwindowsversion() >= (6, ):
            # No need to enable double buffering under Linux and Mac OS X.
            # Under Windows, enabling double buffering on the panel seems
            # to work best to reduce flicker.
            self.hsvBitmap.SetDoubleBuffered(True)
            self.brightCtrl.SetDoubleBuffered(True)
            self.bgBrightCtrl.SetDoubleBuffered(True)

        self.newColourPanel = wx_Panel(self.bgPanel, style=wx.SIMPLE_BORDER)
        
        self.redSpin = wx.SpinCtrl(self.mainPanel, -1, "180", min=0, max=255,
                                   style=wx.SP_ARROW_KEYS)
        self.greenSpin = wx.SpinCtrl(self.mainPanel, -1, "180", min=0, max=255,
                                     style=wx.SP_ARROW_KEYS)
        self.blueSpin = wx.SpinCtrl(self.mainPanel, -1, "180", min=0, max=255,
                                    style=wx.SP_ARROW_KEYS)
        self.hueSpin = wx.SpinCtrl(self.mainPanel, -1, "0", min=0, max=359,
                                   style=wx.SP_ARROW_KEYS)
        self.saturationSpin = wx.SpinCtrl(self.mainPanel, -1, "", min=0, max=255,
                                          style=wx.SP_ARROW_KEYS)
        self.brightnessSpin = wx.SpinCtrl(self.mainPanel, -1, "", min=0, max=255,
                                          style=wx.SP_ARROW_KEYS)
        self.reset_btn = wx.Button(self.mainPanel, -1, lang.getstr("reset"))
        x, y, scale = (float(v) for v in getcfg("dimensions.measureframe.whitepoint.visual_editor").split(","))
        self.area_size_slider = wx.Slider(self.mainPanel, -1,
                                          min(scale * 100, 1500), 100, 1500)
        self.zoomnormalbutton = BitmapButton(self.mainPanel, -1, 
                                             geticon(16, "zoom-original"), 
                                             style=wx.NO_BORDER)
        self.Bind(wx.EVT_BUTTON, self.zoomnormal_handler, self.zoomnormalbutton)
        self.zoomnormalbutton.SetToolTipString(lang.getstr("measureframe."
                                                           "zoomnormal"))
        self.area_x_slider = wx.Slider(self.mainPanel, -1,
                                       int(round(x * 1000)), 0, 1000)
        self.center_x_button = BitmapButton(self.mainPanel, -1, 
                                            geticon(16, "window-center"), 
                                            style=wx.NO_BORDER)
        self.Bind(wx.EVT_BUTTON, self.center_x_handler, self.center_x_button)
        self.center_x_button.SetToolTipString(lang.getstr("measureframe.center"))
        self.area_y_slider = wx.Slider(self.mainPanel, -1,
                                       int(round(y * 1000)), 0, 1000)
        self.center_y_button = BitmapButton(self.mainPanel, -1, 
                                            geticon(16, "window-center"), 
                                            style=wx.NO_BORDER)
        self.Bind(wx.EVT_BUTTON, self.center_y_handler, self.center_y_button)
        self.center_y_button.SetToolTipString(lang.getstr("measureframe.center"))
        self.measure_btn = wx.Button(self.mainPanel, -1, lang.getstr("measure"),
                                     name="visual_whitepoint_editor_measure_btn")
        
        self.Bind(wx.EVT_SIZE, self.area_handler)
        
        self.SetProperties()
        self.DoLayout()

        self.spinCtrls = [self.redSpin, self.greenSpin, self.blueSpin,
                          self.hueSpin, self.saturationSpin, self.brightnessSpin]

        for spin in self.spinCtrls:
            spin.Bind(wx.EVT_SPINCTRL, self.OnSpinCtrl)

        self.reset_btn.Bind(wx.EVT_BUTTON, self.reset_handler)
        self.area_size_slider.Bind(wx.EVT_SLIDER, self.area_handler)
        self.area_x_slider.Bind(wx.EVT_SLIDER, self.area_handler)
        self.area_y_slider.Bind(wx.EVT_SLIDER, self.area_handler)

        self.Bind(wx.EVT_CLOSE, self.OnCloseWindow)
        self.Bind(wx.EVT_CHAR_HOOK, self.OnKeyDown)

        self.Centre(wx.BOTH)

        wx.CallAfter(self.InitFrame)

        self.keepGoing = True
        
        if hasattr(parent, "ambient_measure_handler"):
            self.measure_btn.Bind(wx.EVT_BUTTON,
                                  lambda e: (self.measure_btn.Disable(),
                                             self.setcfg(),
                                             parent.ambient_measure_handler(e)))
        
        
    def SetProperties(self):
        """ Sets some initial properties for :class:`VisualWhitepointEditor` (sizes, values). """
        min_w = s(60)
        self.redSpin.SetMinSize((min_w, -1))
        self.greenSpin.SetMinSize((min_w, -1))
        self.blueSpin.SetMinSize((min_w, -1))
        self.hueSpin.SetMinSize((min_w, -1))
        self.saturationSpin.SetMinSize((min_w, -1))
        self.brightnessSpin.SetMinSize((min_w, -1))


    def DoLayout(self):
        """ Layouts all the controls in the :class:`VisualWhitepointEditor`. """

        margin = s(12)

        dialogSizer = wx.FlexGridSizer(1, 2, 0, 0)
        dialogSizer.AddGrowableRow(0)
        dialogSizer.AddGrowableCol(1)
        mainSizer = wx.BoxSizer(wx.VERTICAL)
        hsvValueSizer = wx.BoxSizer(wx.VERTICAL)
        hsvGridSizer = wx.FlexGridSizer(2, 3, 4, margin)
        rgbValueSizer = wx.BoxSizer(wx.HORIZONTAL)
        rgbGridSizer = wx.FlexGridSizer(2, 3, 4, margin)
        
        hsvSizer = wx.BoxSizer(wx.HORIZONTAL)
        rgbSizer = wx.BoxSizer(wx.VERTICAL)

        mainSizer.Add(rgbSizer, 0, wx.ALL|wx.EXPAND, margin)
        hsvSizer.Add(self.hsvBitmap, 0, wx.ALL, margin)
        hsvSizer.Add(self.brightCtrl, 0, wx.RIGHT|wx.TOP|wx.BOTTOM, margin + s(5) + 2)
        hsvSizer.Add(self.bgBrightCtrl, 0, wx.RIGHT|wx.TOP|wx.BOTTOM, margin + s(5) + 2)
        mainSizer.Add(hsvSizer, 0, wx.ALL|wx.EXPAND, margin)
        
        redLabel = wx.StaticText(self.mainPanel, -1, lang.getstr("red"))
        rgbGridSizer.Add(redLabel, 0)
        greenLabel = wx.StaticText(self.mainPanel, -1, lang.getstr("green"))
        rgbGridSizer.Add(greenLabel, 0)
        blueLabel = wx.StaticText(self.mainPanel, -1, lang.getstr("blue"))
        rgbGridSizer.Add(blueLabel, 0)
        rgbGridSizer.Add(self.redSpin, 0, wx.EXPAND)
        rgbGridSizer.Add(self.greenSpin, 0, wx.EXPAND)
        rgbGridSizer.Add(self.blueSpin, 0, wx.EXPAND)
        rgbValueSizer.Add(rgbGridSizer, 1, 0, 0)
        mainSizer.Add(rgbValueSizer, 0, wx.LEFT|wx.RIGHT|wx.BOTTOM|wx.EXPAND, margin)
        hueLabel = wx.StaticText(self.mainPanel, -1, lang.getstr("hue"))
        hsvGridSizer.Add(hueLabel, 0)
        saturationLabel = wx.StaticText(self.mainPanel, -1, lang.getstr("saturation"))
        hsvGridSizer.Add(saturationLabel, 0)
        brightnessLabel = wx.StaticText(self.mainPanel, -1, lang.getstr("brightness"))
        hsvGridSizer.Add(brightnessLabel, 0)
        hsvGridSizer.Add(self.hueSpin, 0, wx.EXPAND)
        hsvGridSizer.Add(self.saturationSpin, 0, wx.EXPAND)
        hsvGridSizer.Add(self.brightnessSpin, 0, wx.EXPAND)
        hsvValueSizer.Add(hsvGridSizer, 1, wx.EXPAND)
        mainSizer.Add(hsvValueSizer, 0, wx.LEFT|wx.RIGHT|wx.EXPAND, margin)
        mainSizer.Add(self.reset_btn, 0, wx.ALL | wx.ALIGN_CENTER, margin)
        area_slider_label = wx.StaticText(self.mainPanel, -1,
                                          lang.getstr("measureframe.title"))
        mainSizer.Add(area_slider_label, 0, wx.TOP | wx.LEFT, margin)
        mainSizer.Add((1, 8))
        slider_sizer = wx.FlexGridSizer(3, 3, s(4), margin)
        slider_sizer.AddGrowableCol(1)
        mainSizer.Add(slider_sizer, 0, wx.EXPAND | wx.LEFT | wx.RIGHT |
                                       wx.BOTTOM, margin)
        slider_sizer.Add(wx.StaticText(self.mainPanel, -1, lang.getstr("size")),
                         0, wx.ALIGN_CENTER_VERTICAL)
        slider_sizer.Add(self.area_size_slider, 0, wx.ALIGN_CENTER_VERTICAL |
                                                   wx.EXPAND)
        slider_sizer.Add(self.zoomnormalbutton, 0, wx.ALIGN_CENTER_VERTICAL)
        slider_sizer.Add(wx.StaticText(self.mainPanel, -1, "X"),
                         0, wx.ALIGN_CENTER_VERTICAL)
        slider_sizer.Add(self.area_x_slider, 0, wx.ALIGN_CENTER_VERTICAL |
                                                wx.EXPAND)
        slider_sizer.Add(self.center_x_button, 0, wx.ALIGN_CENTER_VERTICAL)
        slider_sizer.Add(wx.StaticText(self.mainPanel, -1, "Y"),
                         0, wx.ALIGN_CENTER_VERTICAL)
        slider_sizer.Add(self.area_y_slider, 0, wx.ALIGN_CENTER_VERTICAL |
                                                wx.EXPAND)
        slider_sizer.Add(self.center_y_button, 0, wx.ALIGN_CENTER_VERTICAL)
        mainSizer.Add(self.measure_btn, 0, wx.ALL | wx.ALIGN_CENTER, margin)

        self.mainPanel.SetAutoLayout(True)
        self.mainPanel.SetSizer(mainSizer)
        mainSizer.Fit(self.mainPanel)
        mainSizer.SetSizeHints(self.mainPanel)
        
        dialogSizer.Add(self.mainPanel, 0, wx.EXPAND)
        dialogSizer.Add(self.bgPanel, 1, wx.EXPAND, 0)
        self.SetAutoLayout(True)
        self.SetSizer(dialogSizer)
        dialogSizer.Fit(self)
        dialogSizer.SetSizeHints(self)
        self.Layout()

        self.mainSizer = mainSizer
        self.dialogSizer = dialogSizer
        

    def InitFrame(self):
        """ Initialize the :class:`VisualWhitepointEditor`. """

        hsvRect = self.hsvBitmap.GetClientRect()
        self._centre = wx.Point(hsvRect.x + hsvRect.width/2, hsvRect.y + hsvRect.height/2)

        self.CalcRects()

        self.SetSpinVals()

        self._initOver = True
        wx.CallAfter(self.Refresh)
                

    def CalcRects(self):
        """ Calculates the brightness control user-selected rect. """

        RECT_WIDTH = s(5)

        pt = self.PtFromAngle(self._colour.h, self._colour.s, self._centre)
        self._currentRect = wx.Rect(pt.x - RECT_WIDTH, pt.y - RECT_WIDTH,
                                    2*RECT_WIDTH, 2*RECT_WIDTH)


    def DrawMarkers(self, dc=None):
        """
        Draws the markers for all the controls.

        :param `dc`: an instance of :class:`DC`. If `dc` is ``None``, a :class:`ClientDC` is
         created on the fly.
        """

        self.hsvBitmap.DrawMarkers(dc)
        self.brightCtrl.DrawMarkers(dc)
        self.bgBrightCtrl.DrawMarkers(dc)


    def DrawHSB(self):
        """ Refreshes the HSB colour wheel. """

        self.hsvBitmap.Refresh()
        

    def DrawBright(self):
        """ Refreshes the brightness control. """

        self.brightCtrl.Refresh()
        self.bgBrightCtrl.Refresh()
        
        
    def SetSpinVals(self):
        """ Sets the values for all the spin controls. """

        self.redSpin.SetValue(self._colour.r)
        self.greenSpin.SetValue(self._colour.g)
        self.blueSpin.SetValue(self._colour.b)
        
        self.hueSpin.SetValue(self._colour.h)
        self.saturationSpin.SetValue(self._colour.s)
        self.brightnessSpin.SetValue(self._colour.v)     

        self.SetPanelColours()
        

    def SetPanelColours(self):
        """ Assigns colours to the colour panels. """

        self.newColourPanel.BackgroundColour = self._colour.GetPyColour()
        self._bgcolour.h = self._colour.h
        self._bgcolour.s = self._colour.s
        self._bgcolour.ToRGB()
        self.bgPanel.BackgroundColour = self._bgcolour.GetPyColour()
        self.bgPanel.Refresh()
        
        
    def OnCloseWindow(self, event):
        """
        Handles the ``wx.EVT_CLOSE`` event for :class:`VisualWhitepointEditor`.
        
        :param `event`: a :class:`CloseEvent` event to be processed.
        """

        self.Destroy()
    
    
    def OnKeyDown(self, event):
        """
        Handles the ``wx.EVT_CHAR_HOOK`` event for :class:`VisualWhitepointEditor`.
        
        :param `event`: a :class:`KeyEvent` event to be processed.
        """

        if event.GetKeyCode() == wx.WXK_ESCAPE:
            self.Close()
        #elif event.KeyCode in (wx.WXK_LEFT, wx.WXK_RIGHT, wx.WXK_UP,
                               #wx.WXK_DOWN):
            #self._colour.h += {wx.WXK_LEFT: 1,
                     #wx.WXK_RIGHT: -1,
                     #wx.WXK_UP: 0,
                     #wx.WXK_DOWN: 0}[event.KeyCode]
            #if self._colour.h > 359:
                #self._colour.h = 0
            #elif self._colour.h < 0:
                #self._colour.h = 359
            #self._colour.s += {wx.WXK_LEFT: 0,
                     #wx.WXK_RIGHT: 0,
                     #wx.WXK_UP: 1,
                     #wx.WXK_DOWN: -1}[event.KeyCode]
            #if self._colour.s > 255:
                #self._colour.s = 255
            #elif self._colour.s < 0:
                #self._colour.s = 0
            #print self._colour.h, self._colour.s
            #self._colour.ToRGB()
            #self.DrawAll()
        else:
            event.Skip()
    

    def PtFromAngle(self, angle, sat, center):
        """
        Given the angle with respect to the x-axis, returns the point based on
        the saturation value.

        :param `angle`: a float representing an angle;
        :param `sat`: a float representing the colour saturation value;
        :param `center`: a float value representing the center.
        """

        angle = deg2rad(angle)
        sat = min(sat*((self.hsvBitmap._bitmap.Size[0] - s(12)) / 2)/51.0,
                  ((self.hsvBitmap._bitmap.Size[0] - s(12)) / 2))

        x = sat*cos(angle)
        y = sat*sin(angle)

        pt = wx.Point(int(round(x)), -int(round(y)))
        pt.x += center.x
        pt.y += center.y
        
        return pt
        

    def OnSpinCtrl(self, event):
        """
        Handles the ``wx.EVT_SPINCTRL`` event for RGB and HSB colours.

        :param `event`: a :class:`SpinEvent` event to be processed.
        """

        obj = event.GetEventObject()
        position = self.spinCtrls.index(obj)
        colourVal = event.GetInt()

        attribute, maxVal = colourAttributes[position], colourMaxValues[position]

        self.AssignColourValue(attribute, colourVal, maxVal, position)
            

    def AssignColourValue(self, attribute, colourVal, maxVal, position):
        """ Common code to handle spin control changes. """

        originalVal = getattr(self._colour, attribute)
        if colourVal != originalVal and self._initOver:
            
            if colourVal < 0:
                colourVal = 0
            if colourVal > maxVal:
                colourVal = maxVal

            setattr(self._colour, attribute, colourVal)
            if position < 3:
                self._colour.ToHSV()
            else:
                self._colour.ToRGB()

            self.DrawAll()
            

    def DrawAll(self):
        """ Draws all the custom controls after a colour change. """

        if self._initOver and not self._inDrawAll:
            self._inDrawAll = True

            dc1 = wx.ClientDC(self.hsvBitmap)
            self.hsvBitmap.DrawMarkers(dc1)

            dc3 = wx.ClientDC(self.brightCtrl)
            self.brightCtrl.DrawMarkers(dc3)

            self.CalcRects()

            self.DrawHSB()
            self.DrawBright()
            
            self.SetSpinVals()
            self._inDrawAll = False


    def GetColourData(self):
        """ Returns a wxPython compatible :class:`ColourData`. """

        self._colourData.SetColour(self._colour.GetPyColour())
        return self._colourData


    def GetRGBAColour(self):
        """ Returns a 4-elements tuple of red, green, blue, alpha components. """

        return (self._colour.r, self._colour.g, self._colour.b, self._colour._alpha)

    
    def GetHSVAColour(self):
        """ Returns a 4-elements tuple of hue, saturation, brightness, alpha components. """

        return (self._colour.h, self._colour.s, self._colour.v, self._colour._alpha)

    
    def EndModal(self, returncode=wx.ID_OK):
        return returncode


    def MakeModal(self, makemodal=False):
        pass


    def Pulse(self, msg=""):
        return self.keepGoing, False


    def Resume(self):
        self.keepGoing = True


    def Update(self, value, msg=""):
        return self.Pulse(msg)


    def UpdatePulse(self, msg=""):
        return self.Pulse(msg)


    def area_handler(self, event=None):
        scale = self.area_size_slider.Value / 100.0
        x = self.area_x_slider.Value / 1000.0
        y = self.area_y_slider.Value / 1000.0
        w, h = (int(round(get_default_size() * scale)), ) * 2
        self.bgPanel.MinSize = -1, -1
        self.newColourPanel.Size = w, h
        self.bgPanel.MinSize = w + s(24), h + s(24)
        bg_w, bg_h = (float(v) for v in self.bgPanel.Size)
        self.newColourPanel.Position = ((bg_w - (w)) * x), ((bg_h - (h)) * y)
        if event:
            event.Skip()
            if event.GetEventType() == wx.EVT_SIZE.evtType[0]:
                wx.CallAfter(self.area_handler)


    def center_x_handler(self, event):
        self.area_x_slider.SetValue(500)
        self.area_handler()


    def center_y_handler(self, event):
        self.area_y_slider.SetValue(500)
        self.area_handler()


    def flush(self):
        pass


    def start_timer(self, ms=50):
        pass


    def stop_timer(self):
        pass


    def reset_handler(self, event):
        RGB = []
        for attribute in "rgb":
            RGB.append(defaults["whitepoint.visual_editor." + attribute])
        self._colourData.SetColour(wx.Colour(*RGB))
        self._colour.r, self._colour.g, self._colour.b = self._colourData.GetColour()
        self._colour.ToHSV()
        self._bgcolour.v = defaults["whitepoint.visual_editor.bg_v"]
        self.DrawAll()


    def setcfg(self):
        for attribute in "rgb":
            value = getattr(self._colour, attribute)
            setcfg("whitepoint.visual_editor." + attribute, value)
        setcfg("whitepoint.visual_editor.bg_v", self._bgcolour.v)
        x, y = (ctrl.Value / 1000.0 for ctrl in (self.area_x_slider,
                                                 self.area_y_slider))
        scale = self.area_size_slider.Value / 100.0
        setcfg("dimensions.measureframe.whitepoint.visual_editor",
               "%f,%f,%f" % (x, y, scale))


    def write(self, txt):
        pass


    def zoomnormal_handler(self, event):
        scale = float(defaults["dimensions.measureframe.whitepoint.visual_editor"].split(",")[2])
        self.area_size_slider.SetValue(int(round(scale * 100)))
        self.area_handler()


if __name__ == "__main__":
    initcfg()
    lang.init()
    app = wx.App(0)
    dlg = VisualWhitepointEditor(None)
    dlg.Show()
    app.MainLoop()
