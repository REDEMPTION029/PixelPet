"""Typed, 64-bit-safe Win32/GDI+ interface. No third-party dependencies."""
import ctypes as C
from ctypes import wintypes as W

PTR = C.c_void_p
UINT_PTR = C.c_size_t
LRESULT = C.c_ssize_t
WNDPROC = C.WINFUNCTYPE(LRESULT, W.HWND, W.UINT, UINT_PTR, LRESULT)


class WNDCLASS(C.Structure):
    _fields_ = [("style", W.UINT), ("lpfnWndProc", WNDPROC), ("cbClsExtra", C.c_int),
                ("cbWndExtra", C.c_int), ("hInstance", W.HINSTANCE), ("hIcon", W.HICON),
                ("hCursor", W.HANDLE), ("hbrBackground", W.HBRUSH),
                ("lpszMenuName", W.LPCWSTR), ("lpszClassName", W.LPCWSTR)]


class MONITORINFO(C.Structure):
    _fields_ = [("cbSize", W.DWORD), ("rcMonitor", W.RECT), ("rcWork", W.RECT), ("dwFlags", W.DWORD)]


class STARTUP(C.Structure):
    _fields_ = [("version", W.UINT), ("callback", PTR), ("no_thread", W.BOOL), ("no_codecs", W.BOOL)]


class BITMAPDATA(C.Structure):
    _fields_ = [("Width", W.UINT), ("Height", W.UINT), ("Stride", C.c_int),
                ("PixelFormat", C.c_int), ("Scan0", PTR), ("Reserved", UINT_PTR)]


class GDIRECT(C.Structure):
    _fields_ = [("X", C.c_int), ("Y", C.c_int), ("Width", C.c_int), ("Height", C.c_int)]


class BITMAPINFO(C.Structure):
    _fields_ = [("biSize", W.DWORD), ("biWidth", W.LONG), ("biHeight", W.LONG),
                ("biPlanes", W.WORD), ("biBitCount", W.WORD), ("biCompression", W.DWORD),
                ("biSizeImage", W.DWORD), ("biXPelsPerMeter", W.LONG),
                ("biYPelsPerMeter", W.LONG), ("biClrUsed", W.DWORD), ("biClrImportant", W.DWORD)]


class BLEND(C.Structure):
    _fields_ = [("BlendOp", W.BYTE), ("BlendFlags", W.BYTE), ("SourceConstantAlpha", W.BYTE), ("AlphaFormat", W.BYTE)]


class GUID(C.Structure):
    _fields_ = [("a", W.DWORD), ("b", W.WORD), ("c", W.WORD), ("d", W.BYTE * 8)]


class NOTIFYICONDATA(C.Structure):
    _fields_ = [("cbSize", W.DWORD), ("hWnd", W.HWND), ("uID", W.UINT),
                ("uFlags", W.UINT), ("uCallbackMessage", W.UINT), ("hIcon", W.HICON),
                ("szTip", W.WCHAR * 128), ("dwState", W.DWORD), ("dwStateMask", W.DWORD),
                ("szInfo", W.WCHAR * 256), ("uVersion", W.UINT), ("szInfoTitle", W.WCHAR * 64),
                ("dwInfoFlags", W.DWORD), ("guidItem", GUID), ("hBalloonIcon", W.HICON)]


user = C.WinDLL("user32", use_last_error=True)
gdi = C.WinDLL("gdi32", use_last_error=True)
kernel = C.WinDLL("kernel32", use_last_error=True)
shell = C.WinDLL("shell32", use_last_error=True)
gdip = C.WinDLL("gdiplus")


def bind(dll, name, result, *args):
    fn = getattr(dll, name)
    fn.restype, fn.argtypes = result, list(args)
    return fn


