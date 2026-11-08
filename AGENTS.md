# AGENTS 使用说明
## 本项目
1. 每次更改后给一个简短提交说明, 不要写像版本号变更, 更新本地化这种无用信息
2. 不要修改README.md
3. 每次修改版本号最后一位+1, 如0.0.1->0.0.2, 不要改前2位; 非常小的改动, 或者只改语言文件不要变更版本号
4. 能用标准库中方法简单实现的, 就不要"重新发明轮子"
5. 极其简单的, 以及只使用1次的代码不要封装成函数

## Typing Rules

- Use Python 3.13 style type hints for all new code.
- Add explicit type annotations for variables whenever reasonable, especially:
  - function local variables with non-trivial inferred types
  - return values of helper computations
  - dictionaries, lists, tuples, and numpy arrays
- Do not add a type annotation when the type is obvious from the right-hand side,
  for example `element = str(...)`, `path = Path(...)`, `count = len(...)`.
- Prefer built-in generic syntax:
  - `list[int]`, `dict[str, float]`, `tuple[int, int]`
- Prefer union operator syntax:
  - `str | None` instead of `Optional[str]`
- Keep aliases explicit when needed:
  - `type CitationMap = dict[np.int16, npt.NDArray[np.int16]]`

## Documentation Rules

- All public classes and functions must have docstrings.
- Public methods should also have docstrings.
- Special methods that are not typically called directly (for example `__len__`, `__iter__`, `__getitem__`) do not need per-method docstrings.
- Put usage of such special methods in the class docstring `Examples` section.
- Follow PEP 257 + common structured docstring convention (Google-style sections).
- Each public API docstring should include:
  - brief summary
  - Args
  - Returns (if a func doesn't returns `None`)
  - Raises (if applicable)
  - Examples (when helpful)
- For extremely simple functions, a single-line summary docstring is enough;
  do not expand it into structured sections.
- Class docstrings should include key Attributes.
- Use ASCII punctuation in comments and docstrings in the main program.
  Do not use full-width or other Unicode punctuation marks.

## Naming Rules

- Use unified, concise, and clear naming.
- Use `snake_case` for variables and functions.
- Use `PascalCase` for classes.
- Avoid ambiguous abbreviations unless they are domain-standard (for example `if`).
- Keep naming consistent across parsing, model, and calculation logic.

## Coding style

- Use EAFP style, for example:
  ```python
  # EAFP style
  try:
      x = my_dict['key']
  except KeyError:
      # handle missing key

  # LBYL style
  if 'key' in my_dict:
      x = my_dict['key']
  else:
      # handling missing key
  ```
- Use `pathlib` for all path handling.

## Linting Rules

- Use ruff to lint modified code; see the `ruff` skill for usage details.
