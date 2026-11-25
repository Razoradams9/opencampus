"""Operator commands. Privileged accounts are created here, never via the API.

    python -m app.cli create-platform-admin --email ops@example.org --name "Ops"
    python -m app.cli seed-demo
    python -m app.cli purge-rate-limits

Passwords are read from OPENCAMPUS_CLI_PASSWORD if set, otherwise prompted.
"""

import argparse
import getpass
import os
import sys

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.db.session import session_factory, set_db_context
from app.models import Institution, Membership, MembershipRole, MembershipStatus, User
from app.schemas.auth import PASSWORD_MAX, PASSWORD_MIN
from app.services.auth import normalise_email


def _password() -> str:
    password = os.getenv("OPENCAMPUS_CLI_PASSWORD") or getpass.getpass("Password: ")
    if not PASSWORD_MIN <= len(password) <= PASSWORD_MAX:
        sys.exit(f"Password must be {PASSWORD_MIN}-{PASSWORD_MAX} characters")
    return password


def _get_or_create_user(db: Session, email: str, name: str, password_hash: str) -> User:
    user = db.scalar(select(User).where(User.email == normalise_email(email)))
    if user is None:
        user = User(email=normalise_email(email), full_name=name, password_hash=password_hash)
        db.add(user)
        db.flush()
    return user


def _ensure_membership(db: Session, user: User, institution: Institution, role: MembershipRole) -> None:
    set_db_context(db, tenant_id=institution.id)
    membership = db.scalar(
        select(Membership).where(Membership.institution_id == institution.id, Membership.user_id == user.id)
    )
    if membership is None:
        db.add(Membership(institution_id=institution.id, user_id=user.id, role=role, status=MembershipStatus.active))
        db.flush()
    set_db_context(db)


def create_platform_admin(email: str, name: str) -> None:
    with session_factory()() as db:
        user = _get_or_create_user(db, email, name, hash_password(_password()))
        user.is_platform_admin = True
        db.commit()
        print(f"Platform admin ready: {user.email}")


# Fictional demo data: reserved .example domains, invented names.
DEMO_INSTITUTIONS = [("aldermoor", "Aldermoor College"), ("halvard", "Halvard Institute of Technology")]
DEMO_USERS = [
    ("maya.okafor@aldermoor.example", "Maya Okafor", [("aldermoor", MembershipRole.student)]),
    ("lena.varga@aldermoor.example", "Lena Varga", [("aldermoor", MembershipRole.faculty)]),
    ("iris.moreau@aldermoor.example", "Iris Moreau", [("aldermoor", MembershipRole.college_admin)]),
    ("tomas.berg@halvard.example", "Tomas Berg", [("halvard", MembershipRole.student)]),
    (
        "sam.achebe@aldermoor.example",
        "Samuel Achebe",
        [("aldermoor", MembershipRole.faculty), ("halvard", MembershipRole.student)],
    ),
]


def seed_demo() -> None:
    password_hash = hash_password(_password())
    with session_factory()() as db:
        institutions: dict[str, Institution] = {}
        for slug, name in DEMO_INSTITUTIONS:
            institution = db.scalar(select(Institution).where(Institution.slug == slug))
            if institution is None:
                institution = Institution(slug=slug, name=name, allow_self_registration=True)
                db.add(institution)
                db.flush()
            institutions[slug] = institution

        for email, name, memberships in DEMO_USERS:
            user = _get_or_create_user(db, email, name, password_hash)
            for slug, role in memberships:
                _ensure_membership(db, user, institutions[slug], role)
        db.commit()

    print("Demo data ready (all accounts share the password you entered):")
    for email, _, memberships in DEMO_USERS:
        print(f"  {email:34} " + ", ".join(f"{role.value}@{slug}" for slug, role in memberships))


def main() -> None:
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    commands = parser.add_subparsers(dest="command", required=True)
    admin = commands.add_parser("create-platform-admin", help="create or promote a platform administrator")
    admin.add_argument("--email", required=True)
    admin.add_argument("--name", required=True)
    commands.add_parser("seed-demo", help="create fictional demo institutions and users")
    commands.add_parser("purge-rate-limits", help="delete expired rate-limit counters")
    args = parser.parse_args()

    if args.command == "create-platform-admin":
        create_platform_admin(args.email, args.name)
    elif args.command == "purge-rate-limits":
        from app.core.config import get_settings
        from app.services.rate_limit import get_rate_limiter

        print(f"Deleted {get_rate_limiter(get_settings()).purge_expired()} expired rate-limit counters")
    else:
        seed_demo()


if __name__ == "__main__":
    main()
