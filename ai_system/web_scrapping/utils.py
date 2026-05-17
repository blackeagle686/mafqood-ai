import re


def sanitize_filename(name: str) -> str:
    """Return a filesystem-safe version of ``name`` by replacing illegal
    characters with underscores.
    """
    return re.sub(r"[\\/*?:\"<>|]", "_", name)
