"""Legacy module preserved for backwards compatibility.

Modules should import helpers directly from the subpackages rather than
relying on this file, which shadowed the real ``requests`` module and
caused confusing imports.  It is left here so that any existing code
referring to ``web_scrapping.requests`` continues to work, but it is
recommended to switch to the objects exposed by the new modules.
"""

# re-export the most common symbols from the real ``requests`` package
# so that ``from web_scrapping import requests`` behaves somewhat like
# ``import requests``.
from requests import Session, get, post, put, delete, head, options, patch, Request, Response

