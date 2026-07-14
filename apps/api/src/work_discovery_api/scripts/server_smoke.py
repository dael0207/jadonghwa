from __future__ import annotations

import threading
import time

import httpx
import uvicorn

from work_discovery_api.main import app


def main() -> None:
    config = uvicorn.Config(app, host="127.0.0.1", port=8765, log_level="error")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run)
    thread.start()
    try:
        for _ in range(50):
            if server.started:
                break
            time.sleep(0.1)
        response = httpx.get("http://127.0.0.1:8765/openapi.json", timeout=5.0)
        response.raise_for_status()
        assert response.json()["info"]["title"] == "Work Discovery AI API"
    finally:
        server.should_exit = True
        thread.join(timeout=10.0)
    print("server smoke OK")


if __name__ == "__main__":
    main()
