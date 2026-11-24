"""Compatibility entry point (IDE run configuration, `fastapi run main.py`). The app lives in `app.main`."""

from app.main import app

__all__ = ["app"]

if __name__ == "__main__":
    from app.__main__ import main

    main()
