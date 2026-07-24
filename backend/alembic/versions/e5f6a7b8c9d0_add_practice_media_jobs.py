"""add practice media jobs

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-07-23
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e5f6a7b8c9d0"
down_revision: Union[str, None] = "d4e5f6a7b8c9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "practice_media_jobs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("media_job_id", sa.String(length=64), nullable=False),
        sa.Column("practice_session_fk", sa.Integer(), nullable=False),
        sa.Column("practice_turn_fk", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("speech_text", sa.Text(), nullable=False),
        sa.Column("provider", sa.String(length=40), nullable=False),
        sa.Column("settings_payload", sa.JSON(), nullable=False),
        sa.Column("audio_relpath", sa.String(length=255), nullable=True),
        sa.Column("video_relpath", sa.String(length=255), nullable=True),
        sa.Column("error_code", sa.String(length=80), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["practice_session_fk"], ["practice_sessions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["practice_turn_fk"], ["practice_turns.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("media_job_id"),
        sa.UniqueConstraint("practice_turn_fk", name="uq_practice_media_job_turn"),
    )
    op.create_index(
        "ix_practice_media_job_media_job_id",
        "practice_media_jobs",
        ["media_job_id"],
        unique=True,
    )
    op.create_index(
        "ix_practice_media_job_practice_session_fk",
        "practice_media_jobs",
        ["practice_session_fk"],
    )
    op.create_index(
        "ix_practice_media_job_practice_turn_fk",
        "practice_media_jobs",
        ["practice_turn_fk"],
    )
    op.create_index("ix_practice_media_job_status", "practice_media_jobs", ["status"])
    op.create_index(
        "ix_practice_media_job_session_status",
        "practice_media_jobs",
        ["practice_session_fk", "status"],
    )


def downgrade() -> None:
    op.drop_index("ix_practice_media_job_session_status", table_name="practice_media_jobs")
    op.drop_index("ix_practice_media_job_status", table_name="practice_media_jobs")
    op.drop_index("ix_practice_media_job_practice_turn_fk", table_name="practice_media_jobs")
    op.drop_index("ix_practice_media_job_practice_session_fk", table_name="practice_media_jobs")
    op.drop_index("ix_practice_media_job_media_job_id", table_name="practice_media_jobs")
    op.drop_table("practice_media_jobs")
