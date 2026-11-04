# git4subeditor

把 Barotrauma（潜渊症）的 `.sub` 潜艇文件转换为适合 Git 版本追踪的文本格式。

`.sub` 实际上是 gzip 压缩的单个 XML 文件（文件头 `1F 8B`），本包目前提供解压功能。

## 安装

```bash
pip install -e .
```

或者仅使用开发依赖：

```bash
pip install -e ".[dev]"
```

## 命令行

```bash
git4subeditor "Git test.sub"
git4subeditor "Git test.sub" -o extracted --force
git4subeditor *.sub -o extracted
git4subeditor "Git test.sub" --stdout
```

`sub-unpack` 是同一命令的别名，便于单独调用解压功能。

参数：

- `-o, --output-dir`：输出目录，默认与输入文件同目录
- `--encoding`：强制指定 XML 编码，默认自动检测 UTF-8 / UTF-16
- `--stdout`：把 XML 输出到标准输出，不写文件
- `--no-validate`：跳过 XML 合法性检查
- `-f, --force`：覆盖已存在的输出文件

## Python API

```python
from pathlib import Path

from git4subeditor import unpack_sub

unpack_sub(Path("Git test.sub"), Path("extracted"))
```

## 后续计划

- 格式化 XML 缩进
- 将 `previewimage` 的 Base64 拆分为独立 PNG
- 将文本格式重新打包为 `.sub`
