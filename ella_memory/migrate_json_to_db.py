import json
from pathlib import Path
from database_memory_manager import DatabaseMemoryManager

def main():
    db = DatabaseMemoryManager()
    user_json_dir = Path("ella_memory/users/")

    if not user_json_dir.exists():
        print("No user JSON directory found.")
        return

    for json_file in user_json_dir.glob("*.json"):
        with open(json_file, "r") as f:
            profile = json.load(f)

        user_id = profile.get("id")
        print(f"Migrating user: {user_id} ({json_file})")
        # Save core profile (name, role, etc.) and notes
        db.save(profile)
        # Add facts
        for fact in profile.get("facts", []):
            db.add_memories(user_id, [fact], [])
        # Add preferences
        for pref in profile.get("preferences", []):
            db.add_memories(user_id, [], [pref])
        print(f"  - facts: {len(profile.get('facts', []))}")
        print(f"  - prefs: {len(profile.get('preferences', []))}")
        print(f"  - notes: {len(profile.get('notes', []))}")
    print("Migration complete!")

if __name__ == '__main__':
    main()