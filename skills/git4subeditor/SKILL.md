---
name: git4subeditor
description: Convert Barotrauma submarine `.sub` files into Git-friendly XML and back with the `git4subeditor` CLI. Use this skill whenever the user works on a Barotrauma submarine mod inside a Git repository: initializing a mod workspace, exporting `.sub` to XML after editing a submarine in game, packing an XML back into `.sub`, checking which submarines changed, reviewing `git diff` of submarine XML, writing commit messages for submarine changes, or restoring an older submarine version. Especially use it when the user mentions Barotrauma, submarine mods, `.sub` files, `git4subeditor`, or asks why a submarine XML diff is huge or unreadable.
compatibility: Requires the `git4subeditor` CLI and `git`. Ask the user before installing anything.
metadata:
  author: Yinjie
  version: '1.2'
  repository: https://github.com/Yinjie1/Git4SubEditor
---

# Git4SubEditor

`.sub` 是 gzip 压缩的单个 XML,直接提交 Git 只能看到二进制变化。`git4subeditor` 把它转成可 diff 的 XML(预览图单独导出、无序集合属性按字母排序),改完再打包回 `.sub`。

## 工作流程

按下面的顺序走,每一步先看命令结果,再决定下一步。所有命令都在 Mod 目录或其子目录执行。

### 1. 确认工具可用

运行 `git4subeditor --version`。找不到命令就停下来问用户是否安装,同意后再 `uv tool install git4subeditor`(装完仍提示找不到命令,再 `uv tool update-shell` 并重开终端)。未经同意不要安装或升级。

### 2. 先看当前状态

运行 `git4subeditor show`。每行一个潜艇路径,可能带标记:

- `(M)` 黄色:游戏内改过,但还没导出成 XML
- `(U)` 绿色:仓库里有这个 `.sub`,但没登记进 `git4subeditor.xml`
- `(D)` 红色:已登记,但磁盘上找不到这个文件
- 没有标记:已登记且未改动

`git4subeditor show xml` 列出 `git4subeditor.xml` 中记录的 XML 路径,文件缺失时末尾同样标红色 `(D)`;加 `--tree` 以目录树显示。二者都可以传扩展名,默认是 `sub`。

退出码为 1 并提示工作区未初始化时,说明还没有 `git4subeditor.xml`,进入第 3 步;否则跳过第 3 步。

### 3. 首次初始化(只在没有 git4subeditor.xml 时)

先问用户两件事:选哪种语言(cn/en/ru)、是否登记 `show` 列出的潜艇。得到答复后运行 `git4subeditor init`,把答复按顺序传给它的提示(写法见"给命令传答复")。

初始化完成后必须显式导出:此时所有 `.sub` 的哈希刚被记为基线,`export` 不给输入时找不到"已改动"的潜艇。把路径逐个列出来导出:

```bash
git4subeditor export "test/A.sub" "test/B.sub"
```

然后 `git add` 并提交初始 XML。`.gitignore` 已由 `init` 写好,`*.sub`、`*.bak`、`*.png`、`history` 都不进仓库。

### 4. 日常:游戏里改完潜艇后

1. 运行 `git4subeditor export`。它会先列出将要导出的潜艇,再问 `[y/N]`;把清单转述给用户,确认后再回答。
2. 用 `git status --short` 和 `git diff -- "*.xml"` 看改了什么。
3. 按改动写中文提交说明,格式 `type(scope): 说明`,例如 `feat(sub): 新增医疗舱与自动门`。概括这次改动的目的,不要罗列每处 diff,也不要写"更新 XML",更不要写"更新 checkval 属性"。
4. 提交。

**导出前不要运行 `init`**。`init` 会把当前 `.sub` 的哈希直接记成新基线,之后再 `export` 就看不到这些改动,新内容永远进不了 XML。

### 5. 发现未注册潜艇

`show` 输出里出现 `(U)` 时,把文件列给用户并询问是否登记。用户同意后,先导出已有的 `(M)` 改动,再运行 `git4subeditor init` 登记新文件。

`init` 还可能单独询问 MOD 根目录变更、Git 仓库路径变更、同名潜艇、移除已消失的潜艇,每一项都要先问用户,不要替他决定。

### 6. 回退到旧版本

```bash
git checkout COMMIT_SHA -- "test.xml"
git4subeditor pack "test.xml"
```

生成的新 `.sub` 会覆盖原文件,原文件先备份为 `.sub.bak`。已登记且配置了 `xml` 属性的 `.sub` 也可以直接 `git4subeditor pack "test.sub"`。回到游戏里重新加载潜艇后生效。

## 给命令传答复

命令需要确认时,先把提示原样转述给用户,得到答复后按当前 shell 传递:

| Shell | 一个答复 | 多个答复 |
| --- | --- | --- |
| bash / zsh | `printf 'y\n' \| git4subeditor pack "test.xml"` | `printf 'y\ny\n' \| git4subeditor init` |
| cmd.exe | `echo y\| git4subeditor pack "test.xml"` | `(echo y& echo y)\| git4subeditor init` |
| PowerShell | `'y' \| git4subeditor pack "test.xml"` | `'y','y' \| git4subeditor init` |

- cmd 的 `echo y` 会带一个尾随空格,程序会去掉;`echo y` 与 `|` 之间不要加空格。
- `input()` 读到 EOF 等同于回答"否",对应步骤会被静默跳过。命令跑完发现没导出、没登记,就是答复数量不够,补上再跑。
- 语言选择只在配置里没有有效 `<language>` 时出现,必须由用户决定。

## 容易出错的地方

- 不要用 `-f` / `--force`,也不要运行交互模式:不带参数的 `git4subeditor`,以及只有交互模式才有的 `config`、`github`、`?`。
- `checkval` 是游戏保存时写入的随机整数,每次保存都会变,属于正常现象,不要试图修掉。
- `git4subeditor.xml` 的 `<submarines>` 以 `path` 为标识,`name` 是可选项且不参与输出,识别潜艇用路径。
- `<update latest="…" lastCheck="…" interval="…" />` 是版本检查缓存,不需要手工维护。
- 同名 `.sub` 会被分别登记,导出和打包时按具体路径操作,避免弄错文件。
