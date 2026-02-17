#!/usr/bin/env python3
"""Entry point to run the Kokoro TTS server."""
import argparse
import uvicorn


def main():
    parser = argparse.ArgumentParser(description="Kokoro TTS micro-server")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind to")
    parser.add_argument("--port", type=int, default=8000, help="Port to bind to")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload")
    args = parser.parse_args()

    uvicorn.run(
        "src.server:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
    )


if __name__ == "__main__":
    main()
