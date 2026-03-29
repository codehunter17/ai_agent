"""
startup.py — Run this for local development.
Loads .env automatically before starting the server.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env from the project root
env_path = Path(__file__).parent / ".env"
if env_path.exists():
    load_dotenv(env_path)
    print(f"✓ Loaded .env from {env_path}")
else:
    print(f"⚠ No .env file found at {env_path}")
    print("  Copy .env.example to .env and add your API key.")

import uvicorn

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    print(f"  Provider: {os.getenv('LLM_PROVIDER', 'NOT SET')}")
    print(f"  Model:    {os.getenv('LLM_MODEL', 'NOT SET')}")
    key = os.getenv("LLM_API_KEY", "")
    print(f"  API Key:  {'✓ loaded' if key else '✗ MISSING'}")
    print(f"\n→ Starting on http://localhost:{port}")
    print(f"  API docs: http://localhost:{port}/docs\n")

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=port,
        reload=True,
    )
