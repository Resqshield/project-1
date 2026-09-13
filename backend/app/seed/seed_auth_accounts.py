"""Development-only representative authentication accounts for B03."""

from __future__ import annotations

import os

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.db.session import get_sync_engine
from backend.app.models.users import User
from backend.app.security.auth import generate_mfa_secret, hash_password
from backend.app.security.rbac import Role


DEV_AUTH_PASSWORD = os.getenv(
    "RESQ_DEV_AUTH_PASSWORD",
    "ResQShieldDev123!",
)


REPRESENTATIVE_ACCOUNTS: tuple[tuple[str, str, Role, bool], ...] = (
    ("citizen@resqshield.local", "Development Citizen", Role.CITIZEN, False),
    ("responder@resqshield.local", "Development Field Responder", Role.FIELD_RESPONDER, False),
    ("district.officer@resqshield.local", "Development District Officer", Role.DISTRICT_OFFICER, True),
    ("ndrf.control@resqshield.local", "Development NDRF Control Room", Role.NDRF_CONTROL_ROOM, True),
    ("sdm.collector@resqshield.local", "Development SDM Collector", Role.SDM_COLLECTOR, True),
    ("pwd.engineer@resqshield.local", "Development PWD Engineer", Role.PWD_ENGINEER, False),
    ("police@resqshield.local", "Development Police", Role.POLICE, False),
    ("shelter.operator@resqshield.local", "Development Shelter Operator", Role.SHELTER_OPERATOR, False),
    ("health@resqshield.local", "Development Health Department", Role.HEALTH_DEPARTMENT, False),
    ("admin@resqshield.local", "Development System Admin", Role.SYSTEM_ADMIN, True),
    ("research@resqshield.local", "Development Research User", Role.RESEARCH, False),
)


def seed_auth_accounts(session: Session) -> dict[str, object]:
    """Create or update representative B03 accounts idempotently."""

    created = 0
    updated = 0
    mfa_accounts: dict[str, str] = {}

    for email, full_name, role, needs_mfa in REPRESENTATIVE_ACCOUNTS:
        user = session.scalars(
            select(User).where(User.email == email)
        ).first()

        if user is None:
            user = User(
                email=email,
                full_name=full_name,
                role_name=role.value,
                password_hash=hash_password(DEV_AUTH_PASSWORD),
                mfa_secret=generate_mfa_secret() if needs_mfa else None,
                mfa_enabled=needs_mfa,
                is_active=True,
            )
            session.add(user)
            created += 1
        else:
            user.full_name = full_name
            user.role_name = role.value
            user.is_active = True

            if not user.password_hash:
                user.password_hash = hash_password(DEV_AUTH_PASSWORD)

            if needs_mfa:
                if not user.mfa_secret:
                    user.mfa_secret = generate_mfa_secret()
                user.mfa_enabled = True
            else:
                user.mfa_enabled = False

            updated += 1

        if needs_mfa and user.mfa_secret:
            mfa_accounts[email] = user.mfa_secret

    session.commit()

    return {
        "created": created,
        "updated": updated,
        "total": len(REPRESENTATIVE_ACCOUNTS),
        "mfa_accounts": mfa_accounts,
    }


def main() -> None:
    print("WARNING: development authentication seed only.")

    engine = get_sync_engine()

    with Session(engine) as session:
        result = seed_auth_accounts(session)

    print(
        f"Auth seed complete: "
        f"{result['created']} created, "
        f"{result['updated']} updated, "
        f"{result['total']} total."
    )


if __name__ == "__main__":
    main()
