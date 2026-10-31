"""Prepare a clean source upload and Windows release ZIP; no remote side effects."""
from pathlib import Path
import hashlib
import importlib.metadata
import shutil
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
VERSION = "0.7.0"
EXE_NAME = f"PixelPet-v{VERSION}.exe"


def main():
    release = ROOT / "release"
    upload = release / f"github-upload-v{VERSION}"
    upload.mkdir(parents=True, exist_ok=False)
    roots = ["pet.py", "README.md", ".gitignore", "启动桌宠.bat", "requirements.txt",
             "requirements-build.txt", "reference_original.png", "src", "assets", "scripts", "docs"]
    files = []
    for name in roots:
        path = ROOT / name
        for file in (path.rglob("*") if path.is_dir() else [path]):
            relative = file.relative_to(ROOT)
            if not file.is_file() or "__pycache__" in relative.parts or file.suffix == ".pyc":
                continue
            if "candidates" in relative.parts:
                continue
            if relative.as_posix() == "docs/cleanup_record.json":
                continue
            assert not any(p in ("runtime", "backups", ".git", "build", "release") for p in relative.parts)
            target = upload / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(file, target)
            files.append(relative)
    assert all((upload / f).stat().st_size < 25 * 1024 * 1024 for f in files)
    source_zip = release / f"PixelPet-v{VERSION}-source.zip"
    with zipfile.ZipFile(source_zip, "w", zipfile.ZIP_DEFLATED) as archive:
        for file in sorted(files):
            archive.write(upload / file, file.as_posix())
    licenses = release / "licenses"
    licenses.mkdir(exist_ok=True)
    shutil.copy2(Path(sys.base_prefix) / "LICENSE.txt", licenses / "Python-LICENSE.txt")
    dist = importlib.metadata.distribution("pyinstaller")
    copyright_file = next(p for p in dist.files if str(p).endswith("licenses/COPYING.txt"))
    shutil.copy2(dist.locate_file(copyright_file), licenses / "PyInstaller-COPYING.txt")
    readme = release / "README.txt"
    readme.write_text(
        f"PixelPet v{VERSION} · Windows x64\n\n"
        f"双击 {EXE_NAME}，无需安装 Python。\n"
        "人物图标同时出现在 Windows 任务栏和托盘。\n"
        "拖动移动；点击头/身体触发表情；双击开心动作。\n"
        "右键菜单：散步、睡觉/唤醒、缩放、置顶、退出。Ctrl+滚轮缩放。\n"
        "托盘单击显隐，右键菜单。\n\n"
        "配置与日志：%LOCALAPPDATA%\\PixelPet\n"
        "v0.7.0：八帧跑动、计时恢复、缓存预算与 DPI 适配。\n"
        "右键按设置开始专注，或选择短时专注 5 分钟。设置可选专注及休息时长。\n"
        "专注期间关闭自动散步/闲聊/打盹，手动互动仍可用。\n"
        "拖到左右边缘松手可收起，点击探头恢复。面板闲置渐退，倒计时保持。\n"
        "八帧侧身步态已接入，动作细节仍可打磨。\n"
        "源码与计划：https://github.com/REDEMPTION029/PixelPet（完成手动上传后可用）\n"
        "随包附带 Python 和 PyInstaller 的许可文本；当前 exe 尚未代码签名。\n",
        encoding="utf-8-sig")
    runtime_zip = release / f"PixelPet-v{VERSION}-windows-x64.zip"
    with zipfile.ZipFile(runtime_zip, "w", zipfile.ZIP_DEFLATED) as archive:
        for file in [release / EXE_NAME, readme, *licenses.iterdir()]:
            archive.write(file, file.relative_to(release).as_posix())
    notes = """# PixelPet v0.7.0 — 计时恢复、八帧动画与多屏适配

Windows x64 早期版本。下载 `PixelPet-v0.7.0-windows-x64.zip`，解压后双击 `PixelPet-v0.7.0.exe`，无需安装 Python。

- 新增专注进度原子存档：启动、暂停、结束时立即保存，运行时每 15 秒检查点，正常退出再保存；重启扣除离线时间，暂停保持，时钟回退保守暂停。
- GPT 重绘八帧侧身动作，拖动周期保留 680ms；脚本仅裁剪对齐。
- 精灵缓存改为 32 MiB 像素预算，复用重复解码资源；隐藏时释放精灵缓存并改为每秒刷新。
- Per-Monitor DPI 缩放覆盖宠物、计时面板、设置窗口；小工作区自动限制尺寸，内部屏幕边界可跨越拖动。
- 修复显示器/DPI 变化后的原地跑动、拖动中缩放跳位、起步阶段关闭散步不生效。
- 设置新增惯性、探头、提示音开关；专注 15/25/45/60 分钟，休息 5/10/15 分钟，保存后用于下一轮。
- 拖动跑步周期从 320ms 放慢到 680ms；松手按最近拖动速度惯性滑行，逐渐减速停下。
- 惯性到达边缘衔接探头；重新抓取、打开菜单或缩放立即停止滑行。
- GPT 重绘四分之三侧身跑步；探头双眼正视使用者，左右边缘保持握边位置。
- 拖到左右边缘松手后收进屏幕并把边偷看，点击恢复；限制裁剪避免跨屏泄露。
- 幼圆中文、Comic Sans MS 数字的头顶倒计时面板，跟随人物；交互时展开，闲置后背景/按钮渐退，活动倒计时常驻。
- 未开启专注或结束计时后隐藏面板；专注及其休息阶段支持面板暂停/继续、结束，完成有一次提示音。
- 独立动作调度：自动行为不打断互动，重复睡眠不重启，拖动可取消待执行动作。
- 原生陪伴设置窗口，配置自动散步、闲聊、打盹、置顶、大小与气泡频率。
- 按设置开始专注、5 分钟快速入口、暂停/继续/结束、完成后按设置休息；通知仅发送一次。
- Windows 任务栏、托盘及 exe 均使用人物图标。
- 透明窗口、拖动、点击与双击、中文气泡、右键菜单、散步、缩放、置顶和单实例。
- 配置与日志保存在 `%LOCALAPPDATA%\\PixelPet`，独立于单文件 exe 的临时解包目录。
- 28 项单元测试、284 次原生渲染检查及 120 组布局模拟通过，覆盖双向拖动、边缘裁剪、计时面板和资源清理。

当前是八帧卡通关键姿态，人物细节与更高帧率的流畅度仍可改善；本机双屏同为 125%，已检查两个实际工作区；不同 DPI 实体跨屏和硬件热插拔未完整验证；发行文件尚未代码签名。计时进度保存在 session.json，重启可恢复。字体使用系统已安装字体，不附带字体文件。

附件提供 Windows 运行包、源码包及 SHA256 校验值。原图作为人物参考，动作由 GPT 重绘，脚本仅切分和对齐帧。
"""
    (release / "RELEASE_NOTES.md").write_text(notes, encoding="utf-8")
    hashes = []
    for file in (release / EXE_NAME, runtime_zip, source_zip):
        hashes.append(f"{hashlib.sha256(file.read_bytes()).hexdigest()}  {file.name}")
    (release / "SHA256SUMS.txt").write_text("\n".join(hashes) + "\n", encoding="ascii")
    for file in (source_zip, runtime_zip):
        with zipfile.ZipFile(file) as archive:
            assert archive.testzip() is None
    print(f"Clean source: {len(files)} files; upload root/src/scripts/docs and assets in separate web batches if over 100.")
    print(f"Source ZIP: {source_zip.stat().st_size:,} bytes")
    print(f"Windows ZIP: {runtime_zip.stat().st_size:,} bytes")
    print("Verified ZIP integrity and SHA256; no remote upload performed.")


if __name__ == "__main__":
    main()
