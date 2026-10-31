"""Windows desktop pet: layered window, native menus and tray, no Qt."""
import ctypes as C
from ctypes import wintypes as W
import logging
import math
import random
import time

from . import native_api as n
from .native_model import ROOT, Library, Player, SurfaceCache, load_config, save_config, validate_config, load_session, save_session
from . import speech
from .behavior import Director, FocusSession
from .desktop_state import DragInertia, EdgeDock, horizontal_clip, mirrored_for, inward_direction, fitted_scale, clamped_position, dragged_position

TITLE = "PixelPet · 原生桌宠"
CLASS_NAME = "PixelPetNativeWindowV1"
TRAY_MESSAGE = 0x8001
DISPLAY_UPDATE = 0x8002
log = logging.getLogger(__name__)


class PetApp:
    def __init__(self, test_mode=False, preview=False):
        self.test_mode = test_mode
        self.imaging = n.Imaging()
        self.cache = SurfaceCache(n.Surface)
        self.hwnd = self.bubble = self.tray = None
        self.icon_big = self.icon_small = None
        self.registered = False
        self.closing = False
        self.running = False
        self.menu_open = False
        self.settings = None
        self.overlay = None
        self.ui_font = None
        self.edge = EdgeDock()
        self.inertia = DragInertia()
        self.clip_key = None
        self.lift = 0.0
        self.dpi=96
        self.pixel_scale=.5
        self.displays=n.monitor_layout()
        self.drag_area=None
        self.pending_display=None
        self.drag_last_x = 0
        self.class_instance = n.kernel.GetModuleHandleW(None)
        self.callback = n.WNDPROC(self._dispatch)
        self.class_definition = n.WNDCLASS(style=8, lpfnWndProc=self.callback,
            hInstance=self.class_instance, hCursor=n.user.LoadCursorW(None, C.c_void_p(32512)),
            lpszClassName=CLASS_NAME)
        try:
            icon = str(ROOT / "assets/app.ico")
            self.icon_big = n.checked(n.user.LoadImageW(None, icon, 1, 48, 48, 0x10))
            self.icon_small = n.checked(n.user.LoadImageW(None, icon, 1, 16, 16, 0x10))
            self.class_definition.hIcon = self.icon_big
            self.library = Library(self.imaging)
            self.player = Player(self.library)
            self.director = Director(self.player)
            self.session = FocusSession()
            self.restored_session=load_session(self.session) if not test_mode else False
            self.last_session_save=time.monotonic()
            self.config = load_config() if not test_mode else validate_config({})
            self.scale = self.config["scale"]
            self.auto_move, self.topmost = self.config["auto_move"], self.config["topmost"]
            self.idle_chat, self.auto_sleep = self.config["idle_chat"], self.config["auto_sleep"]
            self.chat_interval = self.config["chat_interval"]
            self.edge_peek,self.clock_sound = self.config["edge_peek"],self.config["clock_sound"]
            self.drag_inertia=self.config["drag_inertia"]
            self.focus_minutes,self.break_minutes=self.config["focus_minutes"],self.config["break_minutes"]
            self.wake_click = False
            self.pending_notice = None
            self.tray_label = ""
            self.flip = False
            self.canvas_w, self.canvas_h = self.library.canvas
            self.width, self.height = round(self.canvas_w * self.scale), round(self.canvas_h * self.scale)
            self.x = self.config["x"]
            self.y = self.config["y"]
            if self.x is None or self.y is None:
                left, top, right, bottom = n.work_area(0, 0)
                self.x, self.y = right - self.width - 100, bottom - self.height - 30
            self.pressed = None
            self.dragging = False
            self.suppress_click = False
            self.target = None
            now = time.monotonic()
            self.last_tick = self.last_interact = now
            self.next_walk = now + 8
            self.next_speech = now + random.uniform(45, 75)
            self.bubble_until = 0
            self.last_render = None
            self.taskbar_message = n.user.RegisterWindowMessageW("TaskbarCreated")
            n.checked(n.user.RegisterClassW(C.byref(self.class_definition)))
            self.registered = True
            extended = 0x80000 | 0x40000 | 0x08000000  # layered + taskbar + no focus stealing
            if self.topmost:
                extended |= 8
            self.hwnd = n.checked(n.user.CreateWindowExW(extended, CLASS_NAME, TITLE + (" · Preview" if preview else ""), 0x80000000,
                round(self.x), round(self.y), self.width, self.height, None, None, self.class_instance, None))
            n.user.SendMessageW(self.hwnd, 0x80, 1, self.icon_big)
            n.user.SendMessageW(self.hwnd, 0x80, 0, self.icon_small)
            self.bubble = n.checked(n.user.CreateWindowExW(0x80 | 0x08000000 | (8 if self.topmost else 0),
                "STATIC", "", 0x80000000 | 0x00800000 | 0x201, 0, 0, 250, 42,
                self.hwnd, None, self.class_instance, None))
            self.ui_font=n.checked(n.gdi.CreateFontW(-17,0,0,0,400,0,0,0,1,0,0,4,0,"YouYuan"))
            n.user.SendMessageW(self.bubble, 0x30, self.ui_font, 1)
            from .focus_overlay import FocusOverlay
            self.overlay=FocusOverlay(self)
            self.dpi=n.user.GetDpiForWindow(self.hwnd) or 96
            self.clamp()
            self.render(force=True)
            n.checked(n.user.SetTimer(self.hwnd, 1, 33, None))
        except Exception:
            self.close()
            raise

    def clamp(self,area=None):
        if self.edge.side:
            left,top,right,bottom=self.edge.area
            self.y=max(top,min(self.y,max(top,bottom-self.height)))
            return
        left, top, right, bottom = area or self.drag_area or n.work_area(self.x + self.width / 2, self.y + self.height / 2)
        area=(left,top,right,bottom)
        self.pixel_scale=round(fitted_scale(self.scale,area,self.dpi),6)
        self.width,self.height=round(self.canvas_w*self.pixel_scale),round(self.canvas_h*self.pixel_scale)
        if self.dragging:
            self.x,self.y=dragged_position(self.x,self.y,self.width,self.height,area,[m['work'] for m in self.displays])
        else:self.x,self.y=clamped_position(self.x,self.y,self.width,self.height,area)

    def render(self, force=False):
        ax, ay = self.player.anchor
        if self.flip:
            ax = self.canvas_w - ax
        rx = self.x + (256 - ax) * self.pixel_scale
        ry = self.y + (496 - ay) * self.pixel_scale - self.lift
        key = (self.player.action, self.player.index, self.pixel_scale, self.flip, round(rx), round(ry))
        if force or key != self.last_render:
            self.cache.get(self.player, self.pixel_scale, self.flip).display(self.hwnd, rx, ry)
            self.last_render = key
        if self.edge.side:
            l,r=horizontal_clip(rx,self.width,self.edge.area)
            clip=(l,r,self.height)
            if clip!=self.clip_key:
                region=n.checked(n.gdi.CreateRectRgn(l,0,max(l+1,r),self.height))
                if not n.user.SetWindowRgn(self.hwnd,region,True):
                    n.gdi.DeleteObject(region)
                    raise C.WinError(C.get_last_error())
                self.clip_key=clip
        elif self.clip_key is not None:
            n.user.SetWindowRgn(self.hwnd,None,True);self.clip_key=None
        if self.bubble_until:
            self.position_bubble()
        if self.overlay:
            self.overlay.update()

    def position_bubble(self):
        left, top, right, bottom = n.work_area(self.x + self.width / 2, self.y)
        w, h = 250, 42
        x = max(left, min(round(self.x + self.width / 2 - w / 2), right - w))
        y = round(self.y - h - 10)
        if self.overlay and n.user.IsWindowVisible(self.overlay.hwnd):
            y=self.overlay.position[1]-h-6
        if y < top:
            y = min(bottom - h, round(self.y + self.height + 8))
        n.user.SetWindowPos(self.bubble, W.HWND(-1 if self.topmost else -2), x, y, w, h, 0x10)

    def say(self, text):
        self.bubble_until = time.monotonic() + 4
        n.user.SetWindowTextW(self.bubble, text)
        self.position_bubble()
        n.user.ShowWindow(self.bubble, 4)

    def play(self, action, once=False, priority=Director.USER, force=False):
        if self.edge.side and action!="peek":
            self.undock()
        accepted = self.director.request(action, priority, once, force)
        if not accepted:
            return False
        if action!="dragRun":self.inertia.stop()
        self.target = None
        self.next_walk = time.monotonic() + random.uniform(6, 12)
        self.render()
        return True

    def interact(self):
        self.last_interact = time.monotonic()
        if self.overlay:self.overlay.touch()
        if self.player.action in ("sleep", "sleepEnter"):
            self.play("idle", priority=Director.SESSION)

    def start_walk(self, automatic=False):
        if self.session.quiet or self.edge.side or self.dragging or self.inertia.active:
            return False
        left, _, right, _ = n.work_area(self.x + self.width / 2, self.y)
        low, high = left + 8, right - self.width - 8
        if high <= low:
            return
        choices = [max(low, min(high, self.x + d)) for d in (-180, -100, 100, 180)]
        choices = [x for x in choices if abs(x - self.x) > 20]
        if not choices:
            return
        if not self.director.request("walk", Director.AUTO if automatic else Director.USER):
            return False
        self.target = random.choice(choices)
        self.flip = mirrored_for("right" if self.target > self.x else "left",self.library.meta["walk"].get("base_facing","left"))
        return True

    def undock(self):
        if not self.edge.side:return
        direction=inward_direction(self.edge.side)
        restore=self.edge.clear()
        if restore:self.x,self.y=restore
        self.lift=0
        self.director.request("idle",Director.DRAG,force=True)
        self.flip=mirrored_for(direction,self.library.meta["idle"].get("base_facing","left"))
        self.clamp()
        self.render(force=True)

    def dock_if_near_edge(self):
        area=n.work_area(self.x+self.width/2,self.y+self.height/2)
        side=EdgeDock.choose(self.x,self.width,area) if self.edge_peek else None
        if not side:return False
        self.inertia.stop()
        self.edge.begin(side,area,self.x,self.y,self.width,self.pixel_scale)
        self.lift=0
        self.target=None
        self.flip=mirrored_for(inward_direction(side),self.library.meta["peek"]["base_facing"])
        self.director.request("peek",Director.DRAG,force=True)
        self.render(force=True)
        return True

    def recover_display(self,dpi=None,suggested=None):
        keep_drag=bool(dpi and self.dragging)
        self.inertia.stop()
        if not keep_drag:
            self.pressed=None
            self.dragging=False
            n.user.ReleaseCapture()
        if self.edge.side:self.undock()
        self.dpi=max(96,min(384,dpi or n.user.GetDpiForWindow(self.hwnd) or self.dpi))
        self.displays=n.monitor_layout()
        self.drag_area=None
        if suggested:self.x,self.y=suggested.left,suggested.top
        self.target=None
        if self.player.action in ('walk','walkEnter','walkExit','dragRun') and not keep_drag:
            self.director.request('idle',Director.DRAG,force=True)
        self.cache.clear()
        self.clamp()
        if keep_drag:
            p=W.POINT()
            n.user.GetCursorPos(C.byref(p))
            self.pressed=(p.x,p.y,self.x,self.y)
            self.drag_last_x=p.x
            self.inertia.begin(self.x,self.y)
        self.render(force=True)
        self.persist()

    def drag_to(self,cursor_x,cursor_y):
        if not self.pressed:return
        px,py,x,y=self.pressed
        if not self.dragging and abs(cursor_x-px)+abs(cursor_y-py)<=5:return
        if not self.dragging:
            self.play("dragRun",priority=Director.DRAG,force=True)
            self.dragging=True
            self.lift=0
            self.drag_last_x=px
        dx=cursor_x-self.drag_last_x
        if abs(dx)>2:
            self.flip=mirrored_for("right" if dx>0 else "left",self.library.meta["dragRun"]["base_facing"])
            # Keep sub-threshold motion until it accumulates, so slow drags also turn.
            self.drag_last_x=cursor_x
        self.x,self.y=x+cursor_x-px,y+cursor_y-py
        self.drag_area=n.work_area(cursor_x,cursor_y)
        self.clamp()
        self.inertia.sample(self.x,self.y)
        self.overlay.touch()
        self.render()

    def finish_drag(self,allow_dock=True):
        was_dragging=self.dragging
        self.pressed,self.dragging=None,False
        n.user.ReleaseCapture()
        if was_dragging:
            self.clamp()
            self.drag_area=None
            if allow_dock and self.dock_if_near_edge():
                pass
            elif allow_dock and self.drag_inertia and self.inertia.release():
                self.target=None
                if abs(self.inertia.vx)>35:
                    self.flip=mirrored_for("right" if self.inertia.vx>0 else "left",self.library.meta["dragRun"]["base_facing"])
                self.render(force=True)
            else:
                self.inertia.stop()
                self.director.request("idle",Director.DRAG,force=True)
                self.render(force=True)
            self.persist()
        return was_dragging

    def advance_inertia(self,dt):
        if not self.inertia.active:return
        dx,dy=self.inertia.advance(dt)
        desired_x,desired_y=self.x+dx,self.y+dy
        self.x,self.y=desired_x,desired_y
        self.clamp()
        if abs(self.x-desired_x)>.01:self.inertia.vx=0
        if abs(self.y-desired_y)>.01:self.inertia.vy=0
        if self.dock_if_near_edge():
            self.persist()
        elif not self.inertia.active:
            self.director.request("idle",Director.DRAG,force=True)
            self.next_walk=time.monotonic()+8
            self.persist()

    def tick(self):
        now = time.monotonic()
        dt, self.last_tick = min(0.25, now - self.last_tick), now
        event = self.session.poll()
        if event:
            self.pending_notice = event
            if self.overlay:self.overlay.touch()
            if self.clock_sound:n.user.MessageBeep(0x40)
            self.save_progress()
        elif now-self.last_session_save>=15:
            self.save_progress()
        self.update_tray()
        if self.edge.side:
            self.x=self.edge.advance(dt)
        if not self.dragging:self.lift=max(0,self.lift-dt*60)
        if self.overlay:self.overlay.update()
        if self.bubble_until and now > self.bubble_until:
            self.bubble_until = 0
            n.user.ShowWindow(self.bubble, 0)
        if not n.user.IsWindowVisible(self.hwnd):
            return
        if self.menu_open:
            return
        if self.pressed:
            # Native menus/capture can consume the release message; never get stuck dragging.
            if not (n.user.GetAsyncKeyState(1) & 0x8000):
                self.finish_drag()
            else:
                if self.dragging:
                    self.director.advance(dt)
                    self.render()
                return
        self.advance_inertia(dt)
        finished = self.director.advance(dt)
        if finished:
            self.next_walk = now + random.uniform(6, 12)
        if self.target is not None and self.player.action == "walk":
            delta = self.target - self.x
            walk = self.library.meta["walk"]
            cycle_ms = sum(walk.get("frame_durations_ms", [walk["duration_ms"]] * len(self.library.frames["walk"])))
            step = walk.get("cycle_distance", 80) * self.pixel_scale * dt / (cycle_ms / 1000)
            if abs(delta) <= step:
                self.x = self.target
                self.target = None
                self.director.request("idle", Director.SESSION, now=now)
                self.next_walk = now + random.uniform(5, 12)
                self.persist()
            else:
                self.x += math.copysign(step, delta)
            self.clamp()
        if self.pending_notice and not self.director.protected and self.player.action not in ("sleep", "sleepEnter", "sleepExit"):
            self.say(speech.line(self.pending_notice))
            if self.pending_notice == "focus_done":
                self.play("happy", once=True, priority=Director.SESSION)
            self.pending_notice = None
            self.last_interact = now
        if self.player.action == "idle" and self.auto_move and not self.session.quiet and now >= self.next_walk:
            self.start_walk(automatic=True)
        if self.player.action == "idle" and self.auto_sleep and self.session.phase not in ("focus", "break") and now - self.last_interact > 180:
            self.play("sleep", priority=Director.AUTO)
        if now >= self.next_speech and self.player.action == "idle" and self.idle_chat and not self.session.quiet:
            self.say(speech.random_idle())
            self.next_speech = now + random.uniform(self.chat_interval * .8, self.chat_interval * 1.2)
        self.render()

    def set_scale(self, value):
        value = max(0.5, min(2.0, round(value * 4) / 4))
        if value == self.scale:
            return
        if self.dragging:self.finish_drag(allow_dock=False)
        elif self.pressed:
            self.pressed=None
            n.user.ReleaseCapture()
        if self.inertia.active:
            self.inertia.stop()
            self.director.request("idle",Director.DRAG,force=True)
        if self.edge.side:self.undock()
        foot_x, foot_y = self.x + self.width / 2, self.y + self.height
        self.scale = value
        area=n.work_area(foot_x,foot_y)
        self.pixel_scale=round(fitted_scale(value,area,self.dpi),6)
        self.width, self.height = round(self.canvas_w * self.pixel_scale), round(self.canvas_h * self.pixel_scale)
        self.x, self.y = foot_x - self.width / 2, foot_y - self.height
        if self.target is not None:
            self.target = None
            self.director.request("idle", Director.USER, force=True)
        self.clamp()
        self.cache.clear()
        self.render(force=True)
        self.persist()
        self.say(f"当前大小：{int(value * 100)}%")

    def persist(self):
        if self.test_mode:
            return
        try:
            position=self.edge.restore if self.edge.side else (self.x,self.y)
            save_config(dict(x=round(position[0]), y=round(position[1]), scale=self.scale,
                             topmost=self.topmost, auto_move=self.auto_move, idle_chat=self.idle_chat,
                             auto_sleep=self.auto_sleep, chat_interval=self.chat_interval,
                             edge_peek=self.edge_peek,clock_sound=self.clock_sound,
                             drag_inertia=self.drag_inertia,focus_minutes=self.focus_minutes,break_minutes=self.break_minutes))
        except OSError:
            log.exception("Cannot save settings")

    def save_progress(self):
        self.last_session_save=time.monotonic()
        if self.test_mode:return
        try:save_session(self.session)
        except OSError:log.exception("Cannot save focus progress")

    def toggle_visible(self):
        if n.user.IsWindowVisible(self.hwnd):
            if self.inertia.active:
                self.inertia.stop()
                self.director.request("idle",Director.DRAG,force=True)
            n.user.ShowWindow(self.hwnd, 0)
            n.user.ShowWindow(self.bubble, 0)
            self.bubble_until = 0
            if self.overlay:n.user.ShowWindow(self.overlay.hwnd,0)
            self.cache.clear()
            n.user.SetTimer(self.hwnd,1,1000,None)
        else:
            n.user.ShowWindow(self.hwnd, 4)
            n.user.SetTimer(self.hwnd,1,33,None)
            self.last_tick=time.monotonic()
            self.interact()
            self.render(force=True)

    def add_tray(self):
        data = n.NOTIFYICONDATA(cbSize=C.sizeof(n.NOTIFYICONDATA), hWnd=self.hwnd,
            uID=1, uFlags=1 | 2 | 4, uCallbackMessage=TRAY_MESSAGE,
            hIcon=self.icon_small, szTip="PixelPet · 右键打开菜单")
        if n.shell.Shell_NotifyIconW(0, C.byref(data)):
            self.tray = data
        else:
            log.warning("System tray unavailable; use pet right-click menu")

    def update_tray(self):
        label = self.session.label
        if self.tray and label != self.tray_label:
            self.tray.szTip = f"PixelPet · {label}"[:127]
            old = self.tray.uFlags
            self.tray.uFlags = 4
            n.shell.Shell_NotifyIconW(1, C.byref(self.tray))
            self.tray.uFlags = old
            self.tray_label = label

    def begin_focus(self, minutes=None):
        self.pending_notice=None
        self.session.start(self.focus_minutes if minutes is None else minutes,self.break_minutes)
        self.save_progress()
        self.play("adjustGlasses", once=True, priority=Director.SESSION)
        self.say(speech.line("focus_start"))
        self.last_interact = time.monotonic()
        self.overlay.touch();self.overlay.update()

    def apply_settings(self, values):
        self.auto_move, self.idle_chat = values["auto_move"], values["idle_chat"]
        self.auto_sleep, self.chat_interval = values["auto_sleep"], values["chat_interval"]
        self.topmost = values["topmost"]
        self.edge_peek=values["edge_peek"]
        self.clock_sound=values["clock_sound"]
        self.drag_inertia=values["drag_inertia"]
        self.focus_minutes,self.break_minutes=values["focus_minutes"],values["break_minutes"]
        if not self.edge_peek:self.undock()
        if not self.drag_inertia and self.inertia.active:
            self.inertia.stop()
            self.director.request("idle",Director.DRAG,force=True)
        for hwnd in (self.hwnd, self.bubble):
            n.user.SetWindowPos(hwnd, W.HWND(-1 if self.topmost else -2), 0, 0, 0, 0, 0x13)
        if not self.auto_move and self.player.action in ("walk", "walkEnter"):
            self.play("idle", priority=Director.SESSION)
        self.set_scale(values["scale"])
        self.next_speech = time.monotonic() + self.chat_interval
        self.persist()
        self.say("陪伴设置已保存。")

    def menu(self):
        self.last_interact = time.monotonic()
        if self.inertia.active:
            self.inertia.stop()
            self.director.request("idle",Director.DRAG,force=True)
            self.persist()
        if self.dragging:self.finish_drag(allow_dock=False)
        else:
            self.pressed=None;n.user.ReleaseCapture()
        self.overlay.touch()
        menu = n.checked(n.user.CreatePopupMenu())
        self.menu_open = True
        try:
            items = [(1, "显示 / 隐藏"), (12, "陪伴设置…"), (0, ""), (13, self.session.label),
                     (14, f"开始专注 · {self.focus_minutes} 分钟"), (15, "短时专注 · 5 分钟"),
                     (16, "暂停 / 继续计时"), (17, "结束本轮计时"), (21,"时钟提示音"), (18, "扶眼镜"), (0, ""),
                     (2, "说句话"), (3, "开心跳跃"),
                     (4, "睡觉 / 唤醒"), (5, "走一小段"), (0, ""),
                     (6, "自动散步"), (7, "总在最前"), (19,"边缘探头"), (20,"回到桌面"), (0, ""),
                     (8, "放大 (+25%)"), (9, "缩小 (-25%)"),
                     (10, "恢复默认大小 (50%)"), (0, ""), (11, "退出桌宠")]
            for command, label in items:
                flags = 0x800 if command == 0 else 0
                if (command == 6 and self.auto_move) or (command == 7 and self.topmost):
                    flags |= 8
                if (command==19 and self.edge_peek) or (command==21 and self.clock_sound):flags|=8
                if command==20 and not self.edge.side:flags|=1
                if (command == 8 and self.scale >= 2) or (command == 9 and self.scale <= 0.5):
                    flags |= 1
                if command == 13 or (command in (16, 17) and self.session.phase not in ("focus", "break")):
                    flags |= 1
                n.checked(n.user.AppendMenuW(menu, flags, command, label))
            cursor = W.POINT()
            n.user.GetCursorPos(C.byref(cursor))
            n.user.SetForegroundWindow(self.hwnd)
            command = n.user.TrackPopupMenu(menu, 0x100 | 2, cursor.x, cursor.y, 0, self.hwnd, None)
            n.user.PostMessageW(self.hwnd, 0, 0, 0)
        finally:
            n.user.DestroyMenu(menu)
            self.menu_open = False
            self.last_tick = time.monotonic()
        if command:
            self.command(command)

    def command(self, command):
        if command == 1:
            self.toggle_visible()
        elif command == 2:
            self.say(speech.random_idle())
        elif command == 3:
            self.play("happy", once=True)
        elif command == 4:
            self.play("idle" if self.player.action in ("sleep", "sleepEnter") else "sleep", priority=Director.SESSION)
        elif command == 5:
            self.start_walk()
        elif command == 6:
            self.auto_move = not self.auto_move
            if not self.auto_move and self.player.action in ("walk","walkEnter"):
                self.play("idle",priority=Director.SESSION)
            self.next_walk = time.monotonic() + 2
            self.persist()
        elif command == 7:
            self.topmost = not self.topmost
            for hwnd in (self.hwnd, self.bubble):
                n.user.SetWindowPos(hwnd, W.HWND(-1 if self.topmost else -2), 0, 0, 0, 0, 0x13)
            self.persist()
        elif command in (8, 9, 10):
            self.set_scale(self.scale + (0.25 if command == 8 else -0.25) if command != 10 else 0.5)
        elif command == 11:
            n.user.DestroyWindow(self.hwnd)
        elif command == 12:
            if not self.settings:
                from .settings_panel import SettingsPanel
                self.settings = SettingsPanel(self)
            self.settings.show()
        elif command in (14, 15):
            self.begin_focus(None if command == 14 else 5)
        elif command == 16:
            self.session.pause_resume()
            self.save_progress()
            self.say(speech.line("paused" if self.session.paused else "resumed"))
        elif command == 17:
            self.session.stop()
            self.save_progress()
            self.overlay.update()
            self.pending_notice = None
            if self.director.pending and self.director.pending[0] == "adjustGlasses":
                self.director.pending = None
            self.say(speech.line("stopped"))
            self.last_interact = time.monotonic()
        elif command == 18:
            self.play("adjustGlasses", once=True)
        elif command==19:
            self.edge_peek=not self.edge_peek
            if not self.edge_peek:self.undock()
            self.persist()
        elif command==20:self.undock()
        elif command==21:
            self.clock_sound=not self.clock_sound;self.persist()

    def _dispatch(self, hwnd, message, wp, lp):
        try:
            return self._message(hwnd, message, wp, lp)
        except Exception:
            log.exception("Window event failed: %s", hex(message))
            # Stop a repeating failure instead of logging the same error on every timer tick.
            if message == 0x113:
                n.user.KillTimer(hwnd, 1)
                n.user.PostMessageW(hwnd, 0x10, 0, 0)
            return n.user.DefWindowProcW(hwnd, message, wp, lp)

    def _message(self, hwnd, message, wp, lp):
        if message == 0x14:  # erase background: layered DIB supplies all pixels
            return 1
        if message == 0x21:
            return 3  # MA_NOACTIVATE
        if message == 0x113 and self.hwnd:
            self.tick()
            return 0
        if message == 0x201:  # mouse down
            if self.inertia.active:
                self.inertia.stop()
                self.director.request("idle",Director.DRAG,force=True)
            if self.edge.side:self.undock()
            self.wake_click = self.player.action in ("sleep", "sleepEnter", "sleepExit")
            self.interact()
            p = W.POINT()
            n.user.GetCursorPos(C.byref(p))
            self.pressed = (p.x, p.y, self.x, self.y)
            self.drag_last_x=p.x
            self.inertia.begin(self.x,self.y)
            self.dragging = False
            n.user.SetCapture(hwnd)
            return 0
        if message == 0x200 and self.pressed:
            p = W.POINT()
            n.user.GetCursorPos(C.byref(p))
            self.drag_to(p.x,p.y)
            return 0
        if message == 0x202 and self.pressed:
            was_dragging = self.dragging
            self.finish_drag()
            if not was_dragging and self.wake_click:
                self.say(speech.line("wake"))
            elif not was_dragging and not self.suppress_click:
                y = C.c_short((lp >> 16) & 0xffff).value
                head = y < self.height * 0.55
                self.play("headClick" if head else "bodyClick", once=True)
                self.say(random.choice(speech.HEAD_LINES if head else speech.BODY_LINES))
            self.suppress_click = False
            self.next_walk = time.monotonic() + 8
            self.persist()
            return 0
        if message == 0x203:  # double click
            self.pressed = None
            self.suppress_click = False
            n.user.ReleaseCapture()
            self.play("happy", once=True, priority=Director.SESSION, force=True)
            self.say("Ciallo～ 今天也一起加油！")
            return 0
        if message == 0x215:  # capture changed
            if self.dragging:self.finish_drag(allow_dock=False)
            else:self.pressed=None
            return 0
        if message == 0x20A:  # Ctrl + mouse wheel
            if wp & 8:
                delta = C.c_short((wp >> 16) & 0xffff).value
                self.set_scale(self.scale + (0.25 if delta > 0 else -0.25))
            return 0
        if message == 0x7B:  # context menu
            self.menu()
            return 0
        if message == 0x205:  # handle client right-button release explicitly
            self.menu()
            return 0
        if message == 0x101 and (wp == 0x5D or (wp == 0x79 and n.user.GetAsyncKeyState(0x10) & 0x8000)):
            self.menu()
            return 0
        if message == TRAY_MESSAGE:
            if lp in (0x205, 0x7B):
                self.menu()
            elif lp == 0x202:
                self.toggle_visible()
            return 0
        if message == getattr(self, "taskbar_message", -1):
            self.add_tray()
            return 0
        if message in (0x7E, 0x2E0, 0x1A):  # display, per-monitor DPI, work-area change
            if self.hwnd:
                dpi=(wp&0xffff) if message==0x2E0 else None
                rect=None
                if message==0x2E0 and lp:
                    supplied=C.cast(lp,C.POINTER(W.RECT)).contents
                    rect=W.RECT(supplied.left,supplied.top,supplied.right,supplied.bottom)
                post=self.pending_display is None
                self.pending_display=(dpi,rect)
                # UpdateLayeredWindow can deliver DPI messages synchronously. Defer cache
                # destruction until the active display call has released its GDI surface.
                if post:n.user.PostMessageW(hwnd,DISPLAY_UPDATE,0,0)
            return 0
        if message==DISPLAY_UPDATE:
            update=self.pending_display
            self.pending_display=None
            if update:self.recover_display(*update)
            return 0
        if message == 0x10:
            n.user.DestroyWindow(hwnd)
            return 0
        if message == 2:
            n.user.KillTimer(hwnd, 1)
            if self.running:
                n.user.PostQuitMessage(0)
            return 0
        return n.user.DefWindowProcW(hwnd, message, wp, lp)

    def run(self, show_settings=False):
        self.running = True
        if not self.tray:
            self.add_tray()
        n.user.ShowWindow(self.hwnd, 4)
        self.say(("计时已恢复 · "+self.session.label) if self.restored_session and self.session.phase in ('focus','break','ready') else "Ciallo～ 右键我可以打开菜单")
        if show_settings:
            self.command(12)
        message = W.MSG()
        while True:
            result = n.user.GetMessageW(C.byref(message), None, 0, 0)
            if result == -1:
                raise C.WinError(C.get_last_error())
            if result == 0:
                break
            n.user.TranslateMessage(C.byref(message))
            n.user.DispatchMessageW(C.byref(message))

    def close(self):
        if self.closing:
            return
        self.closing = True
        if hasattr(self, "config"):
            self.persist()
        if hasattr(self,'session'):
            self.save_progress()
        if self.tray:
            n.shell.Shell_NotifyIconW(2, C.byref(self.tray))
        if self.settings:
            self.settings.close()
        if self.overlay:
            self.overlay.close()
        for hwnd in (self.bubble, self.hwnd):
            if hwnd and n.user.IsWindow(hwnd):
                n.user.DestroyWindow(hwnd)
        self.bubble = self.hwnd = None
        self.cache.clear()
        if self.registered:
            n.user.UnregisterClassW(CLASS_NAME, self.class_instance)
        for icon in (self.icon_big, self.icon_small):
            if icon:
                n.user.DestroyIcon(icon)
        self.icon_big = self.icon_small = None
        self.imaging.close()
        if self.ui_font:n.gdi.DeleteObject(self.ui_font);self.ui_font=None
