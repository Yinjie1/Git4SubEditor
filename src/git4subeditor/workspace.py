"""Workspace configuration, initialization, and registered submarine display."""

import hashlib
import xml.etree.ElementTree as ET
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from git4subeditor import __version__
from git4subeditor.l10n import DEFAULT_LANGUAGE, SUPPORTED_LANGUAGES, t
from git4subeditor.subfile import SubFileError
from git4subeditor.utils import format_message


@dataclass(frozen=True, slots=True)
class SubmarineEntry:
    """A submarine registered in the project configuration.

    Attributes:
        name: Display name. Defaults to the ``.sub`` filename when the
            configuration omits it. Names may repeat and are not identifiers.
        path: Submarine path relative to the workspace directory. This is the
            registry identity.
        preview: Preview image path relative to the workspace directory, or
            None when no preview is configured.
        hash: SHA-256 hash of the submarine file recorded at registration, or
            None when no hash is configured.
        xml: Exported XML path relative to the workspace directory, or None
            when the submarine has not been exported.
    """

    name: str
    path: str
    preview: str | None = None
    hash: str | None = None
    xml: str | None = None


@dataclass(frozen=True, slots=True)
class WorkspaceInfo:
    """Project information used by the CLI and interactive mode.

    Attributes:
        project_name: Project name from ``git4subeditor.xml``.
        git_repo: Git repository path relative to the workspace.
        mod_root: MOD root path relative to the workspace.
        submarines: Registered submarines in configuration order.
    """

    project_name: str
    git_repo: str
    mod_root: str
    submarines: tuple[SubmarineEntry, ...]


type _TreeEntry = tuple[list[str], SubmarineEntry, str | None]
type SubmarineConfirm = Callable[
    [tuple[SubmarineEntry, ...], tuple[SubmarineEntry, ...]], bool
]
type RemovalConfirm = Callable[[tuple[SubmarineEntry, ...]], bool]
type PathConfirm = Callable[[str, str], bool]
type DuplicateConfirm = Callable[[tuple[tuple[SubmarineEntry, ...], ...]], bool]


def read_config_root() -> ET.Element | None:
    """Read the current directory project configuration root.

    Returns:
        The ``git4subeditor`` element, or None when the configuration does not
        exist.

    Raises:
        SubFileError: If the configuration cannot be read or parsed.
    """
    config_path: Path = Path.cwd() / "git4subeditor.xml"
    try:
        return ET.parse(config_path).getroot()
    except FileNotFoundError:
        return None
    except (OSError, ET.ParseError) as exc:
        raise SubFileError(
            t("err.invalid_config", path=config_path, error=exc)
        ) from exc


def load_workspace_info() -> WorkspaceInfo | None:
    """Load workspace details from the current directory project config.

    Returns:
        Workspace details, or None when ``git4subeditor.xml`` does not exist.

    Raises:
        SubFileError: If the configuration cannot be read or parsed.
    """
    root: ET.Element | None = read_config_root()
    if root is None:
        return None

    project_name: str = (root.findtext("projectName") or "").strip()
    git_repo: str = (root.findtext("gitRepo") or "").strip() or "."
    mod_root: str = (root.findtext("modRoot") or "").strip() or "."
    submarines: list[SubmarineEntry] = []
    for entry in root.findall("./submarines/submarine"):
        path_text: str = (entry.get("path") or "").strip()
        if not path_text:
            continue
        name_text: str = (entry.get("name") or "").strip() or Path(path_text).stem
        hash_text: str = (entry.get("hash") or "").strip()
        xml_text: str = (entry.get("xml") or "").strip()
        submarines.append(
            SubmarineEntry(
                name=name_text,
                path=path_text,
                hash=hash_text or None,
                xml=xml_text or None,
            )
        )

    return WorkspaceInfo(
        project_name=project_name or Path.cwd().name,
        git_repo=git_repo,
        mod_root=mod_root,
        submarines=tuple(submarines),
    )


