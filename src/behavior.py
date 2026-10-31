"""Animation arbitration and a non-blocking focus timer; independent of Win32."""
import math
import time


class Director:
    AUTO, USER, SESSION, DRAG = 1, 3, 4, 10

    def __init__(self, player):
        self.player = player
        self.priority = 0
        self.pending = None
        self.last_user = -math.inf
        self.intent = "idle"

    def request(self, action, priority=USER, once=False, force=False, now=None):
        now = time.monotonic() if now is None else now
        if action not in self.player.library.frames:
            return False
        if not force:
            if action == self.player.action or action == self.intent:
                return False
            if self.player.once:
                if priority < self.priority or priority == self.AUTO:
                    return False
                self.pending = (action, once, priority)
                return True
            if priority == self.AUTO and self.player.action != "idle":
                return False
            if priority == self.USER and now - self.last_user < 0.35:
                return False
        if priority >= self.USER:
            self.last_user = now
        if force:
            self.pending = None
        else:
            exit_action = self.player.library.meta[self.player.action].get("exit")
            if exit_action and exit_action in self.player.library.frames:
                self.pending = (action, once, priority)
                self.priority = priority
                self.player.play(exit_action, once=True)
                return True
        self._start(action, once, priority)
        return True

    def _start(self, action, once, priority):
        self.priority = priority
        self.intent = action
        enter = self.player.library.meta[action].get("enter")
        self.player.play(enter if enter else action, once=True if enter else once)

    def advance(self, dt):
        finished = self.player.advance(dt)
        if finished and self.pending:
            action, once, priority = self.pending
            self.pending = None
            exit_action = self.player.library.meta[self.player.action].get("exit")
            if exit_action and self.player.action != action:
                self.pending = (action, once, priority)
                self.priority = priority
                self.player.play(exit_action, once=True)
            else:
                self._start(action, once, priority)
        elif finished and self.player.action == "idle":
            self.priority = 0
            self.intent = "idle"
        return finished

    @property
    def protected(self):
        return self.player.once


class FocusSession:
    def __init__(self, clock=time.monotonic):
        self.clock = clock
        self.phase = "idle"
        self.paused = False
        self.deadline = 0.0
        self.held = 0.0
        self.break_seconds = 300

    def start(self, minutes=25, break_minutes=5):
        if not 1 <= minutes <= 180 or not 1 <= break_minutes <= 60:
            raise ValueError("Invalid session duration")
        self.phase, self.paused = "focus", False
        self.deadline = self.clock() + minutes * 60
        self.break_seconds = break_minutes * 60

    @property
    def remaining(self):
        if self.phase not in ("focus", "break"):
            return 0
        return max(0, math.ceil(self.held if self.paused else self.deadline - self.clock()))

    @property
    def quiet(self):
        return self.phase == "focus"

    def pause_resume(self):
        if self.phase not in ("focus", "break"):
            return
        if self.paused:
            self.deadline = self.clock() + self.held
        else:
            self.held = max(0, self.deadline - self.clock())
        self.paused = not self.paused

    def stop(self):
        self.phase, self.paused = "idle", False

    def poll(self):
        if self.paused or self.phase not in ("focus", "break") or self.clock() < self.deadline:
            return None
        if self.phase == "focus":
            self.phase = "break"
            self.deadline += self.break_seconds
            if self.clock() >= self.deadline:
                self.phase = "ready"
                return "break_done"
            return "focus_done"
        self.phase = "ready"
        return "break_done"

    def snapshot(self, wall_time=None):
        remaining=max(0.0,self.held if self.paused else self.deadline-self.clock())
        return {"version":1,"phase":self.phase,"paused":self.paused,
                "remaining":remaining if self.phase in ("focus","break") else 0,
                "break_seconds":self.break_seconds,"saved_at":time.time() if wall_time is None else wall_time}

    def restore(self, raw, wall_time=None):
        """Use wall time only across restarts; live countdown stays on monotonic time."""
        self.stop()
        if not isinstance(raw,dict) or type(raw.get('version')) is not int or raw['version']!=1:return False
        phase=raw.get('phase')
        if phase not in ('focus','break','ready','idle') or type(raw.get('paused')) is not bool:return False
        for key,maximum in (('remaining',10800),('break_seconds',3600),('saved_at',1e12)):
            value=raw.get(key)
            if type(value) not in (int,float) or not math.isfinite(value) or not 0<=value<=maximum:return False
        if raw['break_seconds']<60:return False
        self.break_seconds=raw['break_seconds']
        self.phase=phase
        if phase in ('idle','ready'):return True
        now=time.time() if wall_time is None else wall_time
        elapsed=now-raw['saved_at']
        remaining=raw['remaining']
        # A backwards wall clock is ambiguous; preserve remaining time in a paused state.
        self.paused=raw['paused'] or elapsed < -2
        if not self.paused:remaining-=max(0,elapsed)
        if remaining<=0 and not self.paused:
            if phase=='focus':
                remaining+=self.break_seconds
                self.phase='break'
            if remaining<=0:self.phase='ready'
        self.held=max(0,remaining)
        self.deadline=self.clock()+self.held
        return True

    @property
    def label(self):
        if self.phase == "idle":
            return "未开始专注"
        if self.phase == "ready":
            return "休息完成 · 等你开始下一轮"
        m, s = divmod(self.remaining, 60)
        return f"{'专注' if self.phase == 'focus' else '休息'} {m:02}:{s:02}" + ("（暂停）" if self.paused else "")
