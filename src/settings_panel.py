"""Small native Win32 settings window, sharing the application's message loop."""
import ctypes as C
import logging
from . import native_api as n


class SettingsPanel:
    CLASS = "PixelPetSettingsV1"

    def __init__(self, app):
        self.app, self.hwnd = app, None
        self.controls = {}
        self.rects={}
        self.factor=1
        self.font=None
        self.callback = n.WNDPROC(self.dispatch)
        self.definition = n.WNDCLASS(lpfnWndProc=self.callback, hInstance=app.class_instance,
            hIcon=app.icon_big, hCursor=n.user.LoadCursorW(None, C.c_void_p(32512)),
            hbrBackground=n.W.HBRUSH(16), lpszClassName=self.CLASS)
        n.checked(n.user.RegisterClassW(C.byref(self.definition)))

    def control(self, cls, text, style, x, y, w, h, identifier):
        self.rects[identifier]=(x,y,w,h)
        x,y,w,h=[round(v*self.factor) for v in (x,y,w,h)]
        handle = n.checked(n.user.CreateWindowExW(0, cls, text, 0x50000000 | style,
            x, y, w, h, self.hwnd, n.W.HMENU(identifier), self.app.class_instance, None))
        n.user.SendMessageW(handle, 0x30, self.font or self.app.ui_font or n.gdi.GetStockObject(17), 1)
        self.controls[identifier] = handle
        return handle

    def layout(self,area,dpi,x=None,y=None):
        left,top,right,bottom=area
        factor=min(2,max(1,dpi/96),(right-left-16)/410,(bottom-top-16)/540)
        if not self.font or abs(factor-self.factor)>.001:
            previous=self.font
            self.factor=factor
            self.font=n.checked(n.gdi.CreateFontW(-round(17*factor),0,0,0,400,0,0,0,1,0,0,4,0,'YouYuan'))
            for i,handle in self.controls.items():
                n.user.SendMessageW(handle,0x30,self.font,1)
                rect=[round(v*factor) for v in self.rects[i]]
                n.user.SetWindowPos(handle,None,*rect,0x14)
            if previous:n.gdi.DeleteObject(previous)
        if self.hwnd:
            w,h=round(410*factor),round(540*factor)
            x=(left+right-w)//2 if x is None else max(left,min(x,right-w))
            y=(top+bottom-h)//2 if y is None else max(top,min(y,bottom-h))
            n.user.SetWindowPos(self.hwnd,None,x,y,w,h,0x14)

    def show(self):
        area=n.work_area(self.app.x,self.app.y)
        self.layout(area,self.app.dpi)
        if not self.hwnd:
            left, top, right, bottom = n.work_area(self.app.x, self.app.y)
            self.hwnd = n.checked(n.user.CreateWindowExW(0, self.CLASS, "PixelPet · 陪伴设置", 0x80C80000,
                (left + right - 410) // 2, (top + bottom - 540) // 2, 410, 540,
                self.app.hwnd, None, self.app.class_instance, None))
            self.control("STATIC", "日常陪伴", 0, 24, 18, 320, 24, 1)
            for identifier, label, y in ((10, "自动散步", 52), (11, "自动闲聊气泡", 84),
                                         (12, "闲置三分钟后打盹", 116), (13, "始终置顶", 148),
                                         (14, "松手后惯性滑动", 180), (15, "左右边缘收起探头", 212),
                                         (16, "计时完成提示音", 244)):
                self.control("BUTTON", label, 3 | 0x10000, 24, y, 350, 26, identifier)
            for identifier, values, y in ((20, [f"{i}%" for i in range(50, 201, 25)], 286),
                                           (21, ["较多 · 45 秒", "适中 · 75 秒", "安静 · 150 秒"], 324),
                                           (22, [f"{i} 分钟" for i in (15,25,45,60)], 362),
                                           (23, [f"{i} 分钟" for i in (5,10,15)], 400)):
                self.control("STATIC", {20:"人物大小",21:"闲聊频率",22:"下轮专注",23:"下轮休息"}[identifier], 0,
                             24, y + 4, 100, 24, identifier+10)
                box = self.control("COMBOBOX", "", 0x00210003, 134, y, 235, 180, identifier)
                for value in values:
                    text = C.c_wchar_p(value)
                    n.user.SendMessageW(box, 0x143, 0, C.cast(text, C.c_void_p).value)
            self.control("BUTTON", "保存", 0x10001, 190, 452, 85, 30, 100)
            self.control("BUTTON", "取消", 0x10000, 285, 452, 85, 30, 101)
        self.layout(area,self.app.dpi)
        for identifier, value in ((10, self.app.auto_move), (11, self.app.idle_chat),
                                   (12, self.app.auto_sleep), (13, self.app.topmost),
                                   (14,self.app.drag_inertia),(15,self.app.edge_peek),(16,self.app.clock_sound)):
            n.user.SendMessageW(self.controls[identifier], 0xF1, int(value), 0)
        n.user.SendMessageW(self.controls[20], 0x14E, round((self.app.scale - .5) / .25), 0)
        n.user.SendMessageW(self.controls[21], 0x14E, (45, 75, 150).index(self.app.chat_interval), 0)
        n.user.SendMessageW(self.controls[22], 0x14E, (15,25,45,60).index(self.app.focus_minutes), 0)
        n.user.SendMessageW(self.controls[23], 0x14E, (5,10,15).index(self.app.break_minutes), 0)
        n.user.ShowWindow(self.hwnd, 5)
        n.user.SetForegroundWindow(self.hwnd)

    def dispatch(self, hwnd, message, wp, lp):
        try:
            if message==0x2E0 and lp:
                rect=C.cast(lp,C.POINTER(n.W.RECT)).contents
                self.layout(n.work_area(rect.left,rect.top),wp&0xffff,rect.left,rect.top)
                return 0
            if message == 0x10:
                n.user.ShowWindow(hwnd, 0)
                return 0
            if message == 0x111:
                command = wp & 0xFFFF
                if command == 100:
                    values = {key: n.user.SendMessageW(self.controls[i], 0xF0, 0, 0) == 1
                              for i, key in ((10, "auto_move"), (11, "idle_chat"), (12, "auto_sleep"), (13, "topmost"),
                                             (14,"drag_inertia"),(15,"edge_peek"),(16,"clock_sound"))}
                    size = n.user.SendMessageW(self.controls[20], 0x147, 0, 0)
                    frequency = n.user.SendMessageW(self.controls[21], 0x147, 0, 0)
                    focus=n.user.SendMessageW(self.controls[22],0x147,0,0)
                    rest=n.user.SendMessageW(self.controls[23],0x147,0,0)
                    if size not in range(7) or frequency not in range(3) or focus not in range(4) or rest not in range(3):
                        return 0
                    values.update(scale=.5 + size * .25, chat_interval=(45, 75, 150)[frequency],
                                  focus_minutes=(15,25,45,60)[focus],break_minutes=(5,10,15)[rest])
                    self.app.apply_settings(values)
                    n.user.ShowWindow(hwnd, 0)
                    return 0
                if command == 101:
                    n.user.ShowWindow(hwnd, 0)
                    return 0
            if message == 2:
                self.hwnd = None
        except Exception:
            logging.exception("Settings window event failed")
        return n.user.DefWindowProcW(hwnd, message, wp, lp)

    def close(self):
        if self.hwnd and n.user.IsWindow(self.hwnd):
            n.user.DestroyWindow(self.hwnd)
        n.user.UnregisterClassW(self.CLASS, self.app.class_instance)
        if self.font:n.gdi.DeleteObject(self.font);self.font=None
