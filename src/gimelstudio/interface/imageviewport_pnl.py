# ----------------------------------------------------------------------------
# Gimel Studio Copyright 2019-2021 by Noah Rahm and contributors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# ----------------------------------------------------------------------------

import wx
import wx.adv
from wx.lib.newevent import NewCommandEvent
import wx.lib.agw.flatmenu as flatmenu

import numpy as np

from gswidgetkit import Button, EVT_BUTTON, NumberField, EVT_NUMBERFIELD_CHANGE

from .utils import ConvertImageToWx, ComputeMenuPosAlignedLeft
from .basewidgets import ZoomPanel
from gimelstudio.datafiles import *

imageviewport_mousezoom_cmd_event, EVT_IMAGEVIEWPORT_MOUSEZOOM = NewCommandEvent()

ID_MENU_UNDOCKPANEL = wx.NewIdRef()
ID_MENU_HIDEPANEL = wx.NewIdRef()


class ImageViewportPanel(wx.Panel):
    def __init__(self, parent, id=wx.ID_ANY, pos=wx.DefaultPosition, size=wx.DefaultSize,
                 style=wx.NO_BORDER | wx.TAB_TRAVERSAL):
        wx.Panel.__init__(self, parent, id, pos, size, style)

        self._parent = parent

        self.SetBackgroundColour(wx.Colour("#464646"))

        self.BuildUI()

    def BuildUI(self):
        main_sizer = wx.BoxSizer(wx.VERTICAL)

        topbar = wx.Panel(self)
        topbar.SetBackgroundColour("#424242")

        topbar_sizer = wx.GridBagSizer(vgap=1, hgap=1)

        self.area_icon = wx.StaticBitmap(topbar, bitmap=ICON_IMAGEVIEWPORT_PANEL.GetBitmap())
        self.area_label = wx.StaticText(topbar, label="")
        self.area_label.SetForegroundColour("#fff")
        self.area_label.SetFont(self.area_label.GetFont().Bold())

        self.zoom_field = NumberField(topbar, default_value=100, label=_("Zoom"),
                                      min_value=25, max_value=250, suffix="%",
                                      show_p=False)
        self.menu_button = Button(topbar, label="", flat=True,
                                  bmp=(ICON_MORE_MENU_SMALL.GetBitmap(), 'left'))

        topbar_sizer.Add(self.area_icon, (0, 0), flag=wx.LEFT | wx.TOP | wx.BOTTOM, border=8)
        topbar_sizer.Add(self.area_label, (0, 1), flag=wx.ALL, border=8)
        topbar_sizer.Add(self.zoom_field, (0, 3), flag=wx.ALL, border=3)
        topbar_sizer.Add(self.menu_button, (0, 4), flag=wx.ALL, border=3)
        topbar_sizer.AddGrowableCol(2)

        topbar.SetSizer(topbar_sizer)

        self.imageviewport = ImageViewport(self)

        main_sizer.Add(topbar, flag=wx.EXPAND | wx.LEFT | wx.RIGHT)
        main_sizer.Add(self.imageviewport, 1, flag=wx.EXPAND | wx.BOTH)

        self.SetSizer(main_sizer)

        # Event bindings
        self.imageviewport.Bind(EVT_IMAGEVIEWPORT_MOUSEZOOM, self.ZoomImageViewport)
        self.zoom_field.Bind(EVT_NUMBERFIELD_CHANGE, self.ChangeZoom)
        self.menu_button.Bind(EVT_BUTTON, self.OnAreaMenuButton)
        self.Bind(wx.EVT_MENU, self.OnMenuUndockPanel, id=ID_MENU_UNDOCKPANEL)
        self.Bind(wx.EVT_MENU, self.OnMenuHidePanel, id=ID_MENU_HIDEPANEL)
        self.imageviewport.Bind(wx.EVT_ENTER_WINDOW, self.OnAreaFocus)

    @property
    def AUIManager(self):
        return self._parent._mgr

    @property
    def Statusbar(self):
        return self._parent.statusbar

    def UpdateViewerImage(self, image, render_time):
        self.imageviewport.UpdateViewerImage(image, render_time)

    def ChangeZoom(self, event):
        level = event.value / 100.0
        self.imageviewport.SetZoomLevel(level)

    def ZoomImageViewport(self, event):
        self.zoom_field.SetValue(event.value)
        self.zoom_field.UpdateDrawing()
        self.imageviewport.UpdateDrawing()
        self.zoom_field.Refresh()
        self.Refresh()

    def OnAreaFocus(self, event):
        self.Statusbar.PushContextHints(2, mouseicon=ICON_MOUSE_MMB,
                                        text=_("Zoom Viewport"), clear=True)
        self.Statusbar.PushContextHints(3, mouseicon=ICON_MOUSE_MMB_MOVEMENT,
                                        text=_("Pan Viewport"))
        self.Statusbar.PushMessage(_("Image Viewport Area"))
        self.Statusbar.UpdateStatusBar()

    def OnAreaMenuButton(self, event):
        self.CreateAreaMenu()
        pos = ComputeMenuPosAlignedLeft(self.area_dropdownmenu, self.menu_button)
        self.area_dropdownmenu.Popup(pos, self)

    def OnMenuUndockPanel(self, event):
        self.AUIManager.GetPane("imageviewport").Float()
        self.AUIManager.Update()

    def OnMenuHidePanel(self, event):
        self.AUIManager.GetPane("imageviewport").Hide()
        self.AUIManager.Update()

    def CreateAreaMenu(self):
        self.area_dropdownmenu = flatmenu.FlatMenu()

        undockpanel_menuitem = flatmenu.FlatMenuItem(self.area_dropdownmenu,
                                                     ID_MENU_UNDOCKPANEL,
                                                     _("Undock panel"), "", wx.ITEM_NORMAL)
        self.area_dropdownmenu.AppendItem(undockpanel_menuitem)

        hidepanel_menuitem = flatmenu.FlatMenuItem(self.area_dropdownmenu,
                                                   ID_MENU_HIDEPANEL,
                                                   _("Hide panel"), "", wx.ITEM_NORMAL)
        self.area_dropdownmenu.AppendItem(hidepanel_menuitem)


