# git4subeditor

把 Barotrauma（潜渊症）的 `.sub` 潜艇文件转换为适合 Git 版本追踪的文本格式。

## 为什么需要这个工具

`.sub` 实际上是 gzip 压缩的单个 XML 文件（文件头 `1F 8B`）。直接提交 `.sub` 时，
Git 只能看到二进制文件发生了变化，无法审查具体改动。

把 `.sub` 解压成 XML 后还有一个问题：潜艇预览图以 Base64 存放在根节点的
`previewimage` 属性里，往往会让第一行长达几十万字符。只要改动附近的内容，就会
产生巨大的单行 diff。

本工具把 `.sub` 转成同一目录下的一对文件：

- `<name>.xml`：规范化后的 XML，两个空格缩进、LF 换行、每行一个元素
- `<name>.<ext>`：从 `previewimage` 拆出的预览图，通常是 `<name>.png`

XML 根节点不再保存 Base64，而是通过相对链接引用预览图：

```xml
<Submarine name="Git test" preview="Git test.png" ...>
```

`pack` 会把预览图重新写回 `previewimage` 属性，并在覆盖已有 `.sub` 前自动备份为
`<name>.sub.bak`。未修改的 XML 经过 `export -> pack` 后，解压得到的 XML 与原文件
一致（仅换行统一为 LF）。

## 安装

```bash
pip install -e .
```

或者安装开发依赖：

```bash
pip install -e ".[dev]"
```

## 快速开始

```bash
# 1. 在 .sub 旁边导出同名 XML 和预览图
git4subeditor export "Git test.sub"

# 得到：
# Git test.xml
# Git test.png

# 2. 用 Git 管理 XML 和预览图

# 3. 修改 XML 后重新打包
git4subeditor pack "Git test.xml"

# 如果 Git test.sub 已存在，会先备份为：
# Git test.sub.bak
# 然后写入新的 Git test.sub
```

`export` 默认直接输出到输入文件所在目录。`pack` 默认输出到 XML 同目录下的同名
`.sub`；如果目标已存在，会自动备份后覆盖，不需要额外加 `--force`。

## 命令

### export

把 `.sub` 导出为同名 XML 和预览图。

```bash
git4subeditor export "Git test.sub"
git4subeditor export *.sub -o exported
```

| 参数 | 说明 |
| --- | --- |
| `-o, --output-dir` | 输出目录，默认与输入文件同目录 |
| `--sort-attributes` | 按字母顺序排列 XML 属性，跨游戏版本更稳定 |
| `-f, --force` | 覆盖已存在的 XML 或预览图 |

### pack

把导出的 XML 重新打包为 `.sub`。

- 优先读取根节点 `preview` 属性指向的相对路径。
- 如果没有 `preview` 属性，会尝试同目录下的 `<name>.<ext>`、旧的
  `<name>.preview.<ext>` 或 `preview.<ext>`。
- 如果目标 `.sub` 已存在，先复制为 `<目标>.bak`，再写入新文件。
- 使用固定时间戳的 gzip，相同输入会得到相同字节。

```bash
git4subeditor pack "Git test.xml"
git4subeditor pack "Git test.xml" -o "Git test.sub"
```

| 参数 | 说明 |
| --- | --- |
| `-o, --output` | 输出 `.sub` 文件，或一个已存在的目录；默认与 XML 同目录 |
| `--sort-attributes` | 打包前按字母顺序排列 XML 属性 |

### unpack

提取原始 XML，不做规范化，也不拆预览图。适合调试或查看原始内容。

```bash
git4subeditor unpack "Git test.sub"
git4subeditor unpack "Git test.sub" -o extracted --force
git4subeditor unpack "Git test.sub" --stdout
```

| 参数 | 说明 |
| --- | --- |
| `-o, --output-dir` | 输出目录，默认与输入文件同目录 |
| `--encoding` | 强制指定 XML 编码，默认自动检测 UTF-8 / UTF-16 |
| `--stdout` | 把 XML 输出到标准输出，不写文件 |
| `--no-validate` | 跳过 XML 合法性检查 |
| `-f, --force` | 覆盖已存在的输出文件 |

为了兼容旧用法，`git4subeditor "Git test.sub"` 仍然等价于
`git4subeditor unpack "Git test.sub"`。

## Python API

```python
from pathlib import Path

from git4subeditor import export_sub, pack_sub

result = export_sub(Path("Git test.sub"))
print(result.xml_path)
print(result.preview_path)

pack_sub(result.xml_path)
```

## Git 建议

- 只提交 `<name>.xml` 和 `<name>.png`，不要提交 `.sub`。
- 本仓库的 `.gitignore` 默认忽略 `*.sub` 和 `*.bak`，但会正常跟踪 XML 和预览图。
- 本仓库的 `.gitattributes` 把导出的 `*.xml` 固定为 LF 换行，并把 `.sub` 和图片
  标记为二进制。
- 预览图是二进制文件。如果体积较大，可以考虑 Git LFS。

## 注意事项

- `checkval` 是游戏保存时写入的随机整数，用于多人战役校验潜艇文件；本工具不会
  修改它，因此每次在游戏中保存后，根节点仍会出现一行 `checkval` 变化。
- 游戏内部把 `Tags`、`requireditem` 的 `items` 等属性保存为无序集合，重新保存时
  可能整体换序。`export` 和 `pack` 会自动按字母排序这些集合值，避免无意义的
  全文件 diff。首次使用新版本重新导出时，可能产生一次集合排序 diff。
- XML 属性顺序默认保持游戏原样。如果希望跨游戏版本获得更稳定的 diff，可以使用
  `--sort-attributes`；首次启用会产生一次属性顺序 diff。
- `preview` 是相对 XML 所在目录的路径。移动或重命名 XML 时，请一起移动或重命名
  预览图，并同步修改 `preview` 属性。
- 如果没有 `preview` 属性，`pack` 会按扩展名优先级查找同名图片（PNG 优先）。
  不要在同一目录保留多个同名不同扩展名的候选图片。
- 重新打包后建议进入游戏编辑器打开一次，确认潜艇可以正常加载。

## 开发

```bash
uv sync --extra dev
uv run pytest
uv run ruff check .
uv run ruff format --check .
```

## 后续计划

- Git clean/smudge filter，让 `.sub` 在仓库中自动以 XML 形式存储
- XML 结构校验
- 预览图差异可视化
