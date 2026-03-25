# ella_admin_cli.py

from ella_memory.database_manager import DatabaseManager

def main():
    """Main entry point for the ELLA admin CLI."""
    db_manager = DatabaseManager()
    # Add CLI logic here
    print("ELLA Admin CLI started")


if __name__ == "__main__":
    main()