class ImageViewport(ZoomPanel):
    def __init__(self, parent):
        ZoomPanel.__init__(self, parent)

        self._parent = parent
        self._zoom = 100
        self._renderTime = 0.00
        self._rendering = False

        img = np.zeros((200, 200, 4), dtype=np.uint16)

        self._viewportImage = ConvertImageToWx(img)

        self.Bind(wx.EVT_KEY_DOWN, self.OnKeyEvent)

    def GetImage(self):
        return self._viewportImage

    def OnDrawBackground(self, dc):
        dc.SetBackground(wx.Brush('#464646'))
        dc.Clear()

    def OnDrawScene(self, dc):
        image = self.GetImage()
        x = (self.Size[0] - image.Width) / 2.0
        y = (self.Size[1] - image.Height) / 2.0

        # draw checkerboard bg
        dc.SetPen(wx.TRANSPARENT_PEN)
        dc.SetBrush(wx.Brush(ICON_BRUSH_CHECKERBOARD.GetBitmap()))
        dc.DrawRectangle(wx.Rect(x, y, image.Width, image.Height))

        # Draw image
        dc.DrawBitmap(image, x, y, useMask=False)

    def OnDrawInterface(self, dc):
        gc = wx.GraphicsContext.Create(dc)

    def OnKeyEvent(self, event):
        code = event.GetKeyCode()
        mouse = wx.Point(self.Size[0] / 2, self.Size[1] / 2)

        # plus (+)
        if code == wx.WXK_NUMPAD_ADD:
            self.ScenePostScale(1.1, 1.1, mouse[0], mouse[1])
        # minus (-)
        elif code == wx.WXK_NUMPAD_SUBTRACT:
            self.ScenePostScale(0.9, 0.9, mouse[0], mouse[1])

        self.UpdateZoomValue()
        self.SendMouseZoomEvent()
        self.UpdateDrawing()

    def OnMousewheel(self, event):
        rotation = event.GetWheelRotation()
        mouse = event.GetPosition()
        if rotation > 1:
            self.ScenePostScale(1.1, 1.1, mouse[0], mouse[1])
        elif rotation < -1:
            self.ScenePostScale(0.9, 0.9, mouse[0], mouse[1])

        self.UpdateZoomValue()
        self.SendMouseZoomEvent()
        self.UpdateDrawing()

    def UpdateZoomValue(self):
        self._zoom = round(self.GetScaleX() * 100)

    def SetZoomLevel(self, zoom, x=0, y=0):
        if x == 0:
            x = self.Size[0]/2
            y = self.Size[1]/2
        self.ScenePostScale(zoom, zoom, x, y)
        self.UpdateZoomValue()
        self.UpdateDrawing()

    def SendMouseZoomEvent(self):
        wx.PostEvent(self,
                     imageviewport_mousezoom_cmd_event(id=self.GetId(),
                     value=self._zoom))

    def UpdateViewerImage(self, image, render_time):
        """ Update the Image Viewport. This refreshes everything
        in the Viewport.

        :param image: wx.Bitmap
        :param float render_time: float value of the image's render time
        """
        self._renderTime = render_time
        self._viewportImage = ConvertImageToWx(image)
        self.UpdateDrawing()