bind(kernel, "GetModuleHandleW", W.HMODULE, W.LPCWSTR)
bind(kernel, "CreateMutexW", W.HANDLE, PTR, W.BOOL, W.LPCWSTR)
bind(kernel, "CloseHandle", W.BOOL, W.HANDLE)
bind(kernel, "GetCurrentProcess", W.HANDLE)
bind(user, "RegisterClassW", W.ATOM, C.POINTER(WNDCLASS))
bind(user, "UnregisterClassW", W.BOOL, W.LPCWSTR, W.HINSTANCE)
bind(user, "CreateWindowExW", W.HWND, W.DWORD, W.LPCWSTR, W.LPCWSTR, W.DWORD,
     C.c_int, C.c_int, C.c_int, C.c_int, W.HWND, W.HMENU, W.HINSTANCE, PTR)
bind(user, "DefWindowProcW", LRESULT, W.HWND, W.UINT, UINT_PTR, LRESULT)
bind(user, "DestroyWindow", W.BOOL, W.HWND)
bind(user, "IsWindow", W.BOOL, W.HWND)
bind(user, "ShowWindow", W.BOOL, W.HWND, C.c_int)
bind(user, "IsWindowVisible", W.BOOL, W.HWND)
bind(user, "SetWindowPos", W.BOOL, W.HWND, W.HWND, C.c_int, C.c_int, C.c_int, C.c_int, W.UINT)
bind(user, "GetWindowRect", W.BOOL, W.HWND, C.POINTER(W.RECT))
bind(user, "SetWindowTextW", W.BOOL, W.HWND, W.LPCWSTR)
bind(user, "GetMessageW", C.c_int, C.POINTER(W.MSG), W.HWND, W.UINT, W.UINT)
bind(user, "PeekMessageW", W.BOOL, C.POINTER(W.MSG), W.HWND, W.UINT, W.UINT, W.UINT)
bind(user, "TranslateMessage", W.BOOL, C.POINTER(W.MSG))
bind(user, "DispatchMessageW", LRESULT, C.POINTER(W.MSG))
bind(user, "PostQuitMessage", None, C.c_int)
bind(user, "PostMessageW", W.BOOL, W.HWND, W.UINT, UINT_PTR, LRESULT)
bind(user, "SendMessageW", LRESULT, W.HWND, W.UINT, UINT_PTR, LRESULT)
bind(user, "SetTimer", UINT_PTR, W.HWND, UINT_PTR, W.UINT, PTR)
bind(user, "KillTimer", W.BOOL, W.HWND, UINT_PTR)
bind(user, "GetCursorPos", W.BOOL, C.POINTER(W.POINT))
bind(user, "WindowFromPoint", W.HWND, W.POINT)
bind(user, "SetCapture", W.HWND, W.HWND)
bind(user, "ReleaseCapture", W.BOOL)
bind(user, "GetAsyncKeyState", W.SHORT, C.c_int)
bind(user, "GetDC", W.HDC, W.HWND)
bind(user, "ReleaseDC", C.c_int, W.HWND, W.HDC)
bind(user, "UpdateLayeredWindow", W.BOOL, W.HWND, W.HDC, C.POINTER(W.POINT),
     C.POINTER(W.SIZE), W.HDC, C.POINTER(W.POINT), W.DWORD, C.POINTER(BLEND), W.DWORD)
