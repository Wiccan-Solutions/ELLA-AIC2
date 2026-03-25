# database_manager.py
import sqlite3
import datetime
from pathlib import Path
from typing import Optional, List, Dict, Tuple

class DatabaseManager:
    """
    Manages ELLA's persistent memory using SQLite.
    Replaces JSON-based MemoryManager with relational database.
    """

    def __init__(self, db_path: str = "ella_memory/ella_memory.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _get_connection(self):
        """Create a database connection."""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        """Initialize database tables if they don't exist."""
        conn = self._get_connection()
        cursor = conn.cursor()

        # Execute the schema
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

        CREATE INDEX IF NOT EXISTS idx_user_id ON users(user_id);
        CREATE INDEX IF NOT EXISTS idx_user_facts ON user_facts(user_id);
        CREATE INDEX IF NOT EXISTS idx_user_preferences ON user_preferences(user_id);
        CREATE INDEX IF NOT EXISTS idx_conversation_user ON conversation_logs(user_id);
        CREATE INDEX IF NOT EXISTS idx_messages_conversation ON messages(conversation_log_id);
        """)

        conn.commit()
        conn.close()

    # ─────────────────────────────────────────────────────────────────────
    #  USER MANAGEMENT
    # ─────────────────────────────────────────────────────────────────────

    def get_or_create_user(self, user_id: str, name: str, role: str = "user",
                          tone: str = "friendly", override_level: str = "standard") -> Dict:
        """Get user by ID, or create if doesn't exist."""
        conn = self._get_connection()
        cursor = conn.cursor()

        # Try to fetch
        cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()

        if row:
            conn.close()
            return dict(row)

        # Create new
        cursor.execute("""
            INSERT INTO users (user_id, name, role, tone, override_level)
            VALUES (?, ?, ?, ?, ?)
        """, (user_id, name, role, tone, override_level))

        conn.commit()

        cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        conn.close()
        return dict(row)

    def get_user_by_id(self, user_id: str) -> Optional[Dict]:
        """Fetch user by user_id."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None

    def update_user_last_seen(self, user_id: str):
        """Update last_seen timestamp for a user."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE users SET last_seen = CURRENT_TIMESTAMP WHERE user_id = ?",
            (user_id,)
        )
        conn.commit()
        conn.close()

    # ─────────────────────────────────────────────────────────────────────
    #  FACTS MANAGEMENT
    # ─────────────────────────────────────────────────────────────────────

    def add_fact(self, user_id: str, fact: str, learned_from: str = "conversation"):
        """Add a fact about a user. Deduplicates automatically."""
        conn = self._get_connection()
        cursor = conn.cursor()

        # Get user's numeric ID
        cursor.execute("SELECT id FROM users WHERE user_id = ?", (user_id,))
        user_row = cursor.fetchone()
        if not user_row:
            conn.close()
            return False

        user_pk = user_row[0]

        try:
            cursor.execute("""
                INSERT INTO user_facts (user_id, fact, learned_from)
                VALUES (?, ?, ?)
            """, (user_pk, fact.strip(), learned_from))
            conn.commit()
            conn.close()
            return True
        except sqlite3.IntegrityError:
            # Fact already exists
            conn.close()
            return False

    def get_facts(self, user_id: str) -> List[str]:
        """Get all facts for a user."""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT id FROM users WHERE user_id = ?", (user_id,))
        user_row = cursor.fetchone()
        if not user_row:
            conn.close()
            return []

        user_pk = user_row[0]

        cursor.execute(
            "SELECT fact FROM user_facts WHERE user_id = ? ORDER BY created_at DESC",
            (user_pk,)
        )
        facts = [row[0] for row in cursor.fetchall()]
        conn.close()
        return facts

    def delete_fact(self, user_id: str, fact: str) -> bool:
        """Delete a specific fact."""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT id FROM users WHERE user_id = ?", (user_id,))
        user_row = cursor.fetchone()
        if not user_row:
            conn.close()
            return False

        user_pk = user_row[0]

        cursor.execute(
            "DELETE FROM user_facts WHERE user_id = ? AND fact = ?",
            (user_pk, fact)
        )
        conn.commit()
        success = cursor.rowcount > 0
        conn.close()
        return success

    # ─────────────────────────────────────────────────────────────────────
    #  PREFERENCES MANAGEMENT
    # ─────────────────────────────────────────────────────────────────────

    def add_preference(self, user_id: str, preference: str,
                      preference_type: str = "interest", learned_from: str = "conversation"):
        """Add a preference about a user."""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT id FROM users WHERE user_id = ?", (user_id,))
        user_row = cursor.fetchone()
        if not user_row:
            conn.close()
            return False

        user_pk = user_row[0]

        try:
            cursor.execute("""
                INSERT INTO user_preferences (user_id, preference, preference_type, learned_from)
                VALUES (?, ?, ?, ?)
            """, (user_pk, preference.strip(), preference_type, learned_from))
            conn.commit()
            conn.close()
            return True
        except sqlite3.IntegrityError:
            conn.close()
            return False

    def get_preferences(self, user_id: str) -> List[str]:
        """Get all preferences for a user."""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT id FROM users WHERE user_id = ?", (user_id,))
        user_row = cursor.fetchone()
        if not user_row:
            conn.close()
            return []

        user_pk = user_row[0]

        cursor.execute(
            "SELECT preference FROM user_preferences WHERE user_id = ? ORDER BY created_at DESC",
            (user_pk,)
        )
        prefs = [row[0] for row in cursor.fetchall()]
        conn.close()
        return prefs

    def delete_preference(self, user_id: str, preference: str) -> bool:
        """Delete a specific preference."""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT id FROM users WHERE user_id = ?", (user_id,))
        user_row = cursor.fetchone()
        if not user_row:
            conn.close()
            return False

        user_pk = user_row[0]

        cursor.execute(
            "DELETE FROM user_preferences WHERE user_id = ? AND preference = ?",
            (user_pk, preference)
        )
        conn.commit()
        success = cursor.rowcount > 0
        conn.close()
        return success

    # ─────────────────────────────────────────────────────────────────────
    #  MANUAL ENTRY LOGGING
    # ─────────────────────────────────────────────────────────────────────

    def log_manual_entry(self, user_id: str, entry_type: str,
                         entry_content: str, entered_by: str = "admin", notes: str = ""):
        """Log a manual entry for audit trail."""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT id FROM users WHERE user_id = ?", (user_id,))
        user_row = cursor.fetchone()
        if not user_row:
            conn.close()
            return False

        user_pk = user_row[0]

        cursor.execute("""
            INSERT INTO manual_entry_log (user_id, entry_type, entry_content, entered_by, notes)
            VALUES (?, ?, ?, ?, ?)
        """, (user_pk, entry_type, entry_content, entered_by, notes))

        conn.commit()
        conn.close()
        return True

    # ─────────────────────────────────────────────────────────────────────
    #  BUILD MEMORY BLOCK (compatible with existing ELLA code)
    # ─────────────────────────────────────────────────────────────────────

    def build_memory_block(self, user_id: str) -> str:
        """
        Build a <MEMORY> context block from database for injection into Ella's prompt.
        Compatible with existing ELLA system.
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        user_row = cursor.fetchone()
        if not user_row:
            conn.close()
            return ""

        user_dict = dict(user_row)
        user_pk = user_dict['id']

        # Fetch facts, preferences, notes
        cursor.execute(
            "SELECT fact FROM user_facts WHERE user_id = ? ORDER BY created_at DESC",
            (user_pk,)
        )
        facts = [row[0] for row in cursor.fetchall()]

        cursor.execute(
            "SELECT preference FROM user_preferences WHERE user_id = ? ORDER BY created_at DESC",
            (user_pk,)
        )
        prefs = [row[0] for row in cursor.fetchall()]

        cursor.execute(
            "SELECT note FROM user_notes WHERE user_id = ? ORDER BY created_at DESC",
            (user_pk,)
        )
        notes = [row[0] for row in cursor.fetchall()]

        conn.close()

        # Format memory block
        name = user_dict['name']
        role = user_dict['role']
        conversation_count = user_dict['conversation_count']
        last_seen = user_dict['last_seen'] or "never"

        lines = [f"<MEMORY: {name}>"]

        if role in ("creator", "boyfriend"):
            lines.append(f"Relationship: {role.upper()}")

        if conversation_count > 0:
            date_str = last_seen[:10] if len(last_seen) >= 10 else last_seen
            lines.append(f"You have spoken with {name} {conversation_count} time(s). Last session: {date_str}.")
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

        if prefs:
            lines.append("Their preferences and interests:")
            for p in prefs:
                lines.append(f"  • {p}")

        lines.append("</MEMORY>")
        return "\n".join(lines)
