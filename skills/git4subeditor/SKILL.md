---
name: git4subeditor
description: Convert Barotrauma submarine `.sub` files into Git-friendly XML and back with the `git4subeditor` CLI. Use this skill whenever the user works on a Barotrauma submarine mod inside a Git repository: initializing a mod workspace, exporting `.sub` to XML after editing a submarine in game, packing an XML back into `.sub`, checking which submarines changed, reviewing `git diff` of submarine XML, writing commit messages for submarine changes, or restoring an older submarine version. Especially use it when the user mentions Barotrauma, submarine mods, `.sub` files, `git4subeditor`, or asks why a submarine XML diff is huge or unreadable.
compatibility: Requires the `git4subeditor` CLI and `git`. Ask the user before installing anything.
metadata:
  author: Yinjie
  version: '1.1'
  repository: https://github.com/Yinjie1/Git4SubEditor
---

# Git4SubEditor

`git4subeditor` 把 Barotrauma 的 `.sub` 潜艇文件(gzip 压缩的 XML)转换成便于 Git 追踪的 XML,也能把 XML 打包回 `.sub`。
转换会剥离并单独导出预览图、按字母顺序规范化无序集合属性,从而避免巨大的单行 diff 和无意义 diff。

## 硬性规则

始终带上子命令调用,例如 `git4subeditor export "test.sub"`。

不要运行不带参数的 `git4subeditor`:它启动交互模式 REPL,在非 TTY 环境会直接报错退出,也会阻塞自动化流程。
交互模式专有的东西一律不要使用:裸命令、`tree`、`setting`(会用默认程序打开配置文件)、`github`、`?`。

不要使用 `-f` / `--force`。所有确认、语言选择都必须由用户决定,你负责把提示转述给用户并询问,然后把用户的答复作为输入传给命令(见下文"回答提示")。

## 环境确认

```bash
git4subeditor --version
```

找不到命令时**先询问用户是否安装**,得到同意后再执行:

```bash
uv tool install git4subeditor
uv tool update-shell   # 安装后仍提示找不到命令时执行, 然后重开终端
```

不要在用户未同意时安装或升级工具。

所有命令都在 Mod 目录或其子目录下执行,项目配置 `git4subeditor.xml` 位于工作目录。

## 命令一览

| 命令 | 作用 |
| --- | --- |
| `git4subeditor init` | 初始化/更新工作区:写入 `.gitignore` 与 `git4subeditor.xml`,登记仓库内的 `.sub` |
| `git4subeditor sub [--tree]` | 列出已注册潜艇,`(U)` 未注册,`(M)` 已改动 |
| `git4subeditor export [inputs...] [-o DIR] [--sort-attributes]` | `.sub` 导出为 XML 和预览图;不给输入时导出所有已改动的已注册潜艇 |
| `git4subeditor pack inputs... [-o FILE\|DIR] [--sort-attributes]` | XML 打包回 `.sub`;输入也可以是已注册的 `.sub`,此时按其 `xml` 属性打包 |
| `git4subeditor unpack inputs... [-o DIR] [--stdout]` | 只解压 `.sub` 为原始 XML,很少使用 |

退出码:`0` 成功,`1` 处理失败,`2` 用法错误。

## 回答提示

`init`、`export`、`unpack`、`pack` 都可能停下来等待输入。做法是:先把提示和受影响文件清单转述给用户,征得同意后,再按当前 shell 的写法把答复传给命令。

| Shell | 传入一个 `y` | 传入多个答复 |
| --- | --- | --- |
| bash / zsh | `printf 'y\n' \| git4subeditor pack "test.xml"` | `printf 'y\ny\n' \| git4subeditor init` |
| cmd.exe | `echo y\| git4subeditor pack "test.xml"` | `(echo y& echo y)\| git4subeditor init` |
| PowerShell | `'y' \| git4subeditor pack "test.xml"` | `'y','y' \| git4subeditor init` |

- cmd 的 `echo y` 会在答复末尾多一个空格,程序会去掉首尾空白;`echo y` 与 `|` 之间不要加空格。
- 语言选择(`cn`/`en`/`ru`)只在配置里没有有效 `<language>` 时出现,必须让用户自己选。
- `input()` 读到 EOF 等同于回答"否",对应步骤会被跳过且不打印成功信息。发现命令没有真正导出或登记,说明答复数量不够,把实际情况告诉用户后补上再运行。
- 想了解当前状态用 `git4subeditor sub --tree`,它只读不写。