bind(user, "LoadCursorW", W.HANDLE, W.HINSTANCE, PTR)
bind(user, "LoadIconW", W.HICON, W.HINSTANCE, PTR)
bind(user, "LoadImageW", W.HANDLE, W.HINSTANCE, W.LPCWSTR, W.UINT, C.c_int, C.c_int, W.UINT)
bind(user, "GetWindowLongPtrW", LRESULT, W.HWND, C.c_int)
bind(user, "SetWindowRgn", C.c_int, W.HWND, W.HANDLE, W.BOOL)
bind(user, "MessageBeep", W.BOOL, W.UINT)
bind(user, "DestroyIcon", W.BOOL, W.HICON)
bind(user, "CreatePopupMenu", W.HMENU)
bind(user, "AppendMenuW", W.BOOL, W.HMENU, W.UINT, UINT_PTR, W.LPCWSTR)
bind(user, "TrackPopupMenu", W.BOOL, W.HMENU, W.UINT, C.c_int, C.c_int, C.c_int, W.HWND, PTR)
bind(user, "DestroyMenu", W.BOOL, W.HMENU)
bind(user, "SetForegroundWindow", W.BOOL, W.HWND)
bind(user, "MonitorFromPoint", W.HANDLE, W.POINT, W.DWORD)
bind(user, "GetMonitorInfoW", W.BOOL, W.HANDLE, C.POINTER(MONITORINFO))
bind(user, "GetDpiForWindow", W.UINT, W.HWND)
MONITORENUMPROC=C.WINFUNCTYPE(W.BOOL,W.HANDLE,W.HDC,C.POINTER(W.RECT),LRESULT)
bind(user, "EnumDisplayMonitors", W.BOOL, W.HDC, PTR, MONITORENUMPROC, LRESULT)
bind(user, "RegisterWindowMessageW", W.UINT, W.LPCWSTR)
bind(user, "MessageBoxW", C.c_int, W.HWND, W.LPCWSTR, W.LPCWSTR, W.UINT)
bind(user, "GetGuiResources", W.DWORD, W.HANDLE, W.DWORD)
bind(gdi, "CreateCompatibleDC", W.HDC, W.HDC)
bind(gdi, "DeleteDC", W.BOOL, W.HDC)
bind(gdi, "CreateDIBSection", W.HBITMAP, W.HDC, C.POINTER(BITMAPINFO), W.UINT, C.POINTER(PTR), W.HANDLE, W.DWORD)
bind(gdi, "SelectObject", W.HANDLE, W.HDC, W.HANDLE)
bind(gdi, "DeleteObject", W.BOOL, W.HANDLE)
bind(gdi, "GetStockObject", W.HANDLE, C.c_int)
bind(gdi, "CreateRectRgn", W.HANDLE, C.c_int, C.c_int, C.c_int, C.c_int)
bind(gdi, "CreateFontW", W.HFONT, *([C.c_int]*5), *([W.DWORD]*8), W.LPCWSTR)
bind(shell, "Shell_NotifyIconW", W.BOOL, W.DWORD, C.POINTER(NOTIFYICONDATA))
bind(shell, "SetCurrentProcessExplicitAppUserModelID", W.LONG, W.LPCWSTR)
bind(gdip, "GdiplusStartup", C.c_int, C.POINTER(UINT_PTR), C.POINTER(STARTUP), PTR)
bind(gdip, "GdiplusShutdown", None, UINT_PTR)
bind(gdip, "GdipCreateBitmapFromFile", C.c_int, W.LPCWSTR, C.POINTER(PTR))
bind(gdip, "GdipDisposeImage", C.c_int, PTR)
bind(gdip, "GdipGetImageWidth", C.c_int, PTR, C.POINTER(W.UINT))
bind(gdip, "GdipGetImageHeight", C.c_int, PTR, C.POINTER(W.UINT))
bind(gdip, "GdipBitmapLockBits", C.c_int, PTR, C.POINTER(GDIRECT), W.UINT, C.c_int, C.POINTER(BITMAPDATA))
bind(gdip, "GdipBitmapUnlockBits", C.c_int, PTR, C.POINTER(BITMAPDATA))


def checked(value):
    if not value:
        raise C.WinError(C.get_last_error())
    return value


def gdicheck(status):
    if status:
        raise RuntimeError(f"GDI+ returned status {status}")


def work_area(x, y):
    info = MONITORINFO(cbSize=C.sizeof(MONITORINFO))
    checked(user.GetMonitorInfoW(user.MonitorFromPoint(W.POINT(int(x), int(y)), 2), C.byref(info)))
    r = info.rcWork
    return r.left, r.top, r.right, r.bottom


