# git4subeditor

把 Barotrauma（潜渊症）的 `.sub` 潜艇文件转换为适合 Git 版本追踪的文本格式。

## 为什么需要这个工具

`.sub` 实际上是 gzip 压缩的单个 XML 文件（文件头 `1F 8B`）。直接提交 `.sub` 时，
Git 只能看到二进制文件发生了变化，无法审查具体改动。

把 `.sub` 解压成 XML 后还有一个问题：潜艇预览图以 Base64 存放在根节点的
`previewimage` 属性里，往往会让第一行长达几十万字符。只要改动附近的内容，就会
产生巨大的单行 diff。

本工具把 `.sub` 转成一个小型文本包：

- `<name>.xml`：规范化后的 XML，两个空格缩进、LF 换行、每行一个元素
- `<name>.preview.*`：从 `previewimage` 拆出的预览图，通常是 `.png`

`pack` 可以把文本包重新打包成游戏可读取的 `.sub`。未修改的 XML 经过
`export -> pack` 后，解压得到的 XML 与原文件一致（仅换行统一为 LF）。

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
# 1. 导出为 Git 友好格式
git4subeditor export "Git test.sub" -o exported

# 得到：
# exported/Git test.xml
# exported/Git test.preview.png

# 2. 用 Git 管理导出的 XML 和预览图

# 3. 修改 XML 后重新打包
git4subeditor pack "exported/Git test.xml" -o rebuilt.sub
```

`pack` 默认输出到 XML 同目录下的同名 `.sub`。如果目标文件已存在（例如直接覆盖
原始 `.sub`），需要加 `-f/--force`。

## 命令

### export

把 `.sub` 导出为 XML 加预览图。

```bash
git4subeditor export "Git test.sub" -o exported
git4subeditor export *.sub -o exported
```

| 参数 | 说明 |
| --- | --- |
| `-o, --output-dir` | 输出目录，默认与输入文件同目录 |
| `--sort-attributes` | 按字母顺序排列 XML 属性，跨游戏版本更稳定 |
| `-f, --force` | 覆盖已存在的输出文件 |

### pack

把导出的 XML 重新打包为 `.sub`。如果 XML 根节点没有 `previewimage`，会自动读取
同目录下的 `<name>.preview.*` 或 `preview.*` 图片并写回。

```bash
git4subeditor pack "exported/Git test.xml"
git4subeditor pack "exported/Git test.xml" -o "Git test.sub"
```

| 参数 | 说明 |
| --- | --- |
| `-o, --output` | 输出 `.sub` 文件，或一个已存在的目录；默认与 XML 同目录 |
| `--sort-attributes` | 打包前按字母顺序排列 XML 属性 |
| `-f, --force` | 覆盖已存在的输出文件 |

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

result = export_sub(Path("Git test.sub"), Path("exported"))
print(result.xml_path)
print(result.preview_path)

pack_sub(result.xml_path, Path("rebuilt.sub"), force=True)
```

## Git 建议

- 只提交 `<name>.xml` 和 `<name>.preview.png`，不要提交 `.sub`。
- 本仓库的 `.gitignore` 默认忽略 `*.sub` 和 `*.png`，但已放行 `*.preview.png`。
- 本仓库的 `.gitattributes` 把导出的 `*.xml` 固定为 LF 换行，并把 `.sub` 和图片
  标记为二进制。
- 预览图是二进制文件。如果体积较大，可以考虑 Git LFS。

## 注意事项

- `checkval` 是游戏保存时写入的随机整数，用于多人战役校验潜艇文件；本工具不会
  修改它。
- 属性顺序默认保持游戏原样。如果希望跨游戏版本获得更稳定的 diff，可以使用
  `--sort-attributes`；首次启用会产生一次全量 diff。
- 同一个 XML 旁边不要保留多个 `<name>.preview.*` 文件；`pack` 会按扩展名优先级
  选择（PNG 优先）。如果 XML 根节点已经有 `previewimage`，旁边的图片会被忽略。
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
