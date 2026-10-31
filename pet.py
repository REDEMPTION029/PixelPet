"""PixelPet native Windows entry point. Python standard library only."""
import ctypes
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
import sys


def smoke_test(report_path):
    """Exercise the actual bundled assets/window and exit without saving user settings."""
    import json
    from src import native_api as n
    from src.native_app import PetApp
    from src.native_model import ROOT, DATA_DIR
    app = PetApp(test_mode=True, preview=True)
    try:
        counts = {a: len(f) for a, f in app.library.frames.items()}
        assert sum(counts.values()) == 36
        assert n.user.GetWindowLongPtrW(app.hwnd, -20) & 0x40000
        assert n.user.SendMessageW(app.hwnd, 0x7f, 1, 0) == app.icon_big
        for action, frames in app.library.frames.items():
            app.player.play(action)
            for index in range(len(frames)):
                app.player.index = index
                app.render(force=True)
        app.add_tray()
        assert app.tray is not None
        n.user.PostMessageW(app.hwnd, 0x10, 0, 0)
        app.run()
        assert not n.user.IsWindow(app.hwnd)
        report = {"ok": True, "frozen": bool(getattr(sys, "frozen", False)),
                  "python": sys.version, "actions": counts, "taskbar_icon": True,
                  "tray_icon": True, "resources": str(ROOT), "settings": str(DATA_DIR)}
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    finally:
        app.close()


def main():
    if sys.platform != "win32":
        raise SystemExit("This version requires Windows 10 or later.")
    from src.native_model import DATA_DIR
    runtime = DATA_DIR
    runtime.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(runtime / "pet.log", maxBytes=1024 * 1024, backupCount=2, encoding="utf-8")
    logging.basicConfig(handlers=[handler], level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    from src import native_api as n
    n.shell.SetCurrentProcessExplicitAppUserModelID("REDEMPTION029.PixelPet")
    try:
        n.bind(n.user, "SetProcessDpiAwarenessContext", n.W.BOOL, ctypes.c_void_p)(ctypes.c_void_p(-4))
    except AttributeError:
        n.bind(n.user, "SetProcessDPIAware", n.W.BOOL)()
    preview = "--preview" in sys.argv
    smoke_report = Path(sys.argv[sys.argv.index("--smoke-test-report") + 1]) if "--smoke-test-report" in sys.argv else None
    mutex_name = "Local\\PixelPetSmokeV1" if smoke_report else ("Local\\PixelPetNativePreviewV1" if preview else "Local\\PixelPetNativeV1")
    mutex = n.checked(n.kernel.CreateMutexW(None, False, mutex_name))
    already_running = ctypes.get_last_error() == 183
    app = None
    try:
        if already_running:
            logging.info("Another native pet is already running")
            return 0
        if smoke_report:
            smoke_test(smoke_report)
            return 0
        from src.native_app import PetApp
        app = PetApp(test_mode=preview, preview=preview)
        logging.info("Native pet started with %s", sys.executable)
        app.run()
        return 0
    except Exception:
        logging.exception("Pet failed")
        if smoke_report:
            return 1
        n.user.MessageBoxW(None, f"桌宠启动或运行失败。\n请查看：{runtime / 'pet.log'}", "PixelPet", 0x10)
        return 1
    finally:
        if app:
            app.close()
        n.kernel.CloseHandle(mutex)


if __name__ == "__main__":
    sys.exit(main())
