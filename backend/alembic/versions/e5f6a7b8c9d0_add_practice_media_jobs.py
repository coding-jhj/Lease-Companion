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
    table_name = "practice_media_jobs"
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if table_name not in inspector.get_table_names():
        op.create_table(
            table_name,
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
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=False,
            ),
            sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(
                ["practice_session_fk"],
                ["practice_sessions.id"],
                ondelete="CASCADE",
            ),
            sa.ForeignKeyConstraint(
                ["practice_turn_fk"],
                ["practice_turns.id"],
                ondelete="CASCADE",
            ),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("media_job_id"),
            sa.UniqueConstraint(
                "practice_turn_fk",
                name="uq_practice_media_job_turn",
            ),
        )
        inspector = sa.inspect(bind)
    else:
        required_columns = {
            "id",
            "media_job_id",
            "practice_session_fk",
            "practice_turn_fk",
            "status",
            "speech_text",
            "provider",
            "settings_payload",
            "audio_relpath",
            "video_relpath",
            "error_code",
            "created_at",
            "started_at",
            "completed_at",
        }
        existing_columns = {
            column["name"] for column in inspector.get_columns(table_name)
        }
        missing_columns = sorted(required_columns - existing_columns)
        if missing_columns:
            raise RuntimeError(
                "practice_media_jobs already exists but is incomplete; "
                f"missing columns: {', '.join(missing_columns)}"
            )

    # app startup의 create_all로 동일 테이블이 먼저 만들어진 로컬 DB도 안전하게
    # Alembic 관리 상태로 전환한다. 이름이 달라도 같은 컬럼 인덱스면 중복 생성하지 않는다.
    existing_index_columns = {
        tuple(index.get("column_names") or ())
        for index in inspector.get_indexes(table_name)
    }
    expected_indexes = (
        ("ix_practice_media_job_media_job_id", ("media_job_id",), True),
        (
            "ix_practice_media_job_practice_session_fk",
            ("practice_session_fk",),
            False,
        ),
        ("ix_practice_media_job_practice_turn_fk", ("practice_turn_fk",), False),
        ("ix_practice_media_job_status", ("status",), False),
        (
            "ix_practice_media_job_session_status",
            ("practice_session_fk", "status"),
            False,
        ),
    )
    for index_name, columns, unique in expected_indexes:
        if columns not in existing_index_columns:
            op.create_index(
                index_name,
                table_name,
                list(columns),
                unique=unique,
            )


def downgrade() -> None:
    op.drop_table("practice_media_jobs")
