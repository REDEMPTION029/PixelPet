"""Native-version checks; --window also exercises real layered windows."""
import ctypes as C
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.native_model import Player, SurfaceCache, validate_config, save_config, load_config, resample, save_session, load_session
from src.behavior import Director, FocusSession
from src.desktop_state import DragInertia,PanelFade,EdgeDock,horizontal_clip,mirrored_for,inward_direction,fitted_scale,clamped_position,dragged_position


class FakeLibrary:
    frames = {"idle": [1, 2], "happy": [3, 4]}
    meta = {"idle": {"duration_ms": 100, "loop": True},
            "happy": {"duration_ms": 50, "loop": False, "next": "idle"}}


class ModelTests(unittest.TestCase):
    def test_surface_cache_enforces_byte_budget_and_releases_handles(self):
        from types import SimpleNamespace
        class Surface:
            def __init__(self,w,h,data):self.width,self.height,self.closed=w,h,False
            def close(self):self.closed=True
        cache=SurfaceCache(Surface,byte_budget=4*1024*1024)
        player=SimpleNamespace(action='walk',index=0,frame=(512,512,b'\0\0\0\xff'*(512*512)))
        first=cache.get(player,2,False)
        self.assertIs(first,cache.get(player,2,False))
        player.index=1
        second=cache.get(player,2,False)
        self.assertTrue(first.closed)
        self.assertFalse(second.closed)
        self.assertLessEqual(cache.bytes,cache.byte_budget)
        cache.clear()
        self.assertTrue(second.closed)
        self.assertEqual(cache.bytes,0)

    def test_session_file_roundtrip_and_corruption(self):
        session=FocusSession();session.start(5);session.pause_resume()
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'session.json'
            save_session(session,path)
            restored=FocusSession()
            self.assertTrue(load_session(restored,path))
            self.assertTrue(restored.paused)
            self.assertEqual(restored.remaining,session.remaining)
            path.write_text('{broken',encoding='utf-8')
            self.assertFalse(load_session(FocusSession(),path))

    def test_finished_clip_keeps_elapsed_time(self):
        p = Player(FakeLibrary())
        p.play("happy")
        self.assertEqual(p.advance(.125), "happy")
        self.assertEqual(p.elapsed, 25)
        p.advance(.075)
        self.assertEqual(p.index, 1)

    def test_loop_retains_elapsed(self):
        p = Player(FakeLibrary())
        p.advance(0.25)
        self.assertEqual((p.action, p.index, p.elapsed), ("idle", 0, 50))

    def test_once_returns_to_idle(self):
        p = Player(FakeLibrary())
        p.play("happy")
        self.assertEqual(p.advance(0.1), "happy")
        self.assertEqual((p.action, p.index), ("idle", 0))

    def test_missing_action_falls_back(self):
        p = Player(FakeLibrary())
        p.play("missing")
        self.assertEqual(p.action, "idle")

    def test_frame_timing_and_sleep_loop(self):
        from types import SimpleNamespace
        lib = SimpleNamespace(frames={"idle": [1, 2, 3]},
            meta={"idle": {"duration_ms": 100, "frame_durations_ms": [20, 30, 40], "loop": True, "loop_start": 1}})
        p = Player(lib)
        p.advance(0.025)
        self.assertEqual((p.index, p.elapsed), (1, 5))
        p.advance(0.065)
        self.assertEqual((p.index, p.elapsed), (1, 0))

    def test_invalid_config(self):
        cfg = validate_config({"x": float("nan"), "y": "oops", "scale": float("inf"),
                               "topmost": "false", "auto_move": 1})
        self.assertEqual(cfg, validate_config({}))
        self.assertEqual(validate_config({"scale": 500})["scale"], 2)
        self.assertEqual(validate_config([]), validate_config({}))

    def test_new_settings_defaults_and_validation(self):
        old=validate_config({'scale':.75,'auto_move':True})
        self.assertTrue(old['drag_inertia'])
        self.assertEqual((old['focus_minutes'],old['break_minutes']),(25,5))
        cfg=validate_config({'drag_inertia':False,'focus_minutes':45,'break_minutes':10})
        self.assertFalse(cfg['drag_inertia'])
        self.assertEqual((cfg['focus_minutes'],cfg['break_minutes']),(45,10))
        cfg=validate_config({'focus_minutes':True,'break_minutes':999,'drag_inertia':'false'})
        self.assertEqual((cfg['focus_minutes'],cfg['break_minutes']),(25,5))
        self.assertTrue(cfg['drag_inertia'])

    def test_config_roundtrip_and_corruption(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "settings.json"
            save_config({"x": -800, "y": 200, "scale": 0.75, "auto_move": True}, path)
            self.assertEqual(load_config(path)["x"], -800)
            self.assertEqual(load_config(path)["scale"], 0.75)
            path.write_text("broken", encoding="utf-8")
            self.assertEqual(load_config(path), validate_config({}))

    def test_flip_and_scaling_keep_pixel_data(self):
        red, blue = bytes((0, 0, 255, 255)), bytes((255, 0, 0, 255))
        frame = (2, 1, red + blue)
        self.assertEqual(resample(frame, 1, True), (2, 1, blue + red))
        self.assertEqual(resample(frame, 2, False), (4, 2, (red * 2 + blue * 2) * 2))


class BehaviorTests(unittest.TestCase):
    def test_display_geometry_matrix_and_internal_edge_dragging(self):
        for area in ((0,0,1920,1040),(-2560,-200,0,1240),(0,0,800,560),(1920,0,3000,1880)):
            for dpi in (96,120,144,192):
                for user_scale in (.5,1,2):
                    scale=fitted_scale(user_scale,area,dpi)
                    w=h=round(512*scale)
                    x,y=clamped_position(99999,-99999,w,h,area)
                    self.assertGreaterEqual(x,area[0]);self.assertGreaterEqual(y,area[1])
                    self.assertLessEqual(x+w,area[2]);self.assertLessEqual(y+h,area[3])
        areas=[(-1920,0,0,1080),(0,0,2560,1440)]
        self.assertEqual(dragged_position(-128,400,256,256,areas[1],areas),(-128,400))
        self.assertEqual(dragged_position(-128,400,256,256,areas[1],[areas[1]]),(0,400))

    def test_session_restore_live_paused_expired_and_clock_rollback(self):
        clock=[0.0]
        session=FocusSession(lambda:clock[0]);session.start(5,1)
        clock[0]=10
        snapshot=session.snapshot(1000)
        restored=FocusSession(lambda:0)
        self.assertTrue(restored.restore(snapshot,1120))
        self.assertEqual(restored.remaining,170)
        self.assertEqual(restored.phase,'focus')
        session.pause_resume()
        paused=session.snapshot(1000)
        restored.restore(paused,2000)
        self.assertTrue(restored.paused);self.assertEqual(restored.remaining,290)
        restored.restore(snapshot,1300)
        self.assertEqual((restored.phase,restored.remaining),('break',50))
        restored.restore(snapshot,1400)
        self.assertEqual(restored.phase,'ready')
        self.assertIsNone(restored.poll())
        restored.restore(snapshot,900)
        self.assertTrue(restored.paused);self.assertEqual(restored.remaining,290)

    def test_session_restore_rejects_invalid_data_and_stopped_session(self):
        session=FocusSession()
        for raw in (None,{}, {'version':1,'phase':'focus','paused':False,'remaining':float('nan'),'break_seconds':300,'saved_at':10}):
            self.assertFalse(session.restore(raw,100))
            self.assertEqual(session.phase,'idle')
        session.start(1);session.stop()
        restored=FocusSession()
        self.assertTrue(restored.restore(session.snapshot(100),200))
        self.assertEqual(restored.phase,'idle')

    def test_late_timer_poll_skips_an_already_expired_break(self):
        clock=[0.0];session=FocusSession(lambda:clock[0]);session.start(1,1)
        clock[0]=200
        self.assertEqual(session.poll(),'break_done')
        self.assertEqual(session.phase,'ready')
        self.assertIsNone(session.poll())
    def make_inertia(self):
        clock=[0.0]
        motion=DragInertia(lambda:clock[0])
        motion.begin(100,100)
        clock[0]=.05;motion.sample(125,110)
        clock[0]=.1;motion.sample(150,120)
        return motion,clock

    def test_inertia_preserves_direction_and_stops(self):
        motion,_=self.make_inertia()
        self.assertTrue(motion.release())
        self.assertAlmostEqual(motion.vx,500)
        self.assertAlmostEqual(motion.vy,200)
        dx,dy=motion.advance(.033)
        self.assertGreater(dx,0);self.assertGreater(dy,0)
        self.assertLess(motion.vx,500)
        for _ in range(40):motion.advance(.033)
        self.assertFalse(motion.active)

    def test_inertia_paused_release_and_new_grab_do_not_fling(self):
        motion,clock=self.make_inertia()
        clock[0]+=.2
        self.assertFalse(motion.release())
        motion,_=self.make_inertia();motion.release()
        motion.begin(5,5)
        self.assertFalse(motion.active)
        self.assertFalse(motion.release())

    def test_inertia_distance_does_not_depend_on_tick_frequency(self):
        a,_=self.make_inertia();b,_=self.make_inertia()
        a.release();b.release()
        one=a.advance(.1)
        parts=[b.advance(.025) for _ in range(4)]
        self.assertAlmostEqual(one[0],sum(p[0] for p in parts))
        self.assertAlmostEqual(one[1],sum(p[1] for p in parts))

    def test_slow_drag_accumulates_horizontal_motion_before_turning(self):
        from types import SimpleNamespace
        from src.native_app import PetApp
        app=SimpleNamespace(pressed=(100,100,200,200),dragging=True,drag_last_x=100,
            inertia=DragInertia(),
            flip=False,library=SimpleNamespace(meta={'dragRun':{'base_facing':'left'}}),
            clamp=lambda:None,overlay=SimpleNamespace(touch=lambda:None),render=lambda:None)
        for x in (101,102):
            PetApp.drag_to(app,x,100)
            self.assertFalse(app.flip)
        PetApp.drag_to(app,103,100)
        self.assertTrue(app.flip)
        for x in (102,101):
            PetApp.drag_to(app,x,100)
            self.assertTrue(app.flip)
        PetApp.drag_to(app,100,100)
        self.assertFalse(app.flip)

    def test_inward_facing_accounts_for_sprite_orientation(self):
        self.assertEqual(inward_direction('left'),'right')
        self.assertEqual(inward_direction('right'),'left')
        self.assertFalse(mirrored_for(inward_direction('left'),'right'))
        self.assertTrue(mirrored_for(inward_direction('right'),'right'))
        self.assertTrue(mirrored_for('right','left'))
        self.assertFalse(mirrored_for('left','left'))

    def test_idle_and_finished_clock_stay_hidden_even_after_touch(self):
        from types import SimpleNamespace
        from unittest.mock import patch
        from src.focus_overlay import FocusOverlay
        from src import native_api as n
        overlay=FocusOverlay.__new__(FocusOverlay)
        overlay.hwnd=2
        overlay.fade=SimpleNamespace(strength=1)
        overlay.app=SimpleNamespace(hwnd=1,session=SimpleNamespace(phase='idle'))
        for phase in ('idle','ready'):
            overlay.app.session.phase=phase
            with patch.object(n.user,'IsWindowVisible',return_value=True),patch.object(n.user,'ShowWindow') as show:
                overlay.update()
                show.assert_called_once_with(2,0)
    def test_panel_chrome_fades_without_stopping_countdown(self):
        clock=[0.0]
        fade=PanelFade(lambda:clock[0])
        focus=FocusSession(lambda:clock[0]);focus.start(1)
        clock[0]=6.6
        self.assertAlmostEqual(fade.strength,.5)
        clock[0]=20
        self.assertEqual(fade.strength,0)
        self.assertEqual(focus.remaining,40)
        fade.touch();self.assertEqual(fade.strength,1)

    def test_edge_geometry_clips_to_current_monitor(self):
        area=(-1920,0,0,1080)
        self.assertEqual(EdgeDock.choose(-1920,256,area),'left')
        self.assertEqual(EdgeDock.choose(-256,256,area),'right')
        self.assertIsNone(EdgeDock.choose(-900,256,area))
        edge=EdgeDock();edge.begin('left',area,-1920,100,256,.5)
        self.assertEqual(edge.advance(1),-2000)
        self.assertEqual(horizontal_clip(-2000,256,area),(80,256))
        self.assertEqual(edge.clear(),(-1920,100))
    def make_director(self):
        from types import SimpleNamespace
        frames = {name: [1] for name in ("idle", "sleep", "sleepEnter", "sleepExit", "walk", "walkEnter", "walkExit", "happy")}
        meta = {name: {"duration_ms": 100, "loop": name in ("idle", "walk", "sleep"), "next": "idle"} for name in frames}
        meta["sleep"].update(enter="sleepEnter", exit="sleepExit")
        meta["sleepEnter"]["next"] = "sleep"
        meta["walk"].update(enter="walkEnter", exit="walkExit")
        meta["walkEnter"]["next"] = "walk"
        return Director(Player(SimpleNamespace(frames=frames, meta=meta)))

    def test_sleep_enter_wake_during_enter_still_exits(self):
        d = self.make_director()
        self.assertTrue(d.request("sleep", now=1))
        self.assertEqual(d.player.action, "sleepEnter")
        self.assertFalse(d.request("sleep", now=2))
        self.assertTrue(d.request("idle", Director.SESSION, now=3))
        d.advance(.1)
        self.assertEqual(d.player.action, "sleepExit")
        d.advance(.1)
        self.assertEqual(d.player.action, "idle")
        self.assertIsNone(d.pending)

    def test_sleep_exit_before_new_interaction(self):
        d = self.make_director()
        d.request("sleep", now=1)
        d.advance(.1)
        d.request("happy", now=2)
        self.assertEqual(d.player.action, "sleepExit")
        d.advance(.1)
        self.assertEqual(d.player.action, "happy")

    def test_automatic_walk_cannot_interrupt_interaction(self):
        d = self.make_director()
        d.request("happy", now=1)
        self.assertFalse(d.request("walk", Director.AUTO, now=2))
        self.assertEqual(d.player.action, "happy")
        d.advance(.1)
        self.assertTrue(d.request("walk", Director.AUTO, now=3))
        self.assertEqual(d.player.action, "walkEnter")

    def test_drag_cancels_pending_and_walk_stops_via_exit(self):
        d = self.make_director()
        d.request("walk", now=1)
        d.advance(.1)
        d.request("idle", Director.SESSION, now=2)
        self.assertEqual(d.player.action, "walkExit")
        d.request("idle", Director.DRAG, force=True, now=3)
        self.assertEqual(d.player.action, "idle")
        self.assertIsNone(d.pending)

    def test_focus_pause_and_one_shot_notifications(self):
        clock = [0.0]
        focus = FocusSession(lambda: clock[0])
        focus.start(1, 1)
        clock[0] = 10
        focus.pause_resume()
        clock[0] = 200
        self.assertEqual(focus.remaining, 50)
        self.assertIsNone(focus.poll())
        focus.pause_resume()
        clock[0] = 250
        self.assertEqual(focus.poll(), "focus_done")
        self.assertFalse(focus.quiet)
        self.assertIsNone(focus.poll())
        clock[0] = 310
        self.assertEqual(focus.poll(), "break_done")
        self.assertEqual(focus.phase, "ready")
        self.assertIsNone(focus.poll())
        focus.stop()
        self.assertEqual(focus.phase, "idle")


def window_checks():
    from src import native_api as n
    from src.native_app import PetApp
    n.bind(n.user,'SetProcessDpiAwarenessContext',n.W.BOOL,C.c_void_p)(C.c_void_p(-4))
    app = PetApp(test_mode=True)
    app.clock_sound=False
    try:
        assert n.user.GetWindowLongPtrW(app.hwnd, -20) & 0x40000
        assert not (n.user.GetWindowLongPtrW(app.hwnd, -20) & 0x80)
        assert n.user.SendMessageW(app.hwnd, 0x7f, 1, 0) == app.icon_big
        assert n.user.SendMessageW(app.hwnd, 0x7f, 0, 0) == app.icon_small
        counts = {a: len(frames) for a, frames in app.library.frames.items()}
        assert sum(counts.values()) == 71 and counts['dragRun']==8 and 'held' not in counts and counts['peek']==3 and counts['walk']==8, counts
        assert app.library.frames['walk'][0] is app.library.frames['dragRun'][0]
        for frames in app.library.frames.values():
            for w, h, pixels in frames:
                assert len(pixels) == w * h * 4
                assert all(max(pixels[i:i + 3]) <= pixels[i + 3] for i in range(0, len(pixels), 4))
        before = n.user.GetGuiResources(n.kernel.GetCurrentProcess(), 0)
        for scale in (0.5, 0.75, 1.0, 2.0):
            app.set_scale(scale)
            for action, frames in app.library.frames.items():
                app.player.play(action)
                for index in range(len(frames)):
                    app.player.index = index
                    app.flip = bool(index % 2)
                    app.render(force=True)
        app.cache.clear()
        after = n.user.GetGuiResources(n.kernel.GetCurrentProcess(), 0)
        assert after <= before + 2, (before, after)
        app.play("idle", force=True)
        app.play("happy", once=True, priority=Director.SESSION)
        assert app.director.advance(2) == "happy"
        assert app.player.action == "idle"
        app.command(4)
        assert app.player.action == "sleepEnter"
        app.command(4)
        app.director.advance(2)
        assert app.player.action == "sleepExit"
        app.director.advance(2)
        assert app.player.action == "idle"
        app.auto_move = False
        app.director.last_user = float("-inf")
        app.start_walk()
        assert app.player.action == "walkEnter"
        app.director.advance(.3)
        assert app.player.action == "walk" and app.target is not None
        app.x = app.target
        app.last_tick -= 0.1
        n.user.ShowWindow(app.hwnd, 4)
        app.tick()
        assert app.player.action == "walkExit" and app.target is None
        app.director.advance(.4)
        assert app.player.action == "idle"
        app.set_scale(1)
        app.render(force=True)
        # Test Windows' actual layered-window hit testing, not a Python alpha predicate.
        alpha = app.player.frame[2]
        opaque = next((x, y) for y in range(50, 300) for x in range(50, 300)
                      if alpha[(y * 512 + x) * 4 + 3] >= 240)
        assert n.user.WindowFromPoint(n.W.POINT(round(app.x+opaque[0]*app.pixel_scale), round(app.y+opaque[1]*app.pixel_scale))) == app.hwnd
        assert n.user.WindowFromPoint(n.W.POINT(round(app.x), round(app.y))) != app.hwnd
        app.command(6)
        assert app.auto_move
        app.command(6)
        assert not app.auto_move
        app.auto_move=True
        app.director.request('walk',Director.USER,force=True)
        assert app.player.action=='walkEnter'
        app.command(6)
        app.director.advance(.5)
        app.director.advance(.5)
        assert app.player.action=='idle' and not app.auto_move
        app.director.request('walk',Director.DRAG,force=True)
        app.target=app.x+50
        app._message(app.hwnd,0x2E0,0,0)
        app._message(app.hwnd,0x8002,0,0)
        assert app.player.action=='idle' and app.target is None and not app.inertia.active
        app.command(7)
        assert not app.topmost
        app.command(7)
        assert app.topmost
        app.x, app.y = 100000, 100000
        app.clamp()
        left, top, right, bottom = n.work_area(app.x, app.y)
        assert left <= app.x and app.x + app.width <= right
        assert top <= app.y and app.y + app.height <= bottom
        app.add_tray()
        assert app.tray is not None
        app.toggle_visible()
        assert not n.user.IsWindowVisible(app.hwnd)
        app.toggle_visible()
        assert n.user.IsWindowVisible(app.hwnd)
        app.command(12)
        assert n.user.IsWindowVisible(app.settings.hwnd)
        n.user.SendMessageW(app.settings.controls[11], 0xF1, 0, 0)
        n.user.SendMessageW(app.settings.controls[20], 0x14E, 1, 0)
        n.user.SendMessageW(app.settings.controls[22], 0x14E, 2, 0)
        n.user.SendMessageW(app.settings.controls[23], 0x14E, 1, 0)
        n.user.SendMessageW(app.settings.hwnd, 0x111, 100, 0)
        assert not app.idle_chat and app.scale == .75
        assert app.focus_minutes==45 and app.break_minutes==10
        assert not n.user.IsWindowVisible(app.settings.hwnd)
        app.begin_focus()
        assert app.session.remaining==2700 and app.session.break_seconds==600
        app.begin_focus(5)
        assert app.session.quiet and app.player.action == "adjustGlasses"
        assert not app.start_walk(automatic=True)
        app.director.advance(2)
        app.session.deadline = app.session.clock() - 1
        app.tick()
        assert app.session.phase == "break" and app.player.action == "happy"
        app.session.deadline = app.session.clock() - 1
        app.tick()
        assert app.session.phase == "ready" and app.pending_notice == "break_done"
        app.director.advance(2)
        app.tick()
        assert app.pending_notice is None
        left,top,right,bottom=n.work_area(app.x,app.y)
        app.x,app.y=(left+right-app.width)/2,(top+bottom-app.height)/2
        app.pressed=(100,100,app.x,app.y)
        app.drag_last_x=100
        app.drag_to(140,120)
        assert app.dragging and app.player.action=='dragRun' and app.flip and app.lift==0
        app.drag_to(110,130)
        assert not app.flip
        app.finish_drag(allow_dock=False)
        assert not app.dragging and app.player.action=='idle'
        app.x=left
        assert app.dock_if_near_edge()
        assert app.edge.side=='left' and app.player.action=='peek' and not app.flip
        assert app.library.meta['peek']['base_facing']=='right'
        for _ in range(4):app.last_tick-=.1;app.tick()
        assert app.x<left and app.clip_key is not None
        assert not app.start_walk()
        app.undock()
        assert app.edge.side is None and app.clip_key is None
        app.x=right-app.width
        assert app.dock_if_near_edge() and app.flip
        app.undock()
        assert sum(app.library.meta['dragRun']['frame_durations_ms'])==680
        app.x,app.y=(left+right-app.width)/2,(top+bottom-app.height)/2
        start_x,start_y=app.x,app.y
        app.director.request('dragRun',Director.DRAG,force=True)
        app.inertia.vx,app.inertia.vy=300,100
        app.advance_inertia(.1)
        assert app.x>start_x and app.y>start_y and app.inertia.active
        assert not app.start_walk()
        for _ in range(30):app.advance_inertia(.033)
        assert not app.inertia.active and app.player.action=='idle'
        app.x=right-app.width-2
        app.director.request('dragRun',Director.DRAG,force=True)
        app.inertia.vx=400
        app.advance_inertia(.033)
        assert app.edge.side=='right' and not app.inertia.active and app.player.action=='peek'
        app.undock()
        app.edge_peek=False
        app.x=right-app.width
        app.inertia.vx=400
        app.advance_inertia(.033)
        assert not app.inertia.active and app.edge.side is None and app.player.action=='idle'
        app.edge_peek=True
        app.x,app.y=(left+right-app.width)/2,(top+bottom-app.height)/2
        app.pressed=(100,100,app.x,app.y)
        app.dragging=True
        app.director.request('dragRun',Director.DRAG,force=True)
        app.set_scale(1)
        assert not app.dragging and app.pressed is None and app.player.action=='idle'
        app.drag_inertia=False
        app.pressed=(100,100,app.x,app.y)
        app.dragging=True
        app.director.request('dragRun',Director.DRAG,force=True)
        app.inertia.vx=300
        app.finish_drag()
        assert not app.inertia.active and app.player.action=='idle'
        app.drag_inertia=True
        app.session.start(5)
        app.overlay.fade.last_touch-=20
        app.overlay.update()
        assert app.overlay.fade.strength==0 and n.user.IsWindowVisible(app.overlay.hwnd)
        compact=app.overlay.painter.surface(299,'focus',False,0)
        rgba=C.string_at(compact.bits,236*108*4)
        assert rgba[(5*236+5)*4+3]==0
        assert sum(a>0 for a in rgba[3::4])>400
        app.overlay.touch()
        app.overlay.dispatch(app.overlay.hwnd,0x202,0,(round(85*app.overlay.scale)<<16)|round(40*app.overlay.scale))
        assert app.session.paused
        app.overlay.dispatch(app.overlay.hwnd,0x202,0,(round(85*app.overlay.scale)<<16)|round(40*app.overlay.scale))
        assert not app.session.paused
        app.overlay.dispatch(app.overlay.hwnd,0x202,0,(round(85*app.overlay.scale)<<16)|round(180*app.overlay.scale))
        assert app.session.phase=='idle'
        assert not n.user.IsWindowVisible(app.overlay.hwnd)
        original_dpi=app.dpi
        for dpi in (96,144,192):
            app.recover_display(dpi)
            area=n.work_area(app.x+app.width/2,app.y+app.height/2)
            assert area[0]<=app.x and app.x+app.width<=area[2]+1
            assert area[1]<=app.y and app.y+app.height<=area[3]+1
            assert app.cache.bytes<=app.cache.byte_budget
            app.session.start(5)
            app.overlay.update()
            assert n.user.IsWindowVisible(app.overlay.hwnd)
            app.settings.show()
            rect=n.W.RECT()
            n.user.GetWindowRect(app.settings.hwnd,C.byref(rect))
            assert area[0]<=rect.left and rect.right<=area[2]
            assert area[1]<=rect.top and rect.bottom<=area[3]
            app.settings.dispatch(app.settings.hwnd,0x10,0,0)
        app.session.stop()
        app.recover_display(original_dpi)
        for monitor in app.displays:
            left,top,right,bottom=monitor['work']
            app.x,app.y=left+24,top+24
            app.recover_display(monitor['dpi'])
            assert left<=app.x and app.x+app.width<=right+1
            assert top<=app.y and app.y+app.height<=bottom+1
        print(f"PASS: 71 runtime frames, 284 renders, inertia friction/edges, slower drag running/directions, active-only countdown, focus/settings, tray/alpha. GDI: {before} -> {after}")
        n.user.PostMessageW(app.hwnd, 0x10, 0, 0)
        app.run()
        assert not n.user.IsWindow(app.hwnd)
        print("PASS: message loop exits on window close (including preview mode)")
    finally:
        app.close()
    assert not n.user.IsWindow(app.hwnd)
    print("PASS: native window and resource cleanup")


if __name__ == "__main__":
    suite = unittest.TestSuite([unittest.defaultTestLoader.loadTestsFromTestCase(c) for c in (ModelTests, BehaviorTests)])
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    if not result.wasSuccessful():
        sys.exit(1)
    if "--window" in sys.argv:
        window_checks()
