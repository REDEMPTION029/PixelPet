"""A per-pixel-alpha cartoon countdown panel; text remains visible after chrome fades."""
import ctypes as C
from collections import OrderedDict
import logging
from . import native_api as n
from .desktop_state import PanelFade

F = C.c_float


class RectF(C.Structure):
    _fields_ = [("X", F), ("Y", F), ("Width", F), ("Height", F)]


for name, args in {
    "GdipCreateBitmapFromScan0": [C.c_int,C.c_int,C.c_int,C.c_int,n.PTR,C.POINTER(n.PTR)],
    "GdipGetImageGraphicsContext": [n.PTR,C.POINTER(n.PTR)],
    "GdipDeleteGraphics": [n.PTR],
    "GdipGraphicsClear": [n.PTR,n.W.DWORD],
    "GdipSetSmoothingMode": [n.PTR,C.c_int],
    "GdipSetTextRenderingHint": [n.PTR,C.c_int],
    "GdipScaleWorldTransform": [n.PTR,F,F,C.c_int],
    "GdipCreateSolidFill": [n.W.DWORD,C.POINTER(n.PTR)],
    "GdipDeleteBrush": [n.PTR],
    "GdipCreatePath": [C.c_int,C.POINTER(n.PTR)],
    "GdipAddPathArc": [n.PTR,F,F,F,F,F,F],
    "GdipClosePathFigure": [n.PTR],
    "GdipFillPath": [n.PTR,n.PTR,n.PTR],
    "GdipDeletePath": [n.PTR],
    "GdipFillEllipse": [n.PTR,n.PTR,F,F,F,F],
    "GdipCreatePen1": [n.W.DWORD,F,C.c_int,C.POINTER(n.PTR)],
    "GdipDeletePen": [n.PTR],
    "GdipDrawEllipse": [n.PTR,n.PTR,F,F,F,F],
    "GdipDrawLine": [n.PTR,n.PTR,F,F,F,F],
    "GdipCreateFontFamilyFromName": [n.W.LPCWSTR,n.PTR,C.POINTER(n.PTR)],
    "GdipGetGenericFontFamilySansSerif": [C.POINTER(n.PTR)],
    "GdipDeleteFontFamily": [n.PTR],
    "GdipCreateFont": [n.PTR,F,C.c_int,C.c_int,C.POINTER(n.PTR)],
    "GdipDeleteFont": [n.PTR],
    "GdipDrawString": [n.PTR,n.W.LPCWSTR,C.c_int,n.PTR,C.POINTER(RectF),n.PTR,n.PTR],
}.items():
    n.bind(n.gdip,name,C.c_int,*args)


class PanelPainter:
    W,H=236,108

    def __init__(self):
        self.fonts=[]
        self.cache=OrderedDict()
        self.digits=self.font(["Comic Sans MS"],34,1)
        self.text=self.font(["YouYuan","幼圆","Microsoft YaHei"],14,0)

    def font(self,names,size,style):
        family=n.PTR()
        for name in names:
            if n.gdip.GdipCreateFontFamilyFromName(name,None,C.byref(family))==0:
                break
        else:
            n.gdicheck(n.gdip.GdipGetGenericFontFamilySansSerif(C.byref(family)))
        font=n.PTR()
        n.gdicheck(n.gdip.GdipCreateFont(family,size,style,2,C.byref(font)))
        self.fonts.append((font,family))
        return font

    def surface(self,remaining,phase,paused,strength,scale=1):
        level=round(strength*16)
        scale=round(scale,3)
        width,height=round(self.W*scale),round(self.H*scale)
        key=(remaining,phase,paused,level,scale)
        if key in self.cache:
            self.cache.move_to_end(key)
            return self.cache[key]
        bitmap,graphics=n.PTR(),n.PTR()
        n.gdicheck(n.gdip.GdipCreateBitmapFromScan0(width,height,0,0xE200B,None,C.byref(bitmap)))
        try:
            n.gdicheck(n.gdip.GdipGetImageGraphicsContext(bitmap,C.byref(graphics)))
            try:
                n.gdip.GdipGraphicsClear(graphics,0)
                n.gdip.GdipSetSmoothingMode(graphics,4)
                n.gdip.GdipSetTextRenderingHint(graphics,4)
                n.gdicheck(n.gdip.GdipScaleWorldTransform(graphics,scale,scale,0))
                def brush(rgb,alpha=255):
                    p=n.PTR();n.gdicheck(n.gdip.GdipCreateSolidFill((max(0,min(255,alpha))<<24)|rgb,C.byref(p)));return p
                def text(value,font,x,y,w,h,rgb,alpha=255):
                    b=brush(rgb,alpha)
                    try:
                        n.gdicheck(n.gdip.GdipDrawString(graphics,value,len(value),font,C.byref(RectF(x,y,w,h)),None,b))
                    finally:n.gdip.GdipDeleteBrush(b)
                if level:
                    path=n.PTR();fill=brush(0xFFF7FD,round(242*level/16))
                    n.gdicheck(n.gdip.GdipCreatePath(0,C.byref(path)))
                    try:
                        for x,y,start in ((2,2,180),(210,2,270),(210,82,0),(2,82,90)):
                            n.gdip.GdipAddPathArc(path,x,y,24,24,start,90)
                        n.gdip.GdipClosePathFigure(path)
                        n.gdip.GdipFillPath(graphics,fill,path)
                    finally:
                        n.gdip.GdipDeletePath(path);n.gdip.GdipDeleteBrush(fill)
                title="休息一下" if phase=="break" else ("准备好了吗" if phase in ("idle","ready") else "一起专注")
                if paused:title+=" · 已暂停"
                text(title,self.text,16,8,215,23,0x79658D,round(255*level/16))
                minutes,seconds=divmod(remaining,60)
                text(f"{minutes:02}:{seconds:02}",self.digits,66,30,164,47,0x70618E if not paused else 0x9A90A3)
                pen=n.PTR();n.gdicheck(n.gdip.GdipCreatePen1(0xFF9F86BD,2,2,C.byref(pen)))
                try:
                    n.gdip.GdipDrawEllipse(graphics,pen,22,43,26,26)
                    n.gdip.GdipDrawLine(graphics,pen,35,56,35,48)
                    n.gdip.GdipDrawLine(graphics,pen,35,56,42,59)
                finally:n.gdip.GdipDeletePen(pen)
                if level:
                    text("开始 25 分钟" if phase in ("idle","ready") else ("继续" if paused else "暂停"),
                         self.text,19,81,122,22,0x8C729F,round(255*level/16))
                    text("设置" if phase in ("idle","ready") else "结束",self.text,164,81,60,22,0xA07891,round(255*level/16))
            finally:
                n.gdip.GdipDeleteGraphics(graphics)
            bits=n.BITMAPDATA();rect=n.GDIRECT(0,0,width,height)
            n.gdicheck(n.gdip.GdipBitmapLockBits(bitmap,C.byref(rect),1,0xE200B,C.byref(bits)))
            try: pixels=b''.join(C.string_at(bits.Scan0+y*bits.Stride,width*4) for y in range(height))
            finally:n.gdip.GdipBitmapUnlockBits(bitmap,C.byref(bits))
            surface=n.Surface(width,height,pixels)
        finally:n.gdip.GdipDisposeImage(bitmap)
        self.cache[key]=surface
        if len(self.cache)>8:
            _,old=self.cache.popitem(last=False);old.close()
        return surface

    def close(self):
        for surface in self.cache.values():surface.close()
        self.cache.clear()
        for font,family in self.fonts:
            n.gdip.GdipDeleteFont(font);n.gdip.GdipDeleteFontFamily(family)
        self.fonts.clear()


