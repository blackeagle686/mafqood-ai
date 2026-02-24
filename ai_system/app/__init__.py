"""ai_system application package.

This module avoids heavy imports during simple package access.  Previously
importing ``app`` would pull in ``app.api`` which in turn loaded all endpoint
modules and triggered a model download.  We now defer router construction to
``app.main`` and lazily expose subpackages explicitly to satisfy test mocking
(via ``unittest.mock.patch``) which relies on attribute traversal.
"""

# expose subpackages so that ``patch('app.core...')`` and similar calls work
# without having to import them explicitly in every test.
from . import api  # type: ignore
from . import core  # type: ignore
from . import tasks  # type: ignore
from . import db  # type: ignore
from . import schemas  # type: ignore

__all__ = ["api", "core", "tasks", "db", "schemas"]
