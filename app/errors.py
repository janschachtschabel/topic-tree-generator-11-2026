"""Errors that reach the caller. Lives at the package root so every layer can raise it without importing `api`."""

from typing import Any


class ApiError(Exception):
    """An error the caller should see. `message` must not contain secrets or raw exception text."""

    def __init__(
        self,
        status: int,
        code: str,
        message: str,
        *,
        details: Any = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        super().__init__(f"{code}: {message}")
        self.status = status
        self.code = code
        self.message = message
        self.details = details
        self.headers = headers
