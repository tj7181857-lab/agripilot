"""Create or link local AgriPilot login accounts without exposing password hashes."""
from __future__ import annotations

import argparse
import getpass
import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.join(ROOT, "agripilot")
sys.path.insert(0, PKG)

import db as store
from werkzeug.security import generate_password_hash


def credentials(username_arg: str | None) -> tuple[str, str]:
    username = (username_arg or input("Username or email: ")).strip().lower()
    if not username or len(username) > 120 or any(ch.isspace() for ch in username):
        raise SystemExit("Enter a valid username or email.")
    password = getpass.getpass("Password (at least 10 characters): ")
    confirm = getpass.getpass("Confirm password: ")
    if len(password) < 10:
        raise SystemExit("Password must be at least 10 characters.")
    if password != confirm:
        raise SystemExit("Passwords do not match.")
    return username, generate_password_hash(password)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    link = sub.add_parser("link-existing", help="set farmer login on an existing user row")
    link.add_argument("--user-id", required=True, type=int)
    link.add_argument("--username")
    analyst = sub.add_parser("create-analyst", help="create a separate analyst account")
    analyst.add_argument("--name", required=True)
    analyst.add_argument("--username")
    args = parser.parse_args()

    store.init_db()
    username, password_hash = credentials(args.username)
    if store.user_by_username(username):
        raise SystemExit("That username/email is already registered.")
    if args.command == "link-existing":
        if not store.get_by_id("users", args.user_id):
            raise SystemExit(f"User id {args.user_id} does not exist.")
        store.set_user_login(args.user_id, username, password_hash, role="farmer")
        print(f"Farmer login enabled for existing user id {args.user_id}; existing farm links were preserved.")
    else:
        user_id = store.create_account(
            name=args.name.strip(), username=username, password_hash=password_hash,
            language="en", role="analyst",
        )
        print(f"Analyst account created (user id {user_id}). Keep analyst credentials separate from farmer accounts.")


if __name__ == "__main__":
    main()
