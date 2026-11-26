"""Compatibility entry point (IDE run configuration, `uvicorn main:app`). The app lives in `app.main`."""

from app.main import app

__all__ = ["app"]

if __name__ == "__main__":
    from app.__main__ import main

    main()
