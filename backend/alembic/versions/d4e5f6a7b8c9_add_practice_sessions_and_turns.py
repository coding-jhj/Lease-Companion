"""practice_sessions와 practice_turns 추가

Revision ID: d4e5f6a7b8c9
Revises: c8b3bd1c03c6
Create Date: 2026-07-22
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "d4e5f6a7b8c9"
down_revision: Union[str, Sequence[str], None] = "c8b3bd1c03c6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_JSON = sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql")


def upgrade() -> None:
    op.create_table(
        "practice_sessions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("practice_session_id", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("scenario_id", sa.String(length=80), nullable=False),
        sa.Column("scenario_version", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("current_state", sa.String(length=40), nullable=False),
        sa.Column("current_turn_id", sa.String(length=40), nullable=True),
        sa.Column("confirmed_action_ids", _JSON, nullable=False),
        sa.Column("selected_action", sa.String(length=30), nullable=True),
        sa.Column("state_payload", _JSON, nullable=False),
        sa.Column("result", _JSON, nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_practice_sessions_practice_session_id", "practice_sessions", ["practice_session_id"], unique=True
    )
    op.create_index("ix_practice_sessions_user_id", "practice_sessions", ["user_id"])
    op.create_index("ix_practice_sessions_scenario_id", "practice_sessions", ["scenario_id"])
    op.create_index("ix_practice_sessions_status", "practice_sessions", ["status"])

    op.create_table(
        "practice_turns",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("practice_turn_id", sa.String(length=64), nullable=False),
        sa.Column("practice_session_fk", sa.Integer(), nullable=False),
        sa.Column("turn_id", sa.String(length=40), nullable=False),
        sa.Column("attempt_no", sa.Integer(), nullable=False),
        sa.Column("request_id", sa.String(length=64), nullable=False),
        sa.Column("input_payload", _JSON, nullable=False),
        sa.Column("evaluation_payload", _JSON, nullable=True),
        sa.Column("dialogue_response", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["practice_session_fk"], ["practice_sessions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("practice_session_fk", "request_id", name="uq_practice_turn_session_request"),
    )
    op.create_index("ix_practice_turns_practice_turn_id", "practice_turns", ["practice_turn_id"], unique=True)
    op.create_index("ix_practice_turns_practice_session_fk", "practice_turns", ["practice_session_fk"])
    op.create_index(
        "ix_practice_turn_session_turn_attempt",
        "practice_turns",
        ["practice_session_fk", "turn_id", "attempt_no"],
    )


def downgrade() -> None:
    op.drop_index("ix_practice_turn_session_turn_attempt", table_name="practice_turns")
    op.drop_index("ix_practice_turns_practice_session_fk", table_name="practice_turns")
    op.drop_index("ix_practice_turns_practice_turn_id", table_name="practice_turns")
    op.drop_table("practice_turns")
    op.drop_index("ix_practice_sessions_status", table_name="practice_sessions")
    op.drop_index("ix_practice_sessions_scenario_id", table_name="practice_sessions")
    op.drop_index("ix_practice_sessions_user_id", table_name="practice_sessions")
    op.drop_index("ix_practice_sessions_practice_session_id", table_name="practice_sessions")
    op.drop_table("practice_sessions")
