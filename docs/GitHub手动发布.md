# 手动发布到 GitHub

本轮本地文件已准备；此说明不代表已经上传成功。

## 1. 创建仓库

打开 https://github.com/new ：

- Owner：`REDEMPTION029`
- Repository name：`PixelPet`
- Description：`Windows desktop companion with GPT-redrawn animation, built with Python and native Win32. No Qt required.`
- Visibility：想公开分享选 Public，否则选 Private。
- README、.gitignore、License 先都不选，源码包内已有前两者；许可类型留待项目所有者决定。

点击 Create repository。预期地址为 `https://github.com/REDEMPTION029/PixelPet`。

## 2. 上传源码

本地 `release/github-upload-v0.7.0/` 是当前仓库根目录；或者先解压 `PixelPet-v0.7.0-source.zip`。旧 v0.3 包不再包含本轮修复。

在仓库首页选择 uploading an existing file，或 Add file → Upload files。将 **github-upload 文件夹里面的文件和目录** 拖进上传页面，保留 `src/`、`assets/`、`scripts/`、`docs/` 的结构。不要把外层 `github-upload` 目录本身作为仓库唯一根目录，也不要只上传源码 ZIP，因为 GitHub 不会自动解压。

Commit message 可填 `Release PixelPet v0.7.0`，提交到 `main`。

新版源码请分两批上传：先上传根目录文件和 src/scripts/docs，再上传 assets。单个文件小于 25 MiB，各批不超过 100 个文件。不要上传工作目录里的 `backups/`、`runtime/`、`build/` 或整个 `release/`。

## 3. 发布可下载的 exe

上传源码后，在仓库右侧点击 Releases → Create a new release / Draft a new release：

- Tag：`v0.7.0`，创建新 tag，Target 选 `main`。
- Title：`PixelPet v0.7.0 — 计时恢复、八帧动画与多屏适配`。
- Description：复制本地 `release/RELEASE_NOTES.md` 的正文。
- 附件：上传 `PixelPet-v0.7.0-windows-x64.zip` 和 `SHA256SUMS.txt`；也可再上传 `PixelPet-v0.7.0.exe` 方便直接下载。
- 这是首个早期版本，建议勾选 This is a pre-release，然后 Publish release。

完成后的下载页为 `https://github.com/REDEMPTION029/PixelPet/releases`。

官方步骤：[创建仓库](https://docs.github.com/en/repositories/creating-and-managing-repositories/creating-a-new-repository)、[上传文件](https://docs.github.com/en/repositories/working-with-files/managing-files/adding-a-file-to-a-repository)、[发布 Release](https://docs.github.com/en/repositories/releasing-projects-on-github/managing-releases-in-a-repository)。
