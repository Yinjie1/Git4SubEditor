---
name: git4subeditor
description: Convert Barotrauma submarine `.sub` files into Git-friendly XML and back with the `git4subeditor` CLI. Use this skill whenever the user works on a Barotrauma submarine mod inside a Git repository: initializing a mod workspace, exporting `.sub` to XML after editing a submarine in game, packing an XML back into `.sub`, checking which submarines changed, reviewing `git diff` of submarine XML, writing commit messages for submarine changes, or restoring an older submarine version. Especially use it when the user mentions Barotrauma, submarine mods, `.sub` files, `git4subeditor`, or asks why a submarine XML diff is huge or unreadable.
compatibility: Requires the `git4subeditor` CLI (`uv tool install git4subeditor`) and `git`.
metadata:
  author: Yinjie
  version: '1.0'
  repository: https://github.com/Yinjie1/Git4SubEditor
---

# Git4SubEditor

`git4subeditor` 把 Barotrauma 的 `.sub` 潜艇文件(gzip 压缩的 XML)转换成便于 Git 追踪的 XML,也能把 XML 打包回 `.sub`。
转换会剥离并单独导出预览图、按字母顺序规范化无序集合属性,从而避免巨大的单行 diff 和无意义 diff。

## 硬性规则:只用 CLI 模式

始终带上子命令调用,例如 `git4subeditor export "test.sub"`。

不要运行不带参数的 `git4subeditor`:它启动交互模式 REPL,在非 TTY 环境会直接报错退出,也会阻塞自动化流程。
交互模式专有的东西一律不要使用:裸命令、`tree`、`setting`(会用默认程序打开配置文件)、`github`、`?`。

## 环境确认

```bash
git4subeditor --version
uv tool list
```

没有安装时:

```bash
uv tool install git4subeditor
uv tool upgrade git4subeditor
uv tool update-shell   # 安装后提示找不到命令时执行, 然后重开终端
```

所有命令都必须在 Mod 目录或其子目录下执行,项目配置 `git4subeditor.xml` 位于工作目录。

## 命令一览

| 命令 | 作用 |
| --- | --- |
| `git4subeditor init [-f]` | 初始化/更新工作区:写入 `.gitignore` 与 `git4subeditor.xml`,注册仓库内的 `.sub` |
| `git4subeditor sub [--tree]` | 列出已注册潜艇,`(U)` 未注册,`(M)` 已改动 |
| `git4subeditor export [inputs...] [-o DIR] [-f] [--sort-attributes]` | `.sub` 导出为 XML 和预览图;不给输入时导出所有已改动的已注册潜艇 |
| `git4subeditor pack inputs... [-o FILE\|DIR] [--sort-attributes]` | XML 打包回 `.sub`;输入也可以是已注册的 `.sub`,此时按其 `xml` 属性打包 |
| `git4subeditor unpack inputs... [-o DIR] [--stdout] [-f]` | 只解压 `.sub` 为原始 XML,很少使用 |

退出码:`0` 成功,`1` 处理失败,`2` 用法错误。

## 非交互约定

- `init`、`export`、`unpack` 都有 `-f`,自动化时一律加上,否则会等待 `[y/N]` 或语言选择。
- `pack` 没有 `--force`。目标 `.sub` 存在未提交改动时会询问是否覆盖,需要确认时用 `echo y | git4subeditor pack "test.xml"`。`pack` 覆盖前会把原文件备份成 `.sub.bak`。
- 输出语言由 `git4subeditor.xml` 里的 `<language>` 决定(`cn`/`en`/`ru`),不影响命令行为。
- `init` 会做一次联网版本检查(最多约 2 秒),失败只影响 banner 提示,不影响初始化。

## 首次初始化

```bash
git init                      # 仓库不存在时
git4subeditor init -f
git4subeditor export -f       # 导出全部已注册潜艇
git add .gitignore git4subeditor.xml *.xml
git commit -m "chore: 初始化潜艇版本追踪"
```

`init` 会自动把 `*.sub`、`*.bak`、`*.png`、`history` 写进 `.gitignore`,所以 Git 只跟踪 XML 与 `git4subeditor.xml`,预览图不进仓库。

## 游戏内改完潜艇后

```bash
git4subeditor export -f       # 只导出哈希变化的已注册潜艇
git status --short
git diff -- '*.xml'
```

要点:

- 先在游戏里保存潜艇,再导出;导出会重新计算哈希并写入配置。
- **不要在这之前运行 `init`**。`init` 会把当前 `.sub` 的哈希直接记成新基线,之后 `export` 就认不出这些改动,新内容不会被导进 XML。
- 只导出一个指定潜艇时传路径:`git4subeditor export "test/My Sub.sub"`。路径含空格必须加引号。

## 回退到历史版本

```bash
git checkout <commit> -- "test.xml"
git4subeditor pack "test.xml"          # 生成 test.sub, 原文件备份为 test.sub.bak
git4subeditor pack "test.sub"          # 已注册 .sub 且配置了 xml 属性时, 按其 xml 打包
```

打包后需要在游戏里重新加载潜艇,才能看到回退后的效果。

## 写提交说明

该项目的提交说明使用中文,格式为 `type(scope): 说明`,直接用 `git diff -- '*.xml'` 的内容概括改动:

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
- `(M)` 表示 `.sub` 的哈希与配置里记录的不一致,即游戏内改动还没导出;`(U)` 表示文件存在但未注册,运行 `init -f` 可登记。
- `git4subeditor.xml` 的 `<submarines>` 以 `path` 为标识,`name` 是可选属性且不参与输出显示,识别潜艇时用路径。
- `<update latest="…" lastCheck="…" interval="…" />` 是版本检查缓存(`lastCheck` 为 UTC 的 `yyyymmddHH`,`interval` 单位为小时),不需要手工维护。
- 同名的 `.sub` 会被当作不同潜艇分别注册,路径不同即可;导出/打包时按具体路径操作,避免打错文件。
