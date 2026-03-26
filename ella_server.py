#!/usr/bin/env python3
"""
E.L.L.A. — FastAPI Web Server
Wraps the ELLA_v2 memory/chat engine into REST endpoints
for the browser-based UI.

Run with:
    pip install fastapi uvicorn google-generativeai
    export GOOGLE_API_KEY="your_key_here"
    uvicorn ella_server:app --reload --port 8000

Endpoints:
    POST /session/start   — identify user, load memory, get opening line
    POST /chat            — send a message, receive Ella's reply
    POST /session/end     — extract + save memories, close session
    GET  /health          — sanity check
"""

import os
import uuid
import datetime
import json
from typing import Optional

import google.generativeai as genai
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

# ── Import everything from ELLA_v2 ────────────────────────────────────
# Assumes ELLA_v2.py is in the same directory.
# If you renamed it, update the import below.
from ella_memory.database_memory_manager import DatabaseMemoryManager
from ella import (
    identify_user as _identify_user_core,
    extract_memories,
    opening_line,
    ELLA_CORE_IDENTITY,
    KNOWN_IDENTITIES,
)


# ══════════════════════════════════════════════════════════════════════
#  APP SETUP
# ══════════════════════════════════════════════════════════════════════

app = FastAPI(title="E.L.L.A. API", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # Tighten this for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global singletons
api_key = os.environ.get("GOOGLE_API_KEY")
if not api_key:
    raise EnvironmentError("GOOGLE_API_KEY environment variable is not set.")

genai.configure(api_key=api_key)
memory_manager = DatabaseMemoryManager()

# In-memory session store  { session_id: SessionState }
sessions: dict[str, dict] = {}


# ══════════════════════════════════════════════════════════════════════
#  PYDANTIC SCHEMAS
# ══════════════════════════════════════════════════════════════════════

class StartSessionRequest(BaseModel):
    name: str

class StartSessionResponse(BaseModel):
    session_id: str
    user_name: str
    user_role: str
    is_returning: bool
    memory_count: int
    opening_line: str

class ChatRequest(BaseModel):
    session_id: str
    message: str

class ChatResponse(BaseModel):
    reply: str
    session_id: str

class EndSessionRequest(BaseModel):
    session_id: str

class EndSessionResponse(BaseModel):
    new_facts: int
    new_preferences: int
    message: str


# ══════════════════════════════════════════════════════════════════════
#  HELPERS
# ══════════════════════════════════════════════════════════════════════

def resolve_profile(name: str) -> tuple[dict, bool]:
    """
    Replicate identify_user() logic without stdin/stdout —
    returns (profile, is_returning).
    """
    normalized = name.strip().lower()
    if normalized in KNOWN_IDENTITIES:
        seed = KNOWN_IDENTITIES[normalized]
        saved = memory_manager.get(seed["id"])
        if saved:
            saved["role"]           = seed["role"]
            saved["tone"]           = seed["tone"]
            saved["override_level"] = seed["override_level"]
            saved["notes"]          = seed["notes"]
            return saved, True
        memory_manager.save(dict(seed))
        return dict(seed), False

    user_id = normalized.replace(" ", "_")
    saved = memory_manager.get(user_id)
    if saved:
        return saved, True

    profile = memory_manager.create_new_user(name)
    return profile, False


# ══════════════════════════════════════════════════════════════════════
#  ROUTES
# ══════════════════════════════════════════════════════════════════════

@app.get("/", response_class=HTMLResponse)
def get_ui():
    with open("ella_ui.html", "r") as f:
        return f.read()


@app.get("/health")
def health():
    return {"status": "ok", "ella": "online", "time": datetime.datetime.now().isoformat()}


@app.post("/session/start", response_model=StartSessionResponse)
def start_session(req: StartSessionRequest):
    """
    Identify the user by name, load their memory profile,
    spin up a Gemini conversation, and return Ella's opening line.
    """
    profile, is_returning = resolve_profile(req.name)
    user_name = profile["name"]
    user_id   = profile["id"]

    memory_block = memory_manager.build_memory_block(profile)
    full_system  = f"{ELLA_CORE_IDENTITY}\n\n{memory_block}"

    model = genai.GenerativeModel(
        model_name="gemini-1.5-pro",
        system_instruction=full_system,
    )
    conversation = model.start_chat(history=[])

    session_id = str(uuid.uuid4())
    sessions[session_id] = {
        "user_id":      user_id,
        "user_name":    user_name,
        "profile":      profile,
        "conversation": conversation,
        "log":          [],
        "extractor":    genai.GenerativeModel(model_name="gemini-1.5-pro"),
        "started_at":   datetime.datetime.now().isoformat(),
    }

    opener = opening_line(profile, is_returning)
    memory_count = len(profile.get("facts", [])) + len(profile.get("notes", []))

    return StartSessionResponse(
        session_id   = session_id,
        user_name    = user_name,
        user_role    = profile.get("role", "user"),
        is_returning = is_returning,
        memory_count = memory_count,
        opening_line = opener,
    )


@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    """Send a user message, return Ella's reply."""
    if req.session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found. Please start a new session.")

    state = sessions[req.session_id]
    conversation = state["conversation"]

    state["log"].append({"role": "user", "content": req.message})

    try:
        response = conversation.send_message(req.message)
        reply = response.text
    except Exception as exc:
        reply = f"Hmm, something hiccuped on my end — ({exc}). Want to try again? 💜"

    state["log"].append({"role": "ella", "content": reply})

    return ChatResponse(reply=reply, session_id=req.session_id)


@app.post("/session/end", response_model=EndSessionResponse)
def end_session(req: EndSessionRequest):
    """
    Close the session: extract memories from transcript,
    persist to profile, write log, clean up.
    """
    if req.session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found.")

    state     = sessions.pop(req.session_id)
    user_id   = state["user_id"]
    user_name = state["user_name"]
    log       = state["log"]
    extractor = state["extractor"]

    if len(log) < 2:
        return EndSessionResponse(new_facts=0, new_preferences=0, message="No conversation to save.")

    transcript = "\n".join(
        f"{'User' if m['role'] == 'user' else 'Ella'}: {m['content']}"
        for m in log
    )

    new_facts, new_prefs = extract_memories(extractor, transcript, user_name)

    if new_facts or new_prefs:
        memory_manager.add_memories(user_id, new_facts, new_prefs)

    memory_manager.log_session(user_id, log)

    return EndSessionResponse(
        new_facts       = len(new_facts),
        new_preferences = len(new_prefs),
        message         = f"Session saved. Remembered {len(new_facts)} fact(s) and {len(new_prefs)} preference(s).",
    )