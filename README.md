# Git4SubEditor

一个 CLI 工具, 把 Barotrauma 的 `.sub` 潜艇文件转换为适合 Git 版本追踪的文本格式. 

> [!warning]
> 该程序是 Vibe Coding 的产物, 测试时可能并未覆盖所有可能出现的异常; 如果你打算将此程序应用于你正在开发的项目, 请先进行**备份**, 以免发生不可挽回的灾难性事故

## 为什么需要 Git
1. Git 的版本控制, 并不是每个版本都备份一个副本, 而是记录两个版本间的 diff, 这样不仅版本仓库体积非常小, 而且可以很方便地看出每次都做了哪些改动.
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

## 傻瓜式安装教程 (Windows)
### 1. 安装 Git for Windows
直接到 Git [官网](https://git-scm.com/install/windows)上下载
### 2. 构建 Python 环境(可选)
安装包管理工具 uv, 打开 CMD/PowerShell:
```bash
winget install uv
# 检查是否安装成功
uv --version
```
uv 默认把解释器/包/工具都装在C盘, 如果想改安装目录, 可以改环境变量`UV_CACHE_DIR`, `UV_PYTHON_INSTALL_DIR`, `UV_TOOL_BIN_DIR`, `UV_TOOL_DIR`(改完后需重启终端), 运行以下命令检查是否修改成功:
```bash
uv python dir
uv cache dir
uv tool dir
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

```bash
# 1. 在 .sub 旁边导出同名 XML 和预览图
# 若 XML 已存在, 会询问是否覆盖: 输入 y 覆盖, 其他任意输入跳过
git4subeditor export "test.sub"

# 得到:
# test.xml
# test.png

# 2. 用 Git 管理 XML 和预览图

# 3. 修改 XML 后重新打包
git4subeditor pack "test.xml"

# 如果 test.sub 已存在, 会先备份为:
# test.sub.bak
# 然后写入新的 test.sub
```

`export` 默认直接输出到输入文件所在目录. `pack` 默认输出到 XML 同目录下的同名
`.sub`; 如果目标已存在, 会自动备份后覆盖.

## 命令

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
| `--sort-attributes` | 按字母顺序排列 XML 属性, 跨游戏版本更稳定 |
| `-f, --force` | 跳过覆盖询问, 直接覆盖已存在的 XML 或预览图 |

### pack

把导出的 XML 重新打包为 `.sub`. 

- 优先读取根节点 `preview` 属性指向的相对路径. 
- 如果没有 `preview` 属性, 会尝试同目录下的 `<name>.<ext>`, 旧的
  `<name>.preview.<ext>` 或 `preview.<ext>`. 
- 如果目标 `.sub` 已存在, 先复制为 `<目标>.bak`, 再写入新文件. 
- 使用固定时间戳的 gzip, 相同输入会得到相同字节. 

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

为了兼容旧用法, `git4subeditor "test.sub"` 仍然等价于
`git4subeditor unpack "test.sub"`. 

## Python API

```python
from pathlib import Path

from git4subeditor import export_sub, pack_sub

result = export_sub(Path("test.sub"))
print(result.xml_path)
print(result.preview_path)

pack_sub(result.xml_path)
```

## Git 建议

- 只提交 `<name>.xml` 和 `<name>.png`, 不要提交 `.sub`. 
- 本仓库的 `.gitignore` 默认忽略 `*.sub` 和 `*.bak`, 但会正常跟踪 XML 和预览图. 
- 本仓库的 `.gitattributes` 把导出的 `*.xml` 固定为 LF 换行, 并把 `.sub` 和图片
  标记为二进制. 
- 预览图是二进制文件. 如果体积较大, 可以考虑 Git LFS. 

## 注意事项

- `checkval` 是游戏保存时写入的随机整数, 用于多人战役校验潜艇文件; 本工具不会
  修改它, 因此每次在游戏中保存后, 根节点仍会出现一行 `checkval` 变化. 
- 游戏内部把 `Tags`, `requireditem` 的 `items` 等属性保存为无序集合, 重新保存时
  可能整体换序. `export` 和 `pack` 会自动按字母排序这些集合值, 避免无意义的
  全文件 diff. 首次使用新版本重新导出时, 可能产生一次集合排序 diff. 
- XML 属性顺序默认保持游戏原样. 如果希望跨游戏版本获得更稳定的 diff, 可以使用
  `--sort-attributes`; 首次启用会产生一次属性顺序 diff.
- `preview` 是相对 XML 所在目录的路径. 移动或重命名 XML 时, 请一起移动或重命名
  预览图, 并同步修改 `preview` 属性. 
- 如果没有 `preview` 属性, `pack` 会按扩展名优先级查找同名图片 (PNG 优先).
  不要在同一目录保留多个同名不同扩展名的候选图片. 
- 重新打包后建议进入游戏编辑器打开一次, 确认潜艇可以正常加载. 

## 开发

```bash
uv sync --extra dev
uv run pytest
uv run ruff check .
uv run ruff format --check .
```

## 后续计划

- Git clean/smudge filter, 让 `.sub` 在仓库中自动以 XML 形式存储
- XML 结构校验
- 预览图差异可视化
