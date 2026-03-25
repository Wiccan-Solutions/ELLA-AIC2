# ella_admin_cli.py
"""
Administrative CLI tool for manually entering data into ELLA's database.
Run: python ella_admin_cli.py
"""

from database_manager import DatabaseManager

def main():
    db = DatabaseManager()

    print("\n" + "=" * 60)
    print("  ELLA Memory Database — Admin CLI")
    print("=" * 60 + "\n")

    while True:
        print("\nOptions:")
        print("  1. View user profile")
        print("  2. Add fact to user")
        print("  3. Add preference to user")
        print("  4. Delete fact from user")
        print("  5. Delete preference from user")
        print("  6. Create new user")
        print("  7. Exit")

        choice = input("\nSelect option (1-7): ").strip()

        if choice == "1":
            view_user(db)
        elif choice == "2":
            add_fact(db)
        elif choice == "3":
            add_preference(db)
        elif choice == "4":
            delete_fact(db)
        elif choice == "5":
            delete_preference(db)
        elif choice == "6":
            create_user(db)
        elif choice == "7":
            print("\nGoodbye!\n")
            break
        else:
            print("Invalid option. Try again.")

def view_user(db):
    user_id = input("\nEnter user_id to view: ").strip()
    user = db.get_user_by_id(user_id)

    if not user:
        print(f"User '{user_id}' not found.")
        return

    print(f"\n{'─' * 60}")
    print(f"User: {user['name']} (ID: {user['user_id']})")
    print(f"Role: {user['role']} | Tone: {user['tone']}")
    print(f"Conversations: {user['conversation_count']}")
    print(f"Last Seen: {user['last_seen'] or 'Never'}")
    print(f"{'─' * 60}")

    facts = db.get_facts(user_id)
    if facts:
        print("\nFacts:")
        for f in facts:
            print(f"  • {f}")
    else:
        print("\nNo facts recorded.")

    prefs = db.get_preferences(user_id)
    if prefs:
        print("\nPreferences:")
        for p in prefs:
            print(f"  • {p}")
    else:
        print("No preferences recorded.")

    print()

def add_fact(db):
    user_id = input("\nEnter user_id: ").strip()
    if not db.get_user_by_id(user_id):
        print(f"User '{user_id}' not found.")
        return

    fact = input("Enter fact: ").strip()
    if db.add_fact(user_id, fact, learned_from="manual_entry"):
        db.log_manual_entry(user_id, "fact", fact)
        print(f"✓ Fact added to {user_id}.")
    else:
        print("Fact already exists for this user.")

def add_preference(db):
    user_id = input("\nEnter user_id: ").strip()
    if not db.get_user_by_id(user_id):
        print(f"User '{user_id}' not found.")
        return

    preference = input("Enter preference: ").strip()
    pref_type = input("Preference type (interest/dislike/communication_style/hobby) [interest]: ").strip() or "interest"

    if db.add_preference(user_id, preference, preference_type=pref_type, learned_from="manual_entry"):
        db.log_manual_entry(user_id, "preference", preference, notes=f"type: {pref_type}")
        print(f"✓ Preference added to {user_id}.")
    else:
        print("Preference already exists for this user.")

def delete_fact(db):
    user_id = input("\nEnter user_id: ").strip()
    facts = db.get_facts(user_id)

    if not facts:
        print("No facts found for this user.")
        return

    print("\nFacts:")
    for i, f in enumerate(facts, 1):
        print(f"  {i}. {f}")

    choice = input("\nSelect fact number to delete (or 'cancel'): ").strip()
    if choice.lower() == "cancel":
        return

    try:
        idx = int(choice) - 1
        if 0 <= idx < len(facts):
            if db.delete_fact(user_id, facts[idx]):
                print(f"✓ Fact deleted.")
            else:
                print("Failed to delete fact.")
        else:
            print("Invalid selection.")
    except ValueError:
        print("Invalid input.")

def delete_preference(db):
    user_id = input("\nEnter user_id: ").strip()
    prefs = db.get_preferences(user_id)

    if not prefs:
        print("No preferences found for this user.")
        return

    print("\nPreferences:")
    for i, p in enumerate(prefs, 1):
        print(f"  {i}. {p}")

    choice = input("\nSelect preference number to delete (or 'cancel'): ").strip()
    if choice.lower() == "cancel":
        return

    try:
        idx = int(choice) - 1
        if 0 <= idx < len(prefs):
            if db.delete_preference(user_id, prefs[idx]):
                print(f"✓ Preference deleted.")
            else:
                print("Failed to delete preference.")
        else:
            print("Invalid selection.")
    except ValueError:
        print("Invalid input.")

def create_user(db):
    name = input("\nEnter user's full name: ").strip()
    user_id = name.lower().replace(" ", "_")
    role = input("Role (user/creator/boyfriend) [user]: ").strip() or "user"
    tone = input("Tone (friendly/professional_warm/loving_playful) [friendly]: ").strip() or "friendly"

    db.get_or_create_user(user_id, name, role=role, tone=tone)
    print(f"✓ User '{name}' created with ID '{user_id}'.")

if __name__ == "__main__":
    main()
