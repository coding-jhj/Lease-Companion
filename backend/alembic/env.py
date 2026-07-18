"""Alembic 마이그레이션 환경. DB URL은 앱과 동일하게 .env의 DATABASE_URL을 사용한다.

ALEMBIC_DATABASE_URL 환경변수가 있으면 우선한다 (baseline 검증용 scratch DB 등).
"""

from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine, pool

# 앱과 동일한 Base·URL 로딩 (.env 포함)
import os

from app.core.db import DATABASE_URL, Base

# autogenerate가 전체 모델을 보도록 모든 모델 모듈을 import한다
import app.models.analysis  # noqa: F401
import app.models.checklist  # noqa: F401
import app.models.contract  # noqa: F401
import app.models.document  # noqa: F401
import app.models.feedback  # noqa: F401
import app.models.user  # noqa: F401

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

_url = os.environ.get("ALEMBIC_DATABASE_URL", DATABASE_URL)


def run_migrations_offline() -> None:
    """SQL 스크립트만 출력하는 offline 모드."""
    context.configure(
        url=_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """DB에 직접 적용하는 online 모드."""
    connectable = create_engine(_url, poolclass=pool.NullPool)
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
