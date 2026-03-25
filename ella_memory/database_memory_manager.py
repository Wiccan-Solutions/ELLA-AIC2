import sqlite3
import datetime
from pathlib import Path
from typing import Optional, List, Dict

# If you have your ELLA core profiles, you can import them as needed
# from ELLA_v2_0_0 import CREATOR_PROFILE, BOYFRIEND_PROFILE

class DatabaseMemoryManager:
    """
    Drop-in replacement for MemoryManager, using an SQLite database.
    The API is compatible with your original MemoryManager class.
    """
    def __init__(self, db_path: str = "ella_memory/ella_memory.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
        self._bootstrap()

    def _get_connection(self):
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'user',
            tone TEXT NOT NULL DEFAULT 'friendly',
            override_level TEXT NOT NULL DEFAULT 'standard',
            organization TEXT,
            title TEXT,
            conversation_count INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_seen TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS user_facts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            fact TEXT NOT NULL,
            learned_from TEXT DEFAULT 'conversation',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id),
            UNIQUE(user_id, fact)
        );

        CREATE TABLE IF NOT EXISTS user_preferences (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            preference TEXT NOT NULL,
            preference_type TEXT DEFAULT 'interest',
            learned_from TEXT DEFAULT 'conversation',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id),
            UNIQUE(user_id, preference)
        );

        CREATE TABLE IF NOT EXISTS user_notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            note TEXT NOT NULL,
            note_category TEXT DEFAULT 'general',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS conversation_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            conversation_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            session_file TEXT,
            message_count INTEGER DEFAULT 0,
            summary TEXT,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            conversation_log_id INTEGER NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            message_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (conversation_log_id) REFERENCES conversation_logs(id)
        );

        CREATE TABLE IF NOT EXISTS manual_entry_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            entry_type TEXT NOT NULL,
            entry_content TEXT NOT NULL,
            entered_by TEXT DEFAULT 'admin',
            entry_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            notes TEXT,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );
        """)
        conn.commit()
        conn.close()

    def _bootstrap(self):
        """
        Optionally seed hardcoded users (creator/boyfriend).
        Uncomment and complete with your CREATOR_PROFILE, BOYFRIEND_PROFILE if needed.
        """
        # from ELLA_v2_0_0 import CREATOR_PROFILE, BOYFRIEND_PROFILE
        # for prof in [CREATOR_PROFILE, BOYFRIEND_PROFILE]:
        #     self.save(prof)

    # --- Public API (same as original MemoryManager) ---

    def _user_pk(self, user_id: str) -> Optional[int]:
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM users WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        conn.close()
        return row[0] if row else None

    def get(self, user_id: str) -> Optional[Dict]:
        """
        Load a user profile from db (dictionary format).
        Returns None if not found.
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        if not row:
            conn.close()
            return None
        user = dict(row)

        # Fetch facts, preferences, notes
        pk = user['id']
        cursor.execute("SELECT fact FROM user_facts WHERE user_id = ?", (pk,))
        user['facts'] = sorted([r[0] for r in cursor.fetchall()])

        cursor.execute("SELECT preference FROM user_preferences WHERE user_id = ?", (pk,))
        user['preferences'] = sorted([r[0] for r in cursor.fetchall()])

        cursor.execute("SELECT note FROM user_notes WHERE user_id = ?", (pk,))
        user['notes'] = [r[0] for r in cursor.fetchall()]

        conn.close()
        return user

    def save(self, profile: dict):
        """
        Write or update a profile to db, stamping last_seen.
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        now = datetime.datetime.now().isoformat()

        # Insert or update users table
        cursor.execute("""
        INSERT INTO users (user_id, name, role, tone, override_level, organization, title,
                           conversation_count, created_at, last_seen)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(user_id) DO UPDATE SET
            name=excluded.name,
            role=excluded.role,
            tone=excluded.tone,
            override_level=excluded.override_level,
            organization=excluded.organization,
            title=excluded.title,
            conversation_count=excluded.conversation_count,
            last_seen=excluded.last_seen
        """, (
            profile.get("id"),
            profile.get("name"),
            profile.get("role", "user"),
            profile.get("tone", "friendly"),
            profile.get("override_level", "standard"),
            profile.get("organization"),
            profile.get("title"),
            profile.get("conversation_count", 0),
            profile.get("created_at", now),  # fallback for migration
            now
        ))

        # Optionally update notes
        pk = self._user_pk(profile.get("id"))
        # Erase/rebuild notes each save (if provided)
        if pk and "notes" in profile:
            cursor.execute("DELETE FROM user_notes WHERE user_id = ?", (pk,))
            for note in profile["notes"]:
                cursor.execute(
                    "INSERT INTO user_notes (user_id, note) VALUES (?, ?)", (pk, note))
        conn.commit()
        conn.close()

    def create_new_user(self, name: str) -> dict:
        """
        Instantiate and persist a blank profile for a new user.
        """
        user_id = name.strip().lower().replace(" ", "_")
        profile = {
            "id": user_id,
            "name": name.strip().title(),
            "role": "user",
            "tone": "friendly",
            "override_level": "standard",
            "facts": [],
            "preferences": [],
            "notes": [],
            "conversation_count": 0,
            "created_at": datetime.datetime.now().isoformat(),
            "last_seen": None,
        }
        self.save(profile)
        return profile

    def add_memories(self, user_id: str, new_facts: List[str], new_prefs: List[str]):
        """
        Merge newly extracted facts and preferences into a user's profile.
        Deduplicates automatically.
        """
        pk = self._user_pk(user_id)
        if not pk:
            return

        conn = self._get_connection()
        cursor = conn.cursor()

        # Add only new unique facts
        for f in new_facts:
            if f and f.strip():
                try:
                    cursor.execute(
                        "INSERT INTO user_facts (user_id, fact, learned_from) VALUES (?, ?, ?)",
                        (pk, f.strip(), "conversation")
                    )
                except sqlite3.IntegrityError:
                    pass
        for p in new_prefs:
            if p and p.strip():
                try:
                    cursor.execute(
                        "INSERT INTO user_preferences (user_id, preference, learned_from) VALUES (?, ?, ?)",
                        (pk, p.strip(), "conversation")
                    )
                except sqlite3.IntegrityError:
                    pass

        # Increment conversation count
        cursor.execute(
            "UPDATE users SET conversation_count = conversation_count + 1, last_seen = ? WHERE id = ?",
            (datetime.datetime.now().isoformat(), pk)
        )
        conn.commit()
        conn.close()

    def build_memory_block(self, profile: dict) -> str:
        """
        Compatibility: build a <MEMORY> context block for Ella's prompt.
        """
        name = profile.get("name", "this user")
        role = profile.get("role", "user")
        count = profile.get("conversation_count", 0)
        last_seen = profile.get("last_seen") or "never"
        notes = profile.get("notes", [])
        facts = profile.get("facts", [])
        preferences = profile.get("preferences", [])

        lines = [f"<MEMORY: {name}>"]

        if role in ("creator", "boyfriend"):
            lines.append(f"Relationship: {role.upper()}")

        if count > 0:
            date_str = last_seen[:10] if len(last_seen) >= 10 else last_seen
            lines.append(f"You have spoken with {name} {count} time(s). Last session: {date_str}.")
        else:
            lines.append(f"This is your first conversation with {name}.")

        if notes:
            lines.append("What you know (core):")
            for n in notes:
                lines.append(f"  • {n}")

        if facts:
            lines.append("What you've learned about them:")
            for f in facts:
                lines.append(f"  • {f}")

        if preferences:
            lines.append("Their preferences and interests:")
            for p in preferences:
                lines.append(f"  • {p}")

        lines.append("</MEMORY>")
        return "\n".join(lines)

    def log_session(self, user_id: str, history: List[Dict]):
        """
        Write a timestamped conversation log storing JSON transcript reference.
        """
        pk = self._user_pk(user_id)
        if not pk:
            return
        now = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        session_file = f"{user_id}_{now}.json"
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO conversation_logs (user_id, conversation_timestamp, session_file, message_count)
            VALUES (?, ?, ?, ?)
        """, (pk, datetime.datetime.now().isoformat(), session_file, len(history)))
        conn.commit()
        conn.close()
