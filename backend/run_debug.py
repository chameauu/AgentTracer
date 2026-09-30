"""Run the AgentTracer backend under a debugpy debug server.

Wrapper for debugging the live ingestion path in Kiro (Option B):

1. Start this script (it listens on 127.0.0.1:5678 and then blocks waiting
   for a debugger to attach).
2. Attach Kiro's debugger to 127.0.0.1:5678.
3. Set breakpoints in e.g. main.py / ingest_service.py / repositories.
4. It resumes uvicorn on :8000; trigger ingestion with the SDK:

       cd sdk && uv run python ../mock_agent.py "what is the weather in Tunis?"

Usage:
    cd backend
    uv run python run_debug.py
"""

import os
from pathlib import Path

import debugpy
import uvicorn

HOST = "127.0.0.1"
DEBUG_PORT = 5678
APP_PORT = 8000

# Run with backend/ as the working directory no matter where we were launched
# from. debugpy resolves relative breakpoint paths (e.g.
# "src/agent_tracer/...") against the process cwd, so launching from the repo
# root would make it search for a nonexistent /AgentTracer/src/... tree.
_BACKEND_DIR = Path(__file__).resolve().parent
os.chdir(_BACKEND_DIR)

debugpy.listen((HOST, DEBUG_PORT))
print(f"debugpy listening on {HOST}:{DEBUG_PORT} — attach the Kiro debugger now.")
debugpy.wait_for_client()
print(f"debugger attached — starting uvicorn on :{APP_PORT} (cwd={os.getcwd()}).")

# Optional sync point: breaks once here after attach, giving you a moment to
# set breakpoints before any request arrives. Remove if you don't want it.
# debugpy.breakpoint()

uvicorn.run("agent_tracer.main:app", host=HOST, port=APP_PORT)