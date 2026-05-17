import requests


class FacebookSession(requests.Session):
    """A thin wrapper around :class:`requests.Session` that applies
    sensible defaults for scraping Facebook pages.

    The class exists primarily to centralize header, cookie and
token management so that the rest of the scraping code can depend on
an HTTP client with a predictable interface.
    """

    def __init__(self, cookies=None, headers=None):
        super().__init__()
        # mimic a modern browser to avoid trivial blocks
        self.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/58.0.3029.110 Safari/537.3"
            )
        })
        if headers:
            self.headers.update(headers)
        if cookies:
            self.cookies.update(cookies)

    def login(self, email: str, password: str) -> None:
        """Stub for a login helper.

        A real implementation would need to fetch the login page, parse
        any hidden form fields, submit the credentials, and preserve any
        cookies or CSRF tokens that Facebook returns. That logic is
        deliberately omitted here because it is outside the scope of a
        reusable scraping helper.  Calling code may subclass this class
        to provide working login behaviour.
        """
        raise NotImplementedError("Facebook login is not implemented")
