# Git4SubEditor
> Git for Submarine Editor

[![GitHub](https://img.shields.io/badge/GitHub-Git4SubEditor-181717?logo=github)](https://github.com/Yinjie1/Git4SubEditor)
[![PyPI](https://img.shields.io/pypi/v/git4subeditor?logo=pypi)](https://pypi.org/project/git4subeditor/)
[![License](https://img.shields.io/badge/license-MIT-green)](./LICENSE)

一个 CLI 工具, 把 Barotrauma 的 `.sub` 潜艇文件转换为适合 Git 版本追踪的文本格式, 也支持将其转回 `.sub` 文件.

> [!warning]
> 如果你打算将此程序应用于你正在开发的项目, 请先进行**备份**, 以免发生不可挽回的灾难性事故.

> [!note]
> **后续计划**
> - [ ] 我希望能集成一个Git GUI到游戏中, 并直接在潜艇编辑器中可视化不同版本潜艇的差异, 但我不熟悉这个游戏的接口, 也不会C#/Lua, 如果有感兴趣的大佬可以试试.
> - [x] 自动初始化工作区 `git4subeditor init`, 自动添加 `.gitignore` 等
> - [x] 多语言
> - [x] agent skill, 让 ai 根据 `git diff` 拟定提交说明等
> - [x] 历史记录
> - [x] Tab 补全

## 为什么需要 Git
1. Git 的版本控制, 并不是每个版本都备份一个副本, 而是记录两个版本间的 diff, 这样不仅版本仓库体积非常小, 而且可以很方便地看出每次都做了哪些改动. 又或者哪天搞砸了, 也可以回退到之前的任意版本.
    > 就像 Git 官网里提到的: "Git 能高效地存储仓库历史. 截至 2025 年, 当前版本的 Linux 内核源代码大小为 1.7 GB. Git 仅用 5.5 GB 就存储了 Linux 项目的完整历史 (140 万次提交)."
2. 可以上传到远程托管平台, 如 Github, Gitee 等, 这是一种更安全的"云同步", 同时也方便进行多人合作开发.

## 为什么需要这个工具

1. `.sub` 实际上是 gzip 压缩的单个 `xml` 文件. 直接提交 `.sub` 时, Git 只能看到二进制文件发生了变化, 无法审查具体改动.
2. 解压后的 `xml` 中, 潜艇预览图是以源码的形式存放在根节点的 `previewimage` 属性里, 往往会让第一行长达几十万字符. 只要改动附近的内容(例如每次改动潜艇, 同一行`checkval`的值都会变化), 就会产生巨大的单行 diff.
    > `checkval` 是潜艇保存时写入的随机整数, 用于多人战役校验潜艇文件; 本工具不会修改它, 因此每次在游戏中保存后, 根节点仍会出现一行 `checkval` 变化.
1. 此外在 `xml` 中, 由于游戏内部把一些属性当作无序集合保存, 而每次保存潜艇, 这些值的顺序都可能变化, 导致大量无意义 diff.


## 该程序做了什么
将潜艇 `.sub` 文件解压并转成 Git 友好的 `xml` 文件, 也支持将 `xml` 打包成 `.sub`
1. 将预览图单独导出, 并相对链接引用预览图, 以防每次改动潜艇都要巨大的单行 diff.
2. 自动按字母顺序排序下列属性的值, 以防每次保存潜艇顺序改变导致大量无意义 diff
   - Tags
   - requireditem 的 items
   - excludedidentifiers
   - DisallowedUpgrades
   - DisallowAttachingOverTags
   - ContainableRestrictions
   - idcardtags
   - outposttags

---

## 安装教程 (Windows)
> [!tip]
> 要是实在不会, 就把该文档发给 ai, 让 ai 帮忙装.

### 1. 安装 Git for Windows
直接到 Git [官网](https://git-scm.com/install/windows)上下载
### 2. 安装 Python 包管理器
建议使用包管理器 [uv](https://docs.astral.sh/uv/), 打开 CMD/PowerShell:
```bash
winget install uv
# 检查是否安装成功
uv --version
```
安装一个 Python 解释器:
```bash
# 最后一个是版本, 版本不要太低
uv python install 3.13
```
### 3. 安装 Git4SubEditor
运行以下命令进行安装:
```bash
uv tool install git4subeditor
# 检查是否安装成功
uv tool list
git4subeditor --version
```
如果提示找不到命令, 运行以下命令并重启终端后再次尝试:
```bash
uv tool update-shell
```
升级和卸载:
```bash
uv tool upgrade git4subeditor
uv tool uninstall git4subeditor
```

---

## 快速开始
你的潜艇Mod目录位于`Barotrauma\LocalMods\`中, 可以在游戏内的模组选择界面, 点击你的潜艇Mod右侧的"笔"图标快速打开.  
运行这个工具需在当前Mod目录或子目录下打开终端(右键目录背景->在终端中打开), 反正必须确保终端的工作目录是在你要修改的Mod的目录.
### 1. 初始化工作目录
Mod目录中需要有一个 Git 仓库, 如果没有, 可以运行以下命令初始化仓库:
```bash
git init
```
接着运行以下命令, 初始化 git4subeditor 项目:
```bash
git4subeditor init
```
此过程会自动生成/修改 `.gitignore` 文件, 确保 Git 忽略追踪 `*.sub`, `*.bak`, `*.png`, `history` 这4种文件, 你也可以手动添加你要忽略的文件.  
还会生成一个项目配置文件 `git4subeditor.xml`, 里面储存了用户偏好及已注册潜艇信息:
```xml
<?xml version='1.0' encoding='utf-8'?>
<git4subeditor>
  <projectName>test</projectName>
  <language>cn</language>
  <gitRepo>../..</gitRepo>
  <modRoot>../..</modRoot>
  <submarines>
    <submarine name="自定义名称" path="../../test/Git test.sub" preview="../../test/Git test.png" hash="..." />
    <submarine path="../Git test2.sub" preview="../Git test2.png" hash="..." />
    <submarine path="Git test3.sub" preview="Git test3.png" hash="..." />
    <submarine path="tttt/Git test3.sub" preview="tttt/Git test4.png" hash="..." />
  </submarines>
  <update latest="0.2.11" lastCheck="2026111400" interval="24" />
</git4subeditor>
```
### 2. 交互模式
该程序提供 CLI 模式和交互模式, 前者适合 ai 使用, 后者提供了人类可读的界面, 并且交互逻辑更加简单, 还提供了命令补全和历史记录功能, 运行以下命令启动交互模式:
```bash
git4subeditor
```
你将会看到如以下的界面
```
 ██████╗ ██╗████████╗    ██╗  ██╗    by Yinjie
██╔════╝ ██║╚══██╔══╝    ██║  ██║    0.2.11 (20261112)
██║  ███╗██║   ██║       ███████║    无可用更新
██║   ██║██║   ██║       ╚════██║
╚██████╔╝██║   ██║            ██║
 ╚═════╝ ╚═╝   ╚═╝            ╚═╝

███████╗██╗   ██╗██████╗ ███████╗██████╗ ██╗████████╗ ██████╗ ██████╗
██╔════╝██║   ██║██╔══██╗██╔════╝██╔══██╗██║╚══██╔══╝██╔═══██╗██╔══██╗
███████╗██║   ██║██████╔╝█████╗  ██║  ██║██║   ██║   ██║   ██║██████╔╝
╚════██║██║   ██║██╔══██╗██╔══╝  ██║  ██║██║   ██║   ██║   ██║██╔══██╗
███████║╚██████╔╝██████╔╝███████╗██████╔╝██║   ██║   ╚██████╔╝██║  ██║
╚══════╝ ╚═════╝ ╚═════╝ ╚══════╝╚═════╝ ╚═╝   ╚═╝    ╚═════╝ ╚═╝  ╚═╝

项目: test | Git 仓库: ../.. | 模组根目录: ../..
CWD: path_to/current_work_directory
../..
├── ../../test
│   └── Git test.sub
└── ..
    ├── Git test2.sub (M)
    └── .
        ├── Git test3.sub
        └── tttt
            └── Git test4.sub (U)

命令:
  init                        初始化/更新工作区
  show [--tree]               递归搜索并显示仓库下所有潜艇
  export <file.sub> [-o DIR]  解压 .sub 并转为 Git 友好的 XML
  pack <file.xml> [-o FILE]   打包 XML 为 .sub
  unpack <file.sub> [-o DIR]  仅解压 .sub 为原始 XML
  config                      打开工作区配置文件
  github                      前往 Git4SubEditor 项目主页

Tab 补全 · ↑↓ 历史 · Ctrl-R 搜索 · Ctrl-D 退出 · ? 帮助
g4s:test>
```
其中的潜艇 `.sub` 文件目录树, 是以 **Git 仓库**所在目录为根目录递归搜索得到的, 目录以相对路径显示. 示例中的目录结构是为了展示刻意制造的, 不建议搞这么复杂.  
其中未注册潜艇带有绿色标识 `(U)`. 已注册潜艇在初始化或 `export` 时, 会自动计算并记录哈希值到 `git4subeditor.xml` 中, 生成目录树时会再次计算哈希, 若潜艇发生改动, 哈希会发生改变, 发生改动的潜艇带有黄色标识 `(M)`. 已注册但文件缺失的潜艇带有红色标识 `(D)`.
### 3. sub 转 XML
若你的潜艇文件为`test.sub`, 执行命令:
```bash
# 交互模式
export "test.sub"
# CLI 模式
git4subeditor export "test.sub"
```
将会得到2个文件: `test.xml`, `test.png`. 其中`test.xml`就是 Git 要追踪的文件.  
如果已经进行项目初始化(即当前目录有 `git4subeditor.xml`), 可通过以下命令自动导出所有发生改动的已注册 `.sub` 文件:
```bash
# 交互模式
export
# CLI 模式
git4subeditor export
```

### 4. 用 Git 管理 XML
> [!tip]
> 要是实在不会, 就让 ai 帮忙弄, ai 很擅长使用 CLI. 像提交, 回退版本, 比较两个版本的差异, 写提交说明, 都可以问 ai.

该程序不集成操作 Git 仓库的功能, 因为已经有很多成熟的 Git GUI 工具, 重写一遍不仅工作量大, 而且可能还更难用, bug更多, 把仓库搞坏就麻烦了.  
对于不熟悉命令行的小白, 可以安装一些集成了 Git GUI 的 IDE, 用以**可视化差异**与**提交**修改. 我建议用 [VSCode](https://code.visualstudio.com/Download) (选System Installer), Git for Windows 也自带了一个 GUI, 但没那么好用.
关于 Git 的使用, 可以看这个快速入门[教程](https://chriswenchen.github.io/theory-computing-physics-guide/docs/git), 最常用的就几个 CLI 命令:
```bash
# 初始化版本库
git init
# 查看未提交改动(按q退出)
git diff HEAD
# 暂存所有改动
git add .
# 查看状态
git status
# 提交暂存区的内容到版本库
git commit -m "这里写提交说明"
```

### 5. XML 转 sub
如果要回退版本, 用 Git 把 `xml` 回退到指定的版本, 再用以下命令转成 `.sub`文件:
```bash
# 交互模式
pack "test.xml"
# CLI 模式
git4subeditor pack "test.xml"
```
如果 `test.sub` 已存在, 会先备份为: `test.sub.bak` (给你一个后悔的机会), 然后覆盖写入新的 `test.sub`.