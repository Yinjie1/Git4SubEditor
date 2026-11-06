"""Initialize project files for a Barotrauma submarine workspace."""

import subprocess
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

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
        config_updated: Whether deprecated configuration fields were removed.
        git_repository_found: Whether the workspace is inside a Git repository.
    """

    gitignore_path: Path
    config_path: Path
    added: tuple[str, ...]
    gitignore_created: bool
    config_created: bool
    config_updated: bool
    git_repository_found: bool


def initialize_project(directory: Path | None = None) -> InitResult:
    """Initialize a workspace with .gitignore and project configuration.

    A new .gitignore contains the required ignore patterns directly. When an
    existing file is missing patterns, they are appended in a marked block.
    Existing content is never rewritten.

    The project configuration is only created when it does not already exist.
    Existing user preferences are preserved, but the deprecated
    ``gitRepository`` field is removed. The project name is taken from the
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
    git_repository_found: bool = _has_git_repository(base)
    project_name: str = mod_root.name or str(mod_root)
    gitignore_path, added, gitignore_created = _update_gitignore(base)
    config_path, config_created, config_updated = _create_project_config(
        base, project_name
    )
    return InitResult(
        gitignore_path=gitignore_path,
        config_path=config_path,
        added=added,
        gitignore_created=gitignore_created,
        config_created=config_created,
        config_updated=config_updated,
        git_repository_found=git_repository_found,
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


def _has_git_repository(base: Path) -> bool:
    """Return whether the directory is inside a Git work tree."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--is-inside-work-tree"],
            cwd=base,
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        return False
    return result.returncode == 0 and result.stdout.strip() == "true"


def _create_project_config(base: Path, project_name: str) -> tuple[Path, bool, bool]:
    """Create or migrate the project configuration file."""
    path: Path = base / "git4subeditor.xml"
    try:
        parser = ET.XMLParser(target=ET.TreeBuilder(insert_comments=True))
        root: ET.Element = ET.parse(path, parser=parser).getroot()
    except FileNotFoundError:
        root = ET.Element("git4subeditor")
        project_name_element: ET.Element = ET.SubElement(root, "projectName")
        project_name_element.text = project_name
        language: ET.Element = ET.SubElement(root, "language")
        language.text = ""
        _write_project_config(path, root)
        return path, True, False
    except ET.ParseError as exc:
        raise InitializeError(f"invalid project configuration {path}: {exc}") from exc

    deprecated: ET.Element | None = root.find("gitRepository")
    if deprecated is not None:
        root.remove(deprecated)
        _write_project_config(path, root)
        return path, False, True

    return path, False, False


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
