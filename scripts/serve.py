"""Phase 2: start laya-serve bound to 127.0.0.1 with this repo's settings.

    python scripts/serve.py            # reads .env, refuses a public bind without LAYA_API_KEY

Endpoints (from laya.serve): GET /health, POST /v1/systemone, POST /v1/systemone/batch.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from common import load_env  # noqa: E402

LOCAL_HOSTS = {"127.0.0.1", "localhost", "::1"}


def main() -> None:
    load_env()
    # laya-serve defaults to 0.0.0.0; never inherit that silently.
    os.environ.setdefault("LAYA_HOST", "127.0.0.1")
    os.environ.setdefault("LAYA_PORT", "8000")
    os.environ.setdefault("LAYA_MODELS", "multilingual")
    os.environ.setdefault("LAYA_PRELOAD", "1")

    host = os.environ["LAYA_HOST"]
    # In the Docker image the container must bind 0.0.0.0; docker-compose.yml publishes it on 127.0.0.1.
    in_container = os.environ.get("LAYA_IN_CONTAINER") == "1"
    if host not in LOCAL_HOSTS and not in_container and not os.environ.get("LAYA_API_KEY"):
        sys.exit(f"Refusing to bind {host} without LAYA_API_KEY. Use 127.0.0.1 or set a key in .env.")

    print(
        f"laya-serve on http://{host}:{os.environ['LAYA_PORT']} "
        f"models={os.environ['LAYA_MODELS']} device={os.environ.get('LAYA_DEVICE', 'auto')} "
        f"auth={'on' if os.environ.get('LAYA_API_KEY') else 'off'}",
        flush=True,
    )
    from laya.serve import main as serve_main

    serve_main()


if __name__ == "__main__":
    main()
