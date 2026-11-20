"""
Assign a role to a user — used to bootstrap the first admin.

    python set_user_role.py <username> <role>

Example:
    python set_user_role.py alice admin
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "web_app"))

from entity.database import SessionLocal
from entity.role.entity import Role
from entity.user.entity import User


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print(__doc__)
        return 2
    username, role = argv[1], argv[2]

    session = SessionLocal()
    try:
        if not session.get(Role, role):
            print(f"Role '{role}' does not exist.")
            return 1
        user = session.query(User).filter(User.username == username).first()
        if not user:
            print(f"User '{username}' not found.")
            return 1
        user.role = role
        session.commit()
        print(f"{username} is now '{role}'.")
        return 0
    finally:
        SessionLocal.remove()


if __name__ == "__main__":
    sys.exit(main(sys.argv))
