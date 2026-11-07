# Git4SubEditor
> Git for Submarine Editor

一个 CLI 工具, 把 Barotrauma 的 `.sub` 潜艇文件转换为适合 Git 版本追踪的文本格式, 也支持将其转回 `.sub` 文件.

> [!warning]
> 这是一个 Vibe Coding 项目, 我正在对代码进行 review 和测试, 但测试可能并未覆盖所有可能出现的异常; 如果你打算将此程序应用于你正在开发的项目, 请先进行**备份**, 以免发生不可挽回的灾难性事故.

> [!note]
> **后续计划**
> - [ ] 我希望能集成一个Git GUI到游戏中, 并直接在潜艇编辑器中可视化不同版本潜艇的差异, 但我不熟悉这个游戏的接口, 也不会C#/Lua, 如果有感兴趣的大佬可以试试.
> - [x] 自动初始化工作区 `git4subeditor init`, 自动添加 `.gitignore` 等
> - [x] 多语言
> - [ ] agent skill, 让 ai 根据 `git diff` 拟定提交说明
> - [ ] 历史记录
> - [ ] Tab 补全

## 为什么需要 Git
1. Git 的版本控制, 并不是每个版本都备份一个副本, 而是记录两个版本间的 diff, 这样不仅版本仓库体积非常小, 而且可以很方便地看出每次都做了哪些改动. 又或者哪天搞砸了, 也可以回退到之前的任意版本.
    > 就像 Git 官网里提到的: "Git 能高效地存储仓库历史. 截至 2025 年, 当前版本的 Linux 内核源代码大小为 1.7 GB. Git 仅用 5.5 GB 就存储了 Linux 项目的完整历史 (140 万次提交)."
2. 可以上传到远程托管平台, 如 Github, Gitee 等, 这是一种更安全的"云同步", 同时也方便进行多人合作开发.

## 为什么需要这个工具

1. `.sub` 实际上是 gzip 压缩的单个 `xml` 文件. 直接提交 `.sub` 时, Git 只能看到二进制文件发生了变化, 无法审查具体改动.
2. 解压后的 `xml` 中, 潜艇预览图是以 Base64 存放在根节点的 `previewimage` 属性里, 往往会让第一行长达几十万字符. 只要改动附近的内容(例如每次改动潜艇, 同一行`checkval`的值都会变化), 就会产生巨大的单行 diff.
3. 此外在 `xml` 中, 由于游戏内部把一些属性当作无序集合保存, 而每次保存潜艇, 这些值的顺序都可能变化, 导致大量无意义 diff.

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

## 安装教程 (Windows)
> [!tip]
> 要是实在不会, 就把该文档发给 ai, 让 ai 帮忙装.