## 只在缺少配置时初始化

先查看当前状态(只读):

```bash
git4subeditor sub --tree
```

- 退出码为 `0` 且有输出:配置已存在,**不要运行 `init`**,直接按下面的导出与提交流程操作。
- 退出码为 `1` 且提示工作区未初始化:缺少 `git4subeditor.xml`,需要初始化。先询问用户是否登记仓库里的潜艇、用哪种语言,再执行 `git4subeditor init`,并按上表写法传入语言和确认答复。

登记完成后,**自动导出不会做任何事**:`init` 已经把当前 `.sub` 的哈希记成基线,`export` 无输入时只导出哈希变化的潜艇。首次导出要显式列出路径(路径取自 `git4subeditor sub --tree` 的输出或目录清单):

```bash
git4subeditor export "test/My Sub1.sub" "test/My Sub2.sub"
```

`init` 会自动把 `*.sub`、`*.bak`、`*.png`、`history` 写进 `.gitignore`,所以 Git 只跟踪 XML 与 `git4subeditor.xml`,预览图不进仓库。

## 游戏内改完潜艇后

```bash
git4subeditor export            # 提示确认时先问用户
git status --short
git diff -- "*.xml"
```

要点:

- 先在游戏里保存潜艇,再导出;导出会重新计算哈希并写入配置。
- **不要在这之前运行 `init`**。`init` 会把当前 `.sub` 的哈希直接记成新基线,之后 `export` 就认不出这些改动,新内容不会被导进 XML。
- 只导出一个指定潜艇时传路径:`git4subeditor export "test/My Sub.sub"`。路径含空格必须加引号。

## 发现未注册潜艇时

`git4subeditor sub --tree` 输出里出现 `(U)` 标记,说明仓库里有 `.sub` 还没登记。

1. 把带 `(U)` 的文件列给用户,询问是否添加。
2. 用户同意后,先处理已有的 `(M)` 改动(先导出,再 `init`),否则 `init` 会把它们的当前哈希记成基线。
3. 询问用户同意后执行 `git4subeditor init`,并按上表写法把 `y` 传给它的确认提示。如果命令还问了别的确认项(修改 MOD 根目录、Git 仓库路径、同名潜艇、移除已消失的潜艇),同样逐项询问用户后再补上答复重跑。

## 回退到历史版本

```bash
git checkout COMMIT_SHA -- "test.xml"
git4subeditor pack "test.xml"          # 生成 test.sub, 原文件备份为 test.sub.bak
git4subeditor pack "test.sub"          # 已注册 .sub 且配置了 xml 属性时, 按其 xml 打包
```

打包后需要在游戏里重新加载潜艇,才能看到回退后的效果。

## 写提交说明

该项目的提交说明使用中文,格式为 `type(scope): 说明`,直接用 `git diff -- "*.xml"` 的内容概括改动:

- 新增部件、房间、物品用 `feat`
- 调整数值、接线、布局用 `fix` 或 `refactor`
- 仅格式规范化(属性排序)用 `style`

示例:

```text
feat(sub): 新增医疗舱与自动门
fix(sub): 修正反应堆输出功率过低
refactor(sub): 重排引擎室布线
```

一句话概括这次改动的目的,不要逐条罗列 diff,也不要写"更新 XML"这类无信息说明。

## 注意事项

- `checkval` 是游戏保存时写入的随机整数,每次保存都会变。这是正常现象,不要试图"修复"或提交时剔除。
- `(M)` 表示 `.sub` 的哈希与配置里记录的不一致,即游戏内改动还没导出;`(U)` 表示文件存在但未注册。
- `git4subeditor.xml` 的 `<submarines>` 以 `path` 为标识,`name` 是可选属性且不参与输出显示,识别潜艇时用路径。
- `<update latest="…" lastCheck="…" interval="…" />` 是版本检查缓存(`lastCheck` 为 UTC 的 `yyyymmddHH`,`interval` 单位为小时),不需要手工维护。
- 同名 `.sub` 会被当作不同潜艇分别注册,路径不同即可;导出/打包时按具体路径操作,避免打错文件。
