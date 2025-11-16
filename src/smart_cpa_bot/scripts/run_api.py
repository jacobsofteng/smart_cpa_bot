"""Helper to run the FastAPI server."""

from __future__ import annotations

import uvicorn


def main() -> None:
    uvicorn.run("smart_cpa_bot.api.server:app", host="0.0.0.0", port=8000, reload=False)


if __name__ == "__main__":
    main()
