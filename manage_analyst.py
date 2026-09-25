"""Create the single analyst account or reset its password securely.

Run: python manage_analyst.py [username]
The password is entered with terminal echo disabled and stored only as a hash.
"""
from __future__ import annotations
import getpass
import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(ROOT, "agripilot"))
import db as store
from paths import db_path
from werkzeug.security import generate_password_hash

def main() -> int:
    username = (sys.argv[1] if len(sys.argv) > 1 else "analyst@agripilot.local").strip().lower()
    if not username or any(c.isspace() for c in username):
        print("Use a non-empty username without spaces.", file=sys.stderr)
        return 2
    store.init_db(seed=False)
    accounts = store.list_rows("users", "role = ?", ("analyst",), "id ASC", 5)
    if len(accounts) > 1:
        print("More than one analyst account exists; refusing to create or reset one automatically.", file=sys.stderr)
        return 3
    password = getpass.getpass("New analyst password (minimum 14 characters): ")
    confirm = getpass.getpass("Confirm password: ")
    if len(password) < 14 or password != confirm:
        print("Passwords must match and contain at least 14 characters.", file=sys.stderr)
        return 2
    password_hash = generate_password_hash(password)
    if accounts:
        user = accounts[0]
        collision = store.user_by_username(username)
        if collision and collision["id"] != user["id"]:
            print("That username is already assigned to another account.", file=sys.stderr)
            return 4
        store.set_user_login(user["id"], username, password_hash, "analyst")
        print(f"Analyst password reset for {username}; database: {db_path()}")
    else:
        if store.user_by_username(username):
            print("That username is already assigned to a non-analyst account; refusing role conversion.", file=sys.stderr)
            return 4
        store.create_account(name="AgriPilot Analyst", username=username, password_hash=password_hash, role="analyst")
        print(f"Single analyst account created: {username}; database: {db_path()}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