def monitor_layout():
    result=[]
    dpi_query=bind(C.WinDLL('shcore'),'GetDpiForMonitor',W.LONG,W.HANDLE,C.c_int,C.POINTER(W.UINT),C.POINTER(W.UINT))
    @MONITORENUMPROC
    def collect(handle,dc,rect,param):
        info=MONITORINFO(cbSize=C.sizeof(MONITORINFO))
        if not user.GetMonitorInfoW(handle,C.byref(info)):return False
        def bounds(r):return [r.left,r.top,r.right,r.bottom]
        dx,dy=W.UINT(),W.UINT()
        dpi=dx.value if dpi_query(handle,0,C.byref(dx),C.byref(dy))==0 else None
        result.append({'bounds':bounds(info.rcMonitor),'work':bounds(info.rcWork),'primary':bool(info.dwFlags&1),'dpi':dpi})
        return True
    checked(user.EnumDisplayMonitors(None,None,collect,0))
    return result


class Imaging:
    def __init__(self):
        self.token = UINT_PTR()
        gdicheck(gdip.GdiplusStartup(C.byref(self.token), C.byref(STARTUP(1, None, False, False)), None))

    def decode(self, path):
        bitmap = PTR()
        gdicheck(gdip.GdipCreateBitmapFromFile(str(path), C.byref(bitmap)))
        try:
            w, h = W.UINT(), W.UINT()
            gdicheck(gdip.GdipGetImageWidth(bitmap, C.byref(w)))
            gdicheck(gdip.GdipGetImageHeight(bitmap, C.byref(h)))
            data = BITMAPDATA()
            rect = GDIRECT(0, 0, w.value, h.value)
            gdicheck(gdip.GdipBitmapLockBits(bitmap, C.byref(rect), 1, 0xE200B, C.byref(data)))
            try:
                pixels = b"".join(C.string_at(data.Scan0 + y * data.Stride, w.value * 4) for y in range(h.value))
            finally:
                gdicheck(gdip.GdipBitmapUnlockBits(bitmap, C.byref(data)))
            return w.value, h.value, pixels
        finally:
            gdip.GdipDisposeImage(bitmap)

    def close(self):
        if self.token.value:
            gdip.GdiplusShutdown(self.token)
            self.token.value = 0


class Surface:
    """A top-down premultiplied BGRA DIB, owning its GDI handles."""
    def __init__(self, width, height, pixels):
        self.width, self.height = width, height
        self.dc = checked(gdi.CreateCompatibleDC(None))
        self.bitmap = self.old = None
        try:
            info = BITMAPINFO(biSize=C.sizeof(BITMAPINFO), biWidth=width, biHeight=-height,
                              biPlanes=1, biBitCount=32)
            pointer = PTR()
            self.bitmap = checked(gdi.CreateDIBSection(self.dc, C.byref(info), 0, C.byref(pointer), None, 0))
            self.old = checked(gdi.SelectObject(self.dc, self.bitmap))
            self.bits = pointer.value
            C.memmove(pointer, pixels, len(pixels))
        except Exception:
            self.close()
            raise

    def display(self, hwnd, x, y):
        pos, size, origin, blend = W.POINT(round(x), round(y)), W.SIZE(self.width, self.height), W.POINT(), BLEND(0, 0, 255, 1)
        checked(user.UpdateLayeredWindow(hwnd, None, C.byref(pos), C.byref(size), self.dc,
                                        C.byref(origin), 0, C.byref(blend), 2))

    def close(self):
        if self.old:
            gdi.SelectObject(self.dc, self.old)
            self.old = None
        if self.bitmap:
            gdi.DeleteObject(self.bitmap)
            self.bitmap = None
        if self.dc:
            gdi.DeleteDC(self.dc)
            self.dc = None
        self.bits = None
