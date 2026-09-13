"""Add B03 authentication and MFA fields to users.

Revision ID: 0002_b03_auth_fields
Revises: 0001_initial_schema
"""

from __future__ import annotations

from typing import Union

import sqlalchemy as sa
from alembic import op


revision: str = "0002_b03_auth_fields"
down_revision: Union[str, None] = "0001_initial_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add authentication persistence fields."""

    op.add_column(
        "users",
        sa.Column(
            "password_hash",
            sa.String(length=512),
            nullable=True,
        ),
    )

    op.add_column(
        "users",
        sa.Column(
            "mfa_secret",
            sa.String(length=128),
            nullable=True,
        ),
    )

    op.add_column(
        "users",
        sa.Column(
            "mfa_enabled",
            sa.Boolean(),
            server_default=sa.false(),
            nullable=False,
        ),
    )


def downgrade() -> None:
    """Remove B03 authentication persistence fields."""

    op.drop_column("users", "mfa_enabled")
    op.drop_column("users", "mfa_secret")
    op.drop_column("users", "password_hash")
