"""서버 재시작 시 중단된 실행 복구 — 무한 폴링 방지 (2026-07-17 통합 리뷰 후속)."""

# ruff: noqa: E402 -- 테스트 DB 환경변수를 app import 전에 설정해야 한다.

import os
import tempfile

_tmp = tempfile.mkdtemp()
os.environ["DATABASE_URL"] = f"sqlite:///{_tmp}/test_stale.db"
os.environ["JWT_SECRET"] = "test-secret-at-least-32-bytes-long"

from app.core.db import Base, SessionLocal, engine
from app.models.analysis import AnalysisRun, ExtractionRun
from app.models.contract import ContractProject
from app.models.user import User
from app.workers.analysis import fail_stale_runs


def test_stale_pending_running_marked_failed():
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        user = User(username="u", email="u@test.com", password_hash="x")
        db.add(user)
        db.flush()
        contract = ContractProject(user_id=user.id, title="복구 테스트")
        db.add(contract)
        db.flush()
        db.add(ExtractionRun(contract_id=contract.id, status="running"))
        db.add(
            AnalysisRun(
                contract_id=contract.id, analysis_run_id="stale-1",
                input_snapshot_id="snap-x", input_snapshot={}, status="pending",
            )
        )
        # 규칙 분석은 끝났지만 생성 단계에서 중단된 경우
        db.add(
            AnalysisRun(
                contract_id=contract.id, analysis_run_id="stale-2",
                input_snapshot_id="snap-y", input_snapshot={}, status="completed",
                result={}, generation_status="running",
            )
        )
        db.commit()
        cid = contract.id

    fail_stale_runs()

    with SessionLocal() as db:
        assert db.query(ExtractionRun).filter_by(contract_id=cid).one().status == "failed"
        stale1 = db.query(AnalysisRun).filter_by(analysis_run_id="stale-1").one()
        assert stale1.status == "failed" and stale1.error
        stale2 = db.query(AnalysisRun).filter_by(analysis_run_id="stale-2").one()
        assert stale2.status == "completed"  # 규칙 결과는 건드리지 않음
        assert stale2.generation_status == "failed" and stale2.generation_error
