# ELLA-AIC2
**Emotional Language Learning Algorithm**

**E.L.L.A.** is an advanced AI companion that is capable of "getting to know" you. She can remember details about you that you have given her as well as hold a conversation with natural tone a precision. Stay tuned for future updates to her code.


* MemoryManager class with persistent JSON storage per user
* Hardcoded creator/relationship profiles for Daniella and Isaiah
* Post-session memory extraction using Gemini to pull facts/preferences from conversation
* User identification at startup with profile lookup
* Memory injection into the system prompt each session
* Tone differentiation by relationship role


**Architecture overview**

The system is organized into four distinct layers — **identity, memory, extraction, and conversation** — so each concern is isolated and easy to extend later.

**MemoryManager** class handles all persistence under an ella_memory/ directory that auto-generates on first run. Each user gets their own JSON file at ella_memory/users/<user_id>.json. Conversation logs are timestamped and saved to ella_memory/logs/. Daniella and Isaiah's profiles are seeded to disk automatically so their accumulated facts grow over time just like any new user's.

**Hardcoded identity protection** — CREATOR_PROFILE and BOYFRIEND_PROFILE are defined at the module level and cannot be overwritten by runtime input. During identify_user(), even if a saved profile exists for Daniella or Isaiah, their role, tone, override_level, and notes are always re-applied from the hardcoded source. This is your security foundation — those fields can never drift.

**Post-session memory extraction** — after every conversation ends, the full transcript is sent back to Gemini with a structured extraction prompt that returns clean JSON (facts vs preferences). New entries are deduplicated against existing ones before being merged into the profile, so repeated sessions don't bloat the file.

**Memory injection** — at the start of each session, the user's full profile is formatted into a <MEMORY: Name> block and appended to the system prompt. The identity prompt explicitly instructs Ella to treat this as genuine knowledge and surface it organically, not as a database readout.

## Recent Updates

### Database Migration
The memory system has been upgraded to use SQLite database storage for better performance and scalability. The `DatabaseMemoryManager` class provides a drop-in replacement for the original JSON-based `MemoryManager`.

- **Migration Script**: Use `ella_memory/migrate_json_to_db.py` to migrate existing JSON user profiles to the database.
- **Backward Compatibility**: The API remains compatible with the original memory manager.

### Web Server and UI
ELLA now includes a FastAPI-based web server (`ella_server.py`) and a beautiful browser-based UI (`ella_ui.html`) for an enhanced user experience.

- **FastAPI Server**: Wraps the ELLA memory/chat engine into REST endpoints.
  - `POST /session/start`: Identify user, load memory, get opening line.
  - `POST /chat`: Send a message, receive Ella's reply.
  - `POST /session/end`: Extract and save memories, close session.
  - `GET /health`: Sanity check.
  - `GET /`: Serves the browser UI.

- **Browser UI**: A responsive, elegant chat interface with:
  - Identity screen for user name input.
  - Real-time chat with typing indicators.
  - Memory count display.
  - Toast notifications for new memories.
  - Responsive design for mobile and desktop.

**Setup Instructions**:
1. Install dependencies: `pip install -r requirements.txt`
2. Set Google API key: `export GOOGLE_API_KEY="your_key_here"`
3. Run the server: `uvicorn ella_server:app --reload --port 8000`
4. Open `http://localhost:8000` in your browser.

**Production Deployment**: Update `API_BASE` in `ella_ui.html` to your domain (e.g., `https://ella.yourdomain.com`).

### Admin CLI
The `ella_admin_cli.py` provides command-line tools for managing the ELLA database and user data.
