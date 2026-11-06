"""Localization support for command-line messages."""

import xml.etree.ElementTree as ET
from importlib import resources
from pathlib import Path

DEFAULT_LANGUAGE = "en"
SUPPORTED_LANGUAGES: tuple[str, ...] = ("en", "cn")

_language: str = DEFAULT_LANGUAGE
_catalogs: dict[str, dict[str, str]] = {}


def resolve_language(directory: Path | None = None) -> str:
    """Return the configured language, falling back to English.

    Args:
        directory: Directory containing ``git4subeditor.xml``. Defaults to the
            current working directory.

    Returns:
        A supported language code.
    """
    base: Path = directory if directory is not None else Path.cwd()
    try:
        root: ET.Element = ET.parse(base / "git4subeditor.xml").getroot()
    except (OSError, ET.ParseError):
        return DEFAULT_LANGUAGE

    element: ET.Element | None = root.find("language")
    if element is None:
        return DEFAULT_LANGUAGE
    language: str = (element.text or "").strip().lower()
    if language in SUPPORTED_LANGUAGES:
        return language
    return DEFAULT_LANGUAGE


def set_language(language: str) -> str:
    """Set the active language and return the effective language code.

    Args:
        language: Requested language code.

    Returns:
        The active supported language code.
    """
    global _language
    normalized: str = language.strip().lower()
    _language = normalized if normalized in SUPPORTED_LANGUAGES else DEFAULT_LANGUAGE
    return _language


def get_language() -> str:
    """Return the active language code."""
    return _language


def t(key: str, **values: object) -> str:
    """Translate a message key and format its placeholders.

    Args:
        key: Message key from a locale file.
        **values: Values used by ``str.format`` placeholders.

    Returns:
        The translated message, or the key when no translation exists.
    """
    message: str | None = _catalog(_language).get(key)
    if message is None:
        message = _catalog(DEFAULT_LANGUAGE).get(key)
    if message is None:
        return key
    if values:
        return message.format(**values)
    return message


def _catalog(language: str) -> dict[str, str]:
    """Load and cache one locale catalog."""
    try:
        return _catalogs[language]
    except KeyError:
        pass

    catalog: dict[str, str] = {}
    try:
        path = resources.files("git4subeditor").joinpath("locales", f"{language}.xml")
        with path.open("rb") as handle:
            root: ET.Element = ET.parse(handle).getroot()
    except (OSError, ET.ParseError):
        _catalogs[language] = catalog
        return catalog

    for element in root.findall("message"):
        key: str | None = element.get("key")
        if key:
            catalog[key] = element.text or ""
    _catalogs[language] = catalog
    return catalog