def _split_path_text(path_text: str) -> list[str]:
    """Split a configured path into components."""
    parts: tuple[str, ...] = Path(path_text).parts
    if not parts:
        return ["."]
    if path_text.startswith(("./", ".\\")):
        return [".", *parts]
    return list(parts)


def _relative_display(path: Path) -> str:
    """Return a path relative to the current directory in POSIX form."""
    try:
        relative: Path = path.resolve().relative_to(
            Path.cwd().resolve(),
            walk_up=True,
        )
    except ValueError:
        return str(path)
    return relative.as_posix()


def _file_hash(path: Path) -> str:
    """Return the SHA-256 hex digest of a file."""
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def refresh_submarine_metadata(submarines: tuple[SubmarineEntry, ...]) -> bool:
    """Refresh stored hashes and XML paths for exported submarine entries.

    Args:
        submarines: Exported entries containing refreshed hashes and XML paths.

    Returns:
        Whether ``git4subeditor.xml`` was rewritten.

    Raises:
        SubFileError: If the project configuration cannot be read or parsed.
    """
    root: ET.Element | None = read_config_root()
    if root is None:
        return False
    entries: dict[str, SubmarineEntry] = {entry.path: entry for entry in submarines}
    changed: bool = False
    for child in root.findall("./submarines/submarine"):
        path_text: str = (child.get("path") or "").strip()
        entry: SubmarineEntry | None = entries.get(path_text)
        if entry is None:
            continue
        if entry.hash is not None and child.get("hash") != entry.hash:
            child.set("hash", entry.hash)
            changed = True
        if entry.xml is not None and child.get("xml") != entry.xml:
            child.set("xml", entry.xml)
            changed = True
    if changed:
        _write_project_config(Path.cwd() / "git4subeditor.xml", root)
    return changed


def _status_suffix(status: str | None) -> str:
    """Return a colored status suffix for a listed submarine."""
    if status is None:
        return ""
    color: str = "red" if status == "U" else "yellow"
    return f" {format_message(f'({status})', color=color)}"


def print_submarine_paths(info: WorkspaceInfo, tree: bool = True) -> None:
    """Print all submarine paths under the repository.

    Paths are shown relative to the workspace directory. Unregistered
    submarine files are marked with a red ``(U)`` suffix.
    Registered files whose hash changed are marked with a yellow ``(M)``.

    Args:
        info: Workspace information containing registered submarines.
        tree: Whether to print a directory tree. When False, print files in
            path order.
    """
    root_label: str = info.git_repo or "."
    workspace_root: Path = Path.cwd()
    root_path: Path = workspace_root / root_label
    root_path_resolved: Path = root_path.resolve()
    registered = {entry.path: entry for entry in info.submarines}
    scanned_entries, unregistered, modified, _ = _detect_submarines(
        read_config_root(),
        root_path_resolved,
        workspace_root,
    )
    unregistered_paths: set[str] = {entry.path for entry in unregistered}
    modified_paths: set[str] = {entry.path for entry in modified}
    listed: list[tuple[SubmarineEntry, str | None]] = []
    for scanned in scanned_entries:
        entry: SubmarineEntry = registered.get(scanned.path) or scanned
        status: str | None = None
        if scanned.path in unregistered_paths:
            status = "U"
        elif scanned.path in modified_paths:
            status = "M"
        listed.append((entry, status))

    if not tree:
        for submarine, status in listed:
            path_text: str = _relative_display(workspace_root / submarine.path)
            print(f"{submarine.name}: {path_text}{_status_suffix(status)}")
        return

    entries: list[_TreeEntry] = []
    for submarine, status in listed:
        try:
            repository_relative: Path = (
                (workspace_root / submarine.path)
                .resolve()
                .relative_to(root_path_resolved)
            )
        except ValueError:
            continue
        parts: list[str] = _split_path_text(repository_relative.as_posix())
        if not parts:
            continue
        entries.append((parts[:-1], submarine, status))

    if not entries:
        return

    def print_children(
        children: list[_TreeEntry],
        prefix: str,
        parent: Path,
    ) -> None:
        """Print tree entries below one directory level."""
        files: list[tuple[SubmarineEntry, str | None]] = [
            (submarine, status)
            for directories, submarine, status in children
            if not directories
        ]
        directory_names: list[str] = list(
            dict.fromkeys(
                directories[0] for directories, _, _ in children if directories
            )
        )

        total: int = len(files) + len(directory_names)
        index: int = 0
        for submarine, status in files:
            index += 1
            connector: str = "└── " if index == total else "├── "
            filename: str = Path(submarine.path).name
            print(
                f"{prefix}{connector}{submarine.name}: {filename}"
                f"{_status_suffix(status)}"
            )

        for directory_name in directory_names:
            index += 1
            connector = "└── " if index == total else "├── "
            directory_path: Path = parent / directory_name
            directory_text: str = format_message(
                _relative_display(directory_path),
                color="light_blue",
            )
            print(f"{prefix}{connector}{directory_text}")
            child_prefix: str = prefix + ("    " if index == total else "│   ")
            nested: list[_TreeEntry] = [
                (directories[1:], submarine, status)
                for directories, submarine, status in children
                if directories and directories[0] == directory_name
            ]
            print_children(nested, child_prefix, directory_path)

    print(format_message(_relative_display(root_path), color="light_blue"))
    print_children(entries, "", root_path)


