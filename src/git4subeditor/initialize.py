"""Initialize Git and project configuration for a submarine workspace."""

import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

IGNORE_PATTERNS: tuple[str, ...] = ("*.sub", "*.bak", "*.png")
BEGIN_MARKER = "# ===== Git4SubEditor ====="

PROJECT_CONFIG_FILENAME = "git4subeditor.xml"
PROJECT_CONFIG_ROOT_TAG = "git4subeditor"
PROJECT_NAME_TAG = "projectName"
LANGUAGE_TAG = "language"
GIT_REPOSITORY_TAG = "gitRepository"
DEFAULT_GIT_REPOSITORY = "."


@dataclass(frozen=True, slots=True)
class InitResult:
    """Result of initializing a submarine workspace.

    Attributes:
        gitignore_path: Path to the .gitignore file.
        config_path: Path to the project configuration file.
        added: Ignore patterns added to .gitignore by this call.
        gitignore_created: Whether the .gitignore file was created.
        config_created: Whether the project configuration file was created.
    """

    gitignore_path: Path
    config_path: Path
    added: tuple[str, ...]
    gitignore_created: bool
    config_created: bool


def initialize_project(directory: Path | None = None) -> InitResult:
    """Initialize a workspace with .gitignore and project configuration.

    A new .gitignore contains the required ignore patterns directly. When an
    existing file is missing patterns, they are appended in a marked block.
    Existing content is never rewritten.

    The project configuration is only created when it does not already exist,
    so user preferences are never overwritten.

    Args:
        directory: Workspace directory. Defaults to the current working
            directory.

    Returns:
        Details about the created or updated files.

    Raises:
        OSError: If a file cannot be read or written.

    Examples:
        >>> result = initialize_project(Path("MySubmarine"))
        >>> result.gitignore_created
        True
        >>> result.added
        ('*.sub', '*.bak', '*.png')
    """
    base: Path = directory if directory is not None else Path.cwd()
    gitignore_path, added, gitignore_created = _update_gitignore(base)
    config_path, config_created = _create_project_config(base)
    return InitResult(
        gitignore_path=gitignore_path,
        config_path=config_path,
        added=added,
        gitignore_created=gitignore_created,
        config_created=config_created,
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
    chunks.append(f"{BEGIN_MARKER}{newline}")
    chunks.extend(f"{pattern}{newline}" for pattern in added)

    with path.open("a", encoding="utf-8", newline="") as handle:
        handle.write("".join(chunks))

    return path, added, False


def _create_project_config(base: Path) -> tuple[Path, bool]:
    """Create the project configuration file if it does not exist."""
    path: Path = base / PROJECT_CONFIG_FILENAME
    if path.exists():
        return path, False

    root: ET.Element = ET.Element(PROJECT_CONFIG_ROOT_TAG)
    project_name: ET.Element = ET.SubElement(root, PROJECT_NAME_TAG)
    project_name.text = base.resolve().name or str(base.resolve())
    language: ET.Element = ET.SubElement(root, LANGUAGE_TAG)
    language.text = ""
    git_repository: ET.Element = ET.SubElement(root, GIT_REPOSITORY_TAG)
    git_repository.text = DEFAULT_GIT_REPOSITORY

    ET.indent(root, space="  ")
    with path.open("wb") as handle:
        ET.ElementTree(root).write(
            handle,
            encoding="utf-8",
            xml_declaration=True,
            short_empty_elements=True,
        )
        handle.write(b"\n")

    return path, True
