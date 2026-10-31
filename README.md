# PixelPet · GPT 重绘版 v0.3.0

Windows 桌面伙伴，使用 Python 和 Win32 原生接口，不依赖 Qt。发行版是单文件 exe，使用者无需安装 Python。

![角色图标](assets/app-icon.png)

## 启动

发行版：双击 `PixelPet.exe`。源码版：安装 Python 3.14 后，运行 `python pet.py`；本机也可使用 `启动桌宠.bat`。

人物图标同时出现在 Windows 任务栏和右下角托盘，exe 文件也使用同一图标。

拖动人物移动；点击头/身体触发表情；双击播放开心动作；右键菜单支持散步、睡觉/唤醒、缩放、置顶与退出。Ctrl + 滚轮缩放，托盘图标单击显隐、右键打开菜单。

## 本轮改变

六组旧动画已全部替换为 GPT 根据 `reference_original.png` 重绘的 36 张帧：待机、走路、摸头、身体点击、坐姿睡觉、开心跳跃。每帧使用独立时长，睡眠进入后只循环闭眼段。

角色动作由 GPT 绘制。脚本仅切分六格图、对齐画布和保存 PNG，不使用区域像素移动、切块扭动或程序绘制来伪造动作。原图未修改。第一版重绘仍需结合播放检查服装小细节和帧间连贯性，不承诺单次生图完全消除漂移。

下载源码后在本地打开 [动画预览](docs/动画预览.html)，可同时播放六组动作、逐帧检查或切换深浅背景。原始生图在 `assets/sheets/`，完整提示词在 `docs/generation_prompts.json`。

## 项目结构

```text
pet.py                  入口、日志、DPI、单实例
src/                    原生窗口、动画、配置与文案（5 个文件）
assets/                 36 张运行帧、时长配置及 6 张 GPT 原稿
scripts/import_sheets.py 切图与画布对齐，不生成动作
scripts/test_native.py   单元与原生窗口测试
scripts/build_exe.py     单文件 exe 构建
scripts/build_icon.py    从原始角色制作多尺寸图标
docs/                   动画预览、制作记录、提示词
runtime/                源码版本地配置与日志，不发布
reference_original.png  唯一人物参考，未改动
```

旧 Qt 代码和像素移动补帧工具已清除。本地旧备份、用户配置、日志和构建缓存不会上传 GitHub。

## 开发与验证

```powershell
python pet.py
python scripts/test_native.py --window
python scripts/import_sheets.py
python -m pip install -r requirements-build.txt
python scripts/build_exe.py
```

构建结果是 `release/PixelPet.exe`，包含 36 张动作帧及图标。无需 Qt、Pillow 或额外图像处理库。

发行版配置与日志在 `%LOCALAPPDATA%\PixelPet`，不会写入 exe 的临时解包目录；源码版使用 `runtime/`。初次默认 50% 大小、自动散步关闭；缩放范围为 50%–200%。本版针对 Windows 10/11 x64，当前 Windows 11 电脑实测通过，其他系统版本和混合 DPI 多屏热插拔待验证。当前发行文件尚未代码签名。

## 开发路线与参考

详见 [开发路线与 GitHub 参考](docs/开发路线与GitHub参考.md)。优先改进动作衔接和角色一致性，再增加番茄钟、状态养成、可导入素材包及可选聊天能力。当前版本没有这些未实现功能。
