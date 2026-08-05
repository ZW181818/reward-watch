from __future__ import annotations

import argparse
import getpass
import sys
from pathlib import Path

from sqlalchemy import func
from sqlalchemy.orm import Session


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.admin_security import hash_password  # noqa: E402
from app.database import AdminUserRow, initialize_database  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Create or reset a Reward Watch administrator.")
    parser.add_argument("--email", required=True)
    parser.add_argument("--password", help="Prefer omitting this option to use the hidden prompt.")
    args = parser.parse_args()

    email = args.email.strip().lower()
    password = args.password or getpass.getpass("Administrator password: ")
    password_hash = hash_password(password)
    engine = initialize_database()
    try:
        with Session(engine) as session, session.begin():
            user = session.query(AdminUserRow).filter(func.lower(AdminUserRow.email) == email).one_or_none()
            if user is None:
                session.add(AdminUserRow(email=email, password_hash=password_hash, role="admin"))
                action = "Created"
            else:
                user.password_hash = password_hash
                user.is_active = True
                action = "Reset"
        print(f"{action} administrator {email}")
    finally:
        engine.dispose()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
