"""Initialize project files for a Barotrauma submarine workspace."""

import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

from git4subeditor import __version__

IGNORE_PATTERNS: tuple[str, ...] = ("*.sub", "*.bak", "*.png")


class InitializeError(Exception):
    """Raised when a workspace cannot be recognized as a Barotrauma mod."""


@dataclass(frozen=True, slots=True)
class InitResult:
    """Result of initializing a submarine workspace.

    Attributes:
        gitignore_path: Path to the .gitignore file.
        config_path: Path to the project configuration file.
        added: Ignore patterns added to .gitignore by this call.
        gitignore_created: Whether the .gitignore file was created.
        config_created: Whether the project configuration file was created.
        config_updated: Whether the project configuration file was rewritten.
        git_repository_path: Repository path relative to the workspace, or an
            empty string when no repository was found.
        current_git_repository: Whether the workspace itself is a repository
            root.
        upper_git_repository_path: Path to an upper-level repository relative
            to the workspace, or None when no upper-level repository exists.
    """

    gitignore_path: Path
    config_path: Path
    added: tuple[str, ...]
    gitignore_created: bool
    config_created: bool
    config_updated: bool
    git_repository_path: str
    current_git_repository: bool
    upper_git_repository_path: str | None


def initialize_project(directory: Path | None = None) -> InitResult:
    """Initialize a workspace with .gitignore and project configuration.

    A new .gitignore contains the required ignore patterns directly. When an
    existing file is missing patterns, they are appended in a marked block.
    Existing content is never rewritten.

    Existing user preferences are preserved. The ``gitRepo``, ``modRoot``,
    and ``version`` fields are updated. The project name is taken from the
    nearest ancestor directory containing ``filelist.xml``.

    Args:
        directory: Workspace directory. Defaults to the current working
            directory.

    Returns:
        Details about the created or updated files.

    Raises:
        InitializeError: If no ``filelist.xml`` exists in the directory or any
            of its ancestors.
        OSError: If a file cannot be read or written.

    Examples:
        >>> result = initialize_project(Path("MySubmarine"))
        >>> result.gitignore_created
        True
        >>> result.added
        ('*.sub', '*.bak', '*.png')
    """
    base: Path = directory if directory is not None else Path.cwd()
    mod_root: Path = _find_mod_root(base)
    repository_path, current_repository, upper_repository = _find_git_repository(
        base, mod_root
    )
    project_name: str = mod_root.name or str(mod_root)
    mod_root_path: str = _relative_path(base.resolve(), mod_root)
    gitignore_path, added, gitignore_created = _update_gitignore(base)
    config_path, config_created, config_updated = _create_project_config(
        base, project_name, repository_path, mod_root_path
    )
    return InitResult(
        gitignore_path=gitignore_path,
        config_path=config_path,
        added=added,
        gitignore_created=gitignore_created,
        config_created=config_created,
        config_updated=config_updated,
        git_repository_path=repository_path,
        current_git_repository=current_repository,
        upper_git_repository_path=upper_repository,
    )


def _update_gitignore(base: Path) -> tuple[Path, tuple[str, ...], bool]:
    """Create or update .gitignore and return its path, additions, and state."""
    path: Path = base / ".gitignore"

    try:
        with path.open("r", encoding="utf-8", newline="") as handle:
            text: str = handle.read()
    except FileNotFoundError:
        content: str = "".join(f"{pattern}\n" for pattern in IGNORE_PATTERNS)
        path.write_text(content, encoding="utf-8", newline="\n")
        return path, IGNORE_PATTERNS, True

    existing: set[str] = {line.strip() for line in text.splitlines()}
    added: tuple[str, ...] = tuple(
        pattern for pattern in IGNORE_PATTERNS if pattern not in existing
    )
    if not added:
        return path, (), False

    newline: str = "\r\n" if "\r\n" in text else "\n"
    chunks: list[str] = []
    if text and not text.endswith(("\n", "\r")):
        chunks.append(newline)
    chunks.append(f"# ===== Git4SubEditor ====={newline}")
    chunks.extend(f"{pattern}{newline}" for pattern in added)

    with path.open("a", encoding="utf-8", newline="") as handle:
        handle.write("".join(chunks))

    return path, added, False


def _find_mod_root(base: Path) -> Path:
    """Return the nearest directory containing filelist.xml."""
    current: Path = base.resolve()
    for directory in (current, *current.parents):
        if (directory / "filelist.xml").is_file():
            return directory
    raise InitializeError(
        f"not a Barotrauma MOD project: filelist.xml not found in "
        f"{current} or its parent directories"
    )


def _find_git_repository(base: Path, mod_root: Path) -> tuple[str, bool, str | None]:
    """Find repositories from the workspace up to the mod root."""
    current: Path = base.resolve()
    repositories: list[Path] = []
    for directory in (current, *current.parents):
        if (directory / ".git").exists():
            repositories.append(directory)
        if directory == mod_root:
            break

    if not repositories:
        return "", False, None

    if repositories[0] == current:
        upper: str | None = None
        if len(repositories) > 1:
            upper = _relative_path(current, repositories[1])
        return ".", True, upper

    return _relative_path(current, repositories[0]), False, None


def _relative_path(current: Path, target: Path) -> str:
    """Return a portable relative path from the workspace to the target."""
    depth: int = len(current.relative_to(target).parts)
    return "/".join([".."] * depth) or "."


def _create_project_config(
    base: Path,
    project_name: str,
    repository_path: str,
    mod_root_path: str,
) -> tuple[Path, bool, bool]:
    """Create or update the project configuration file."""
    path: Path = base / "git4subeditor.xml"
    try:
        parser = ET.XMLParser(target=ET.TreeBuilder(insert_comments=True))
        root: ET.Element = ET.parse(path, parser=parser).getroot()
    except FileNotFoundError:
        root = ET.Element("git4subeditor")
        _set_config_value(root, "projectName", project_name)
        _set_config_value(root, "language", "")
        _set_config_value(root, "gitRepo", repository_path)
        _set_config_value(root, "modRoot", mod_root_path)
        _set_config_value(root, "version", __version__)
        _write_project_config(path, root)
        return path, True, False
    except ET.ParseError as exc:
        raise InitializeError(f"invalid project configuration {path}: {exc}") from exc

    changed: bool = False
    legacy: ET.Element | None = root.find("gitRepository")
    if legacy is not None:
        root.remove(legacy)
        changed = True
    changed |= _set_config_value(root, "gitRepo", repository_path)
    changed |= _set_config_value(root, "modRoot", mod_root_path)
    changed |= _set_config_value(root, "version", __version__)
    if changed:
        _write_project_config(path, root)
    return path, False, changed


def _set_config_value(root: ET.Element, tag: str, value: str) -> bool:
    """Set a configuration value and return whether it changed."""
    element: ET.Element | None = root.find(tag)
    changed: bool = False
    if element is None:
        element = ET.SubElement(root, tag)
        changed = True
    if (element.text or "") != value:
        element.text = value
        changed = True
    return changed


def _write_project_config(path: Path, root: ET.Element) -> None:
    """Write the project configuration with stable formatting."""
    ET.indent(root, space="  ")
    with path.open("wb") as handle:
        ET.ElementTree(root).write(
            handle,
            encoding="utf-8",
            xml_declaration=True,
            short_empty_elements=True,
        )
        handle.write(b"\n")