class FocusOverlay:
    CLASS="PixelPetCountdownV1"

    def __init__(self,app):
        self.app=app;self.fade=PanelFade();self.painter=PanelPainter();self.last=None
        self.position=(0,0);self.top_cache={}
        self.scale=1
        self.callback=n.WNDPROC(self.dispatch)
        self.definition=n.WNDCLASS(lpfnWndProc=self.callback,hInstance=app.class_instance,lpszClassName=self.CLASS)
        n.checked(n.user.RegisterClassW(C.byref(self.definition)))
        self.hwnd=n.checked(n.user.CreateWindowExW(0x80000|0x80|0x08000000|(8 if app.topmost else 0),
            self.CLASS,"PixelPet · 专注倒计时",0x80000000,0,0,236,108,app.hwnd,None,app.class_instance,None))

    def touch(self):self.fade.touch()

    def update(self):
        app=self.app
        active=app.session.phase in ("focus","break")
        strength=self.fade.strength
        if not n.user.IsWindowVisible(app.hwnd) or not active:
            n.user.ShowWindow(self.hwnd,0);return
        remaining=app.session.remaining
        frame_key=(app.player.action,app.player.index)
        if frame_key not in self.top_cache:
            w,h,data=app.player.frame
            top=next((y for y in range(h) if max(data[y*w*4+3:(y+1)*w*4:4],default=0)>=128),0)
            self.top_cache[frame_key]=top
        head=app.y+self.top_cache[frame_key]*app.pixel_scale-app.lift
        area=app.edge.area if app.edge.side else n.work_area(app.x+app.width/2,app.y+app.height/2)
        left,top,right,bottom=area
        self.scale=min(2,max(1,app.dpi/96),(right-left-8)/236,(bottom-top-8)/108)
        width,height=round(236*self.scale),round(108*self.scale)
        centre=max(left+40,min(right-40,app.x+app.width/2))
        x=max(left+4,min(round(centre-width/2),right-width-4))
        y=round(head-height-8)
        if y<top+4:y=min(bottom-height-4,round(app.y+app.height+8))
        key=(remaining,app.session.phase,app.session.paused,round(strength*16),x,y,app.topmost,self.scale)
        if key!=self.last:
            self.painter.surface(remaining,app.session.phase,app.session.paused,strength,self.scale).display(self.hwnd,x,y)
            n.user.SetWindowPos(self.hwnd,n.W.HWND(-1 if app.topmost else -2),0,0,0,0,0x13)
            self.position=(x,y);self.last=key
        n.user.ShowWindow(self.hwnd,4)

    def dispatch(self,hwnd,message,wp,lp):
        try:
            if message==0x21:return 3
            if message in (0x200,0x202) and self.app.session.phase not in ("focus","break"):
                n.user.ShowWindow(hwnd,0);return 0
            if message==0x200:
                self.touch();return 0
            if message==0x202:
                x=C.c_short(lp&0xffff).value;y=C.c_short((lp>>16)&0xffff).value
                x,y=x/self.scale,y/self.scale
                expanded=self.fade.strength>.2
                self.touch()
                if expanded and y>=78:
                    active=self.app.session.phase in ("focus","break")
                    self.app.command((16 if active else 14) if x<145 else (17 if active else 12))
                self.update();return 0
            if message==0x205:
                self.touch();self.app.menu();return 0
        except Exception:logging.exception('Countdown panel event failed')
        return n.user.DefWindowProcW(hwnd,message,wp,lp)

    def close(self):
        if self.hwnd and n.user.IsWindow(self.hwnd):n.user.DestroyWindow(self.hwnd)
        self.painter.close()
        n.user.UnregisterClassW(self.CLASS,self.app.class_instance)
