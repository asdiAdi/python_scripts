"""Shared helpers usable by all scripts in this repo.

Import as:
    from common.paths import get_repo_root, get_workspace_root
    from common.io import info, error
    from common.logging import setup_logging
"""

from common.io import confirm, eprint, error, info
from common.logging import setup_logging
from common.paths import get_repo_root, get_workspace_root
from common.prompt import PromptClient

__all__ = [
    "PromptClient",
    "confirm",
    "eprint",
    "error",
    "get_repo_root",
    "get_workspace_root",
    "info",
    "setup_logging",
]
