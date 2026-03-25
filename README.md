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