IGNORE_PATTERNS: tuple[str, ...] = ("*.sub", "*.bak", "*.png", "history")


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
        submarines: Submarine files found below the Git repository root, with
            paths relative to the workspace directory.
        submarines_updated: Whether the submarine registry was updated.
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
    submarines: tuple[SubmarineEntry, ...]
    submarines_updated: bool


def _read_config_paths(base: Path) -> tuple[str, str] | None:
    """Return configured gitRepo and modRoot values from an existing config."""
    path: Path = base / "git4subeditor.xml"
    try:
        parser = ET.XMLParser(target=ET.TreeBuilder(insert_comments=True))
        root = ET.parse(path, parser=parser).getroot()
    except FileNotFoundError:
        return None
    except ET.ParseError as exc:
        raise InitializeError(t("err.invalid_config", path=path, error=exc)) from exc
    return (
        (root.findtext("gitRepo") or "").strip(),
        (root.findtext("modRoot") or "").strip(),
    )


def _choose_path(confirm: PathConfirm | None, old: str, new: str) -> str:
    """Return the new path when confirmed, otherwise the old path."""
    if confirm is None or old == new:
        return new
    return new if confirm(old, new) else old


def initialize_project(
    directory: Path | None = None,
    language: str | None = None,
    confirm_submarines: SubmarineConfirm | None = None,
    confirm_removals: RemovalConfirm | None = None,
    confirm_mod_root: PathConfirm | None = None,
    confirm_git_repo: PathConfirm | None = None,
    confirm_duplicates: DuplicateConfirm | None = None,
) -> InitResult:
    """Initialize or update a workspace with .gitignore and project configuration.

    A new .gitignore contains the required ignore patterns directly. When an
    existing file is missing patterns, they are appended in a marked block.
    Existing content is never rewritten.

    Existing user preferences are preserved. The ``gitRepo``, ``modRoot``,
    and ``version`` fields are updated. The project name is taken from the
    nearest ancestor directory containing ``filelist.xml``. After the Git
    repository is located, ``.sub`` files below its root are registered in
    the ``submarines`` section using paths relative to the workspace. Existing
    entries are matched by path, which acts as the registry identity. Their
    ``name``, ``preview``, and other attributes are preserved, while new
    entries get a derived ``.png`` preview and omit the optional ``name``
    attribute.

    Args:
        directory: Workspace directory. Defaults to the current working
            directory.
        language: Language code written to the project configuration. When
            omitted, an existing valid language is preserved.
        confirm_submarines: Optional callback that receives the registered and
            pending submarine entries. Returning False leaves the registry
            unchanged. When omitted, pending changes are applied directly.
        confirm_removals: Optional callback that receives registered entries
            whose paths no longer exist. Returning False keeps those entries.
        confirm_mod_root: Optional callback that receives the configured and
            detected MOD root paths. Returning False keeps the configured path.
        confirm_git_repo: Optional callback that receives the configured and
            detected Git repository paths. Returning False keeps the configured
            path.
        confirm_duplicates: Optional callback that receives groups of scanned
            submarine files whose names collide. Returning False leaves the
            registry unchanged.

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
        ('*.sub', '*.bak', '*.png', 'history')
    """
    base: Path = directory if directory is not None else Path.cwd()
    mod_root: Path = _find_mod_root(base)
    repository_path, current_repository, upper_repository = _find_git_repository(
        base, mod_root
    )
    repository_root: Path | None = (
        (base / repository_path).resolve() if repository_path else None
    )
    project_name: str = mod_root.name or str(mod_root)
    mod_root_path: str = _relative_path(base.resolve(), mod_root)
    existing_paths: tuple[str, str] | None = _read_config_paths(base)
    if existing_paths is not None:
        old_repository_path, old_mod_root_path = existing_paths
        mod_root_path = _choose_path(
            confirm_mod_root,
            old_mod_root_path,
            mod_root_path,
        )
        repository_path = _choose_path(
            confirm_git_repo,
            old_repository_path,
            repository_path,
        )
    gitignore_path, added, gitignore_created = _update_gitignore(base)
    (
        config_path,
        config_created,
        config_updated,
        submarines_updated,
        submarines,
    ) = _create_project_config(
        base,
        project_name,
        repository_path,
        mod_root_path,
        language,
        repository_root,
        confirm_submarines,
        confirm_removals,
        confirm_duplicates,
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
        submarines=submarines,
        submarines_updated=submarines_updated,
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
    raise InitializeError(t("err.not_mod", path=current))


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
    return target.relative_to(current, walk_up=True).as_posix()


def _detect_submarines(
    root: ET.Element | None,
    repository_root: Path | None,
    workspace_root: Path,
) -> tuple[
    tuple[SubmarineEntry, ...],
    tuple[SubmarineEntry, ...],
    tuple[SubmarineEntry, ...],
    tuple[SubmarineEntry, ...],
]:
    """Return scanned submarine files and registry differences.

    Files inside ``.git`` directories are ignored. Paths are relative to the
    workspace directory and always use ``/`` separators. Every scanned entry
    gets a derived ``.png`` preview path and its SHA-256 hash.

    Args:
        root: Existing project configuration root, or None when the
            configuration does not exist yet.
        repository_root: Resolved Git repository root, or None when no
            repository was found.
        workspace_root: Workspace directory used as the base for relative
            paths.

    Returns:
        All scanned submarine entries, unregistered entries, registered
        entries whose hash changed, and registered entries whose paths are no
        longer present.
    """
    entries: list[SubmarineEntry] = []
    if repository_root is not None:
        for path in repository_root.rglob("*"):
            if path.suffix.lower() != ".sub" or not path.is_file():
                continue
            repository_relative: Path = path.relative_to(repository_root)
            if ".git" in repository_relative.parts[:-1]:
                continue
            relative: str = _relative_path(workspace_root.resolve(), path.resolve())
            preview: str = Path(relative).with_suffix(".png").as_posix()
            entries.append(
                SubmarineEntry(
                    name=path.stem,
                    path=relative,
                    preview=preview,
                    hash=_file_hash(path),
                )
            )
        entries.sort(key=lambda entry: entry.path.casefold())

    registered: dict[str, SubmarineEntry] = {}
    if root is not None:
        for child in root.findall("./submarines/submarine"):
            path_text: str = (child.get("path") or "").strip()
            if not path_text:
                continue
            name_text: str = (child.get("name") or "").strip() or Path(path_text).stem
            registered[path_text] = SubmarineEntry(
                name=name_text,
                path=path_text,
                preview=(child.get("preview") or "").strip() or None,
                hash=(child.get("hash") or "").strip() or None,
                xml=(child.get("xml") or "").strip() or None,
            )

    unregistered: list[SubmarineEntry] = []
    modified: list[SubmarineEntry] = []
    for entry in entries:
        old: SubmarineEntry | None = registered.get(entry.path)
        if old is None:
            unregistered.append(entry)
        elif old.hash != entry.hash:
            modified.append(
                SubmarineEntry(
                    name=old.name,
                    path=entry.path,
                    preview=entry.preview,
                    hash=entry.hash,
                    xml=old.xml,
                )
            )

    scanned_paths: set[str] = {entry.path for entry in entries}
    missing: tuple[SubmarineEntry, ...] = tuple(
        entry for path, entry in registered.items() if path not in scanned_paths
    )
    return tuple(entries), tuple(unregistered), tuple(modified), missing


def _duplicate_name_groups(
    entries: tuple[SubmarineEntry, ...],
    pending_paths: set[str],
) -> tuple[tuple[SubmarineEntry, ...], ...]:
    """Group scanned submarines that include a pending path by stem.

    Args:
        entries: Scanned submarine entries in scan order.
        pending_paths: Paths that are new or changed in this scan.

    Returns:
        Duplicate groups containing at least one pending path, preserving
        scan order.
    """
    groups: dict[str, list[SubmarineEntry]] = {}
    for entry in entries:
        groups.setdefault(Path(entry.path).stem.casefold(), []).append(entry)
    return tuple(
        tuple(group)
        for group in groups.values()
        if len(group) > 1 and any(entry.path in pending_paths for entry in group)
    )


def _confirm_submarine_update(
    confirm: SubmarineConfirm | None,
    root: ET.Element | None,
    pending: tuple[SubmarineEntry, ...],
) -> bool:
    """Return whether pending registry changes should be applied."""
    if confirm is None or not pending:
        return True

    registered: list[SubmarineEntry] = []
    if root is not None:
        for child in root.findall("./submarines/submarine"):
            path: str = (child.get("path") or "").strip()
            if not path:
                continue
            registered.append(
                SubmarineEntry(
                    name=(child.get("name") or "").strip() or Path(path).stem,
                    path=path,
                    preview=(child.get("preview") or "").strip() or None,
                    hash=(child.get("hash") or "").strip() or None,
                )
            )
    return confirm(tuple(registered), pending)


def _create_project_config(
    base: Path,
    project_name: str,
    repository_path: str,
    mod_root_path: str,
    language: str | None,
    repository_root: Path | None,
    confirm_submarines: SubmarineConfirm | None,
    confirm_removals: RemovalConfirm | None,
    confirm_duplicates: DuplicateConfirm | None,
) -> tuple[
    Path,
    bool,
    bool,
    bool,
    tuple[SubmarineEntry, ...],
]:
    """Create or update the project configuration file."""
    path: Path = base / "git4subeditor.xml"
    try:
        parser = ET.XMLParser(target=ET.TreeBuilder(insert_comments=True))
        root: ET.Element = ET.parse(path, parser=parser).getroot()
    except FileNotFoundError:
        root = ET.Element("git4subeditor")
        _set_config_value(root, "projectName", project_name)
        selected_language: str = (
            language if language in SUPPORTED_LANGUAGES else DEFAULT_LANGUAGE
        )
        _set_config_value(root, "language", selected_language)
        _set_config_value(root, "gitRepo", repository_path)
        _set_config_value(root, "modRoot", mod_root_path)
        _set_config_value(root, "version", __version__)
        submarines, unregistered, modified, _ = _detect_submarines(
            None, repository_root, base
        )
        unregistered_paths: set[str] = {entry.path for entry in unregistered}
        duplicate_groups: tuple[tuple[SubmarineEntry, ...], ...] = (
            _duplicate_name_groups(submarines, unregistered_paths)
        )
        duplicates_confirmed: bool = (
            confirm_duplicates is None
            or not duplicate_groups
            or confirm_duplicates(duplicate_groups)
        )
        pending: tuple[SubmarineEntry, ...] = (*unregistered, *modified)
        update_submarines: bool = duplicates_confirmed and _confirm_submarine_update(
            confirm_submarines, root, pending
        )
        if update_submarines:
            _sync_submarines(
                root,
                submarines,
                update=True,
                remove_missing=True,
            )
        else:
            ET.SubElement(root, "submarines")
        _write_project_config(path, root)
        return path, True, False, update_submarines, submarines
    except ET.ParseError as exc:
        raise InitializeError(t("err.invalid_config", path=path, error=exc)) from exc

    submarines, unregistered, modified, removed = _detect_submarines(
        root, repository_root, base
    )
    unregistered_paths: set[str] = {entry.path for entry in unregistered}
    duplicate_groups = _duplicate_name_groups(submarines, unregistered_paths)
    duplicates_confirmed = (
        confirm_duplicates is None
        or not duplicate_groups
        or confirm_duplicates(duplicate_groups)
    )
    pending: tuple[SubmarineEntry, ...] = (*unregistered, *modified)
    update_submarines: bool = duplicates_confirmed and _confirm_submarine_update(
        confirm_submarines,
        root,
        pending,
    )
    remove_submarines: bool = duplicates_confirmed and (
        not removed or confirm_removals is None or confirm_removals(removed)
    )
    changed: bool = False
    legacy: ET.Element | None = root.find("gitRepository")
    if legacy is not None:
        root.remove(legacy)
        changed = True
    if language is not None:
        selected_language = (
            language if language in SUPPORTED_LANGUAGES else DEFAULT_LANGUAGE
        )
        changed |= _set_config_value(root, "language", selected_language)
    else:
        language_element: ET.Element | None = root.find("language")
        current_language: str = (
            (language_element.text or "").strip().lower()
            if language_element is not None
            else ""
        )
        if current_language not in SUPPORTED_LANGUAGES:
            changed |= _set_config_value(root, "language", DEFAULT_LANGUAGE)
    changed |= _set_config_value(root, "gitRepo", repository_path)
    changed |= _set_config_value(root, "modRoot", mod_root_path)
    changed |= _set_config_value(root, "version", __version__)
    submarines_updated: bool = False
    if update_submarines or remove_submarines:
        submarines_updated = _sync_submarines(
            root,
            submarines,
            update=update_submarines,
            remove_missing=remove_submarines,
        )
    changed |= submarines_updated
    if changed:
        _write_project_config(path, root)
    return path, False, changed, submarines_updated, submarines


def _sync_submarines(
    root: ET.Element,
    submarines: tuple[SubmarineEntry, ...],
    *,
    update: bool,
    remove_missing: bool,
) -> bool:
    """Sync the submarine registry by path.

    Existing entries are matched by path. Their ``name``, ``preview``, and any
    other attributes are preserved. When ``update`` is true, hashes are
    refreshed and new entries are added without the optional ``name``.
    When ``remove_missing`` is true, paths absent from the scan are removed.

    Args:
        root: Root element of the project configuration.
        submarines: Entries found by the current scan.
        update: Whether to add or refresh scanned entries.
        remove_missing: Whether to remove registered paths not in the scan.

    Returns:
        Whether the configuration changed.
    """
    element: ET.Element | None = root.find("submarines")
    changed: bool = False
    if element is None:
        if not update:
            return False
        element = ET.SubElement(root, "submarines")
        changed = True

    scanned_paths: set[str] = {entry.path for entry in submarines}
    existing: dict[str, ET.Element] = {}
    for child in list(element.findall("submarine")):
        path_text: str = (child.get("path") or "").strip()
        if (
            not path_text
            or path_text in existing
            or (remove_missing and path_text not in scanned_paths)
        ):
            element.remove(child)
            changed = True
            continue
        existing[path_text] = child

    if not update:
        return changed

    for entry in submarines:
        child: ET.Element | None = existing.get(entry.path)
        if child is not None:
            new_hash: str = entry.hash or ""
            if (child.get("hash") or "") != new_hash:
                child.set("hash", new_hash)
                changed = True
            continue
        child = ET.SubElement(
            element,
            "submarine",
            {
                "path": entry.path,
                "preview": entry.preview or "",
                "hash": entry.hash or "",
            },
        )
        existing[entry.path] = child
        changed = True

    return changed


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