### 1. 安装 Git for Windows
直接到 Git [官网](https://git-scm.com/install/windows)上下载
### 2. 安装 Python 环境(可选)
安装包管理工具 [uv](https://docs.astral.sh/uv/), 打开 CMD/PowerShell:
```bash
winget install uv
# 检查是否安装成功
uv --version
```
uv 默认把解释器/包/工具都装在C盘, 如果想改安装目录, 可以改环境变量`UV_CACHE_DIR`, `UV_PYTHON_INSTALL_DIR`, `UV_TOOL_BIN_DIR`, `UV_TOOL_DIR`, 运行以下命令检查是否修改成功:
```bash
uv python dir
uv cache dir
uv tool dir
```
运行以下命令并重启终端, 来把`UV_TOOL_BIN_DIR`添加到PATH:
```bash
uv tool update-shell
```
安装一个 Python 解释器:
```bash
# 最后一个是版本, 版本不要太低
uv python install 3.15
```
### 3. 安装 Git4SubEditor
从 GitHub 安装到 uv 的独立工具环境, 不会污染 Python 全局环境:

```bash
uv tool install "git4subeditor @ git+https://github.com/Yinjie1/Git4SubEditor.git"
# 检查是否安装成功
uv tool list
git4subeditor --version
```

## 快速开始
### 1. 初始化工作目录
你的潜艇Mod目录就是项目工作目录, 位于`Barotrauma\LocalMods\`中, 也可以在游戏内的模组选择界面, 点击你的潜艇Mod右侧的"笔"图标快速打开.  
首先在目录中新建一个`.gitignore`文件(不要留后缀), 里面填让 Git 忽略的文件, 建议在里面添加这些内容:
```
# 忽略潜艇二进制文件, 否则版本库会变得很大
*.sub 
*.bak
# 一般没必要追踪图片, 也可能导致版本库变得很大
*.png
```
运行这个工具需在当前潜艇Mod目录打开终端(右键目录背景->在终端中打开), 反正必须确保终端的工作目录是在你要修改的Mod的目录
### 2. sub 转 XML
若你的潜艇文件为`test.sub`, 执行命令:
```bash
git4subeditor export "test.sub"
```
将会得到2个文件: `test.xml`, `test.png`. 其中`test.xml`就是 Git 要追踪的文件.  
默认直接输出到输入文件所在目录, 若 `xml` 已存在, 会询问是否覆盖: 输入 `y` 覆盖, 其他任意输入跳过

### 2. 用 Git 管理 XML
> [!tip]
> 要是实在不会, 就让 ai 帮忙弄, ai 都懂 Git 命令. 像提交, 回退版本, 比较两个版本的差异, 都可以问 ai.

关于 Git 的使用, 可以看这个快速入门[教程](https://chriswenchen.github.io/theory-computing-physics-guide/docs/git), 最常用的就几个命令:
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

对于不熟悉命令行的小白, 可以安装一些集成了 Git GUI 的 IDE, 如 [VSCode](https://code.visualstudio.com/Download), 来可视化差异与提交修改.
### 3. XML 转 sub
如果要回退版本, 用 Git 把 `xml` 回退到指定的版本, 再用以下命令转成 `.sub`文件:
```bash
git4subeditor pack "test.xml"
```
如果 `test.sub` 已存在, 会先备份为: `test.sub.bak`, 然后覆盖写入新的 `test.sub`

## 命令

### init

在当前工作目录创建或更新 `.gitignore`. 

```bash
git4subeditor init
```

- 文件不存在时, 新建文件并写入 `*.sub`, `*.bak`, `*.png`. 
- 文件已存在时, 检查这三项; 缺少的项会追加到文件末尾, 并用
  `# ===== Git4SubEditor =====` 标记. 
- 三项都已忽略时, 不修改文件. 

### export

把 `.sub` 导出为同名 XML 和预览图. 

```bash
git4subeditor export "test.sub"
git4subeditor export *.sub -o exported
```

如果同名 XML 已存在, 默认会询问是否覆盖. 输入 `y` 表示覆盖, 输入其他任意内容
表示跳过当前文件. 使用 `--force` 时不询问, 直接覆盖.

| 参数 | 说明 |
| --- | --- |
| `-o, --output-dir` | 输出目录, 默认与输入文件同目录 |
| `--sort-attributes` | 按字母顺序排列 XML 属性本身；Tags、items 等集合值始终排序 |
| `-f, --force` | 跳过覆盖询问, 直接覆盖已存在的 XML 或预览图 |

### pack

把导出的 XML 重新打包为 `.sub`. 

- 读取根节点 `preview` 属性指向的相对路径. 
- 如果目标 `.sub` 已存在, 先复制为 `<目标>.bak`, 再写入新文件. 

```bash
git4subeditor pack "test.xml"
git4subeditor pack "test.xml" -o "test.sub"
```

| 参数 | 说明 |
| --- | --- |
| `-o, --output` | 输出 `.sub` 文件, 或一个已存在的目录; 默认与 XML 同目录 |
| `--sort-attributes` | 打包前按字母顺序排列 XML 属性 |

### unpack

提取原始 XML, 不做规范化, 也不拆预览图. 适合调试或查看原始内容. 

```bash
git4subeditor unpack "test.sub"
git4subeditor unpack "test.sub" -o extracted --force
git4subeditor unpack "test.sub" --stdout
```

| 参数 | 说明 |
| --- | --- |
| `-o, --output-dir` | 输出目录, 默认与输入文件同目录 |
| `--encoding` | 强制指定 XML 编码, 默认自动检测 UTF-8 / UTF-16 |
| `--stdout` | 把 XML 输出到标准输出, 不写文件 |
| `--no-validate` | 跳过 XML 合法性检查 |
| `-f, --force` | 覆盖已存在的输出文件 |

必须显式指定子命令, 例如 `git4subeditor unpack "test.sub"`. 直接传入文件名会
报参数错误. 

## 注意事项

- `checkval` 是游戏保存时写入的随机整数, 用于多人战役校验潜艇文件; 本工具不会
  修改它, 因此每次在游戏中保存后, 根节点仍会出现一行 `checkval` 变化. 
- 游戏内部把 `Tags`, `requireditem` 的 `items` 等属性保存为无序集合, 重新保存时
  可能整体换序. `export` 和 `pack` 会自动按字母排序这些集合值, 避免无意义的
  全文件 diff. 首次使用新版本重新导出时, 可能产生一次集合排序 diff. 
- `preview` 是相对 XML 所在目录的路径. 移动或重命名 XML 时, 请一起移动或重命名
  预览图, 并同步修改 `preview` 属性. 
- 如果 `preview` 指向的图片不存在, `pack` 会输出警告并省略预览图, 不会搜索
  其他图片. 
- 重新打包后建议进入游戏编辑器打开一次, 确认潜艇可以正常加载.