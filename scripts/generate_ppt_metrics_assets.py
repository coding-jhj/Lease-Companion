"""2번 평가 리포트와 3번 엔진 호출 요약의 PPT용 CSV·SVG를 만든다."""

from __future__ import annotations

import argparse
import csv
import html
import json
from pathlib import Path
from typing import Any


KRW_PER_USD = 1470.0


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _nested(payload: dict[str, Any], *keys: str) -> float:
    value: Any = payload
    for key in keys:
        value = value[key]
    return float(value)


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


_TIER_STYLE = {
    # tier: (막대 색, 그룹 제목, 그룹 부제)
    "provider": (
        "#0D9488",
        "운영 경로 실측 — Gemini 3.5 Flash · Cohere rerank",
        "실제 서비스가 타는 경로. 발표에 쓸 성능 수치는 이 그룹이다",
    ),
    "regression": (
        "#2563EB",
        "로컬 회귀 기준선 — 외부 호출 0건",
        "정규식·BM25 폴백 경로. 코드 회귀 감지용이며 서비스 성능이 아님",
    ),
    "quality": (
        "#0D9488",
        "품질 측정 — 실제 검색·생성 결과",
        "개선 여지가 남아 있는 구간",
    ),
    "structural": (
        "#94A3B8",
        "해석 주의 — 구조적으로 100%가 나오는 값",
        "성능 근거로 쓰지 않는다",
    ),
}
_TIER_ORDER = ("provider", "quality", "regression", "structural")


def _evaluation_svg(rows: list[dict[str, Any]], path: Path) -> None:
    width = 1600
    body: list[str] = []
    y = 158
    for tier in _TIER_ORDER:
        group = [row for row in rows if row.get("tier") == tier]
        if not group:
            continue
        color, title, subtitle = _TIER_STYLE[tier]
        body.extend(
            [
                f'<rect x="80" y="{y}" width="7" height="30" rx="3" fill="{color}"/>',
                f'<text x="102" y="{y + 24}" font-family="Malgun Gothic,sans-serif" font-size="23" font-weight="700" fill="#0F172A">{html.escape(title)}</text>',
                f'<text x="102" y="{y + 50}" font-family="Malgun Gothic,sans-serif" font-size="17" fill="#64748B">{html.escape(subtitle)}</text>',
            ]
        )
        y += 76
        for row in group:
            value = float(row["score"])
            bar = round(value * 620)
            body.extend(
                [
                    f'<text x="100" y="{y + 24}" font-family="Malgun Gothic,sans-serif" font-size="20" fill="#1E293B">{html.escape(str(row["metric"]))}</text>',
                    f'<rect x="560" y="{y}" width="620" height="33" rx="7" fill="#E2E8F0"/>',
                    f'<rect x="560" y="{y}" width="{bar}" height="33" rx="7" fill="{color}"/>',
                    f'<text x="1198" y="{y + 25}" font-family="Malgun Gothic,sans-serif" font-size="23" font-weight="700" fill="#0F172A">{value * 100:.2f}%</text>',
                    f'<text x="1320" y="{y + 25}" font-family="Malgun Gothic,sans-serif" font-size="16" fill="#64748B">{html.escape(str(row["sample"]))}</text>',
                    f'<text x="100" y="{y + 51}" font-family="Malgun Gothic,sans-serif" font-size="16" fill="#94A3B8">{html.escape(str(row.get("caveat", "")))}</text>',
                ]
            )
            y += 68
        y += 26
    footer_top = y + 6
    height = footer_top + 130
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#F8FAFC"/>',
        '<text x="80" y="76" font-family="Malgun Gothic,sans-serif" font-size="42" font-weight="700" fill="#0F172A">평가 리포트 핵심 결과</text>',
        '<text x="80" y="118" font-family="Malgun Gothic,sans-serif" font-size="21" fill="#475569">고정 합성 test · Offline ID RAGAS · Gemini judge Online RAGAS · 측정 성격별로 묶어 표기</text>',
        *body,
        f'<line x1="80" y1="{footer_top}" x2="1520" y2="{footer_top}" stroke="#CBD5E1" stroke-width="2"/>',
        f'<text x="80" y="{footer_top + 38}" font-family="Malgun Gothic,sans-serif" font-size="18" font-weight="700" fill="#B45309">해석: 발표에 쓸 성능 수치는 초록(운영 경로)이다. 파란 회귀 기준선의 100%는 정규식·BM25 폴백 경로 값이며 서비스 성능이 아니다.</text>',
        f'<text x="80" y="{footer_top + 70}" font-family="Malgun Gothic,sans-serif" font-size="17" fill="#64748B">규칙 엔진은 결정론이다. 규칙 감점 3건은 엔진이 아니라 Gemini 추출 오류(압류·신탁·금액 필드)가 전파된 결과다.</text>',
        f'<text x="80" y="{footer_top + 100}" font-family="Malgun Gothic,sans-serif" font-size="17" fill="#64748B">회색 두 항목은 성능 지표가 아니다 — 완주율은 실패 시 평가가 중단되는 구조, 일반 RAG는 정답 출처 화이트리스트 안에서만 검색된다. 전 구간 합성 test 기준.</text>',
        "</svg>",
    ]
    path.write_text("\n".join(parts) + "\n", encoding="utf-8")


def _cycle_rows(actual: dict[str, Any], simulation: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for label, payload in (
        ("실제 계약 점검", actual),
        ("시뮬레이션(3턴)", simulation),
    ):
        cost = float(payload["known_cost_usd"])
        calls = int(payload["call_count"])
        rows.append(
            {
                "mode": label,
                "cycle_count": 1,
                "provider_call_count": calls,
                "input_tokens": int(payload["input_tokens"]),
                "output_tokens": int(payload["output_tokens"]),
                "search_units": int(payload["search_units"]),
                "wall_clock_seconds": round(
                    int(payload["wall_clock_ms"]) / 1000, 3
                ),
                "known_cost_usd": round(cost, 9),
                "known_cost_krw": round(cost * KRW_PER_USD, 2),
                "average_cost_usd_per_provider_call": round(
                    cost / calls, 9
                ),
            }
        )
    return rows


def _cycle_svg(
    rows: list[dict[str, Any]],
    actual: dict[str, Any],
    path: Path,
) -> None:
    maximum = max(float(row["known_cost_usd"]) for row in rows)
    parts = [
        '<svg xmlns="http://www.w3.org/2000/svg" width="1600" height="900" viewBox="0 0 1600 900">',
        '<rect width="100%" height="100%" fill="#F8FAFC"/>',
        '<text x="85" y="85" font-family="Malgun Gothic,sans-serif" font-size="42" font-weight="700" fill="#0F172A">모드별 전체 1사이클 실측</text>',
        '<text x="85" y="128" font-family="Malgun Gothic,sans-serif" font-size="21" fill="#475569">Gemini 3.5 Flash Standard · Cohere Evaluation · 1 USD = 1,470 KRW 단순 환산</text>',
    ]
    colors = ("#2563EB", "#0D9488")
    for index, (row, color) in enumerate(zip(rows, colors)):
        y = 210 + index * 245
        cost = float(row["known_cost_usd"])
        bar = round(900 * cost / maximum)
        parts.extend(
            [
                f'<text x="90" y="{y}" font-family="Malgun Gothic,sans-serif" font-size="31" font-weight="700" fill="#0F172A">{html.escape(str(row["mode"]))}</text>',
                f'<rect x="90" y="{y + 35}" width="900" height="55" rx="10" fill="#E2E8F0"/>',
                f'<rect x="90" y="{y + 35}" width="{bar}" height="55" rx="10" fill="{color}"/>',
                f'<text x="1030" y="{y + 78}" font-family="Malgun Gothic,sans-serif" font-size="32" font-weight="700" fill="#0F172A">${cost:.6f}</text>',
                f'<text x="90" y="{y + 130}" font-family="Malgun Gothic,sans-serif" font-size="20" fill="#334155">약 {float(row["known_cost_krw"]):,.2f}원 · {row["provider_call_count"]}콜 · 입력 {int(row["input_tokens"]):,} / 출력 {int(row["output_tokens"]):,} tokens</text>',
                f'<text x="90" y="{y + 168}" font-family="Malgun Gothic,sans-serif" font-size="18" fill="#64748B">벽시계 {float(row["wall_clock_seconds"]):,.1f}초 · provider 1콜 평균 ${float(row["average_cost_usd_per_provider_call"]):.6f}</text>',
            ]
        )
    classification = actual.get("outcome", {}).get("classification_method")
    warning = (
        "실제 계약 사이클은 완주했으나 조항 분류가 504 후 safe_fallback."
        if classification != "provider"
        else "실제 계약 사이클의 조항 분류도 provider 경로로 완료."
    )
    parts.extend(
        [
            '<line x1="85" y1="745" x2="1515" y2="745" stroke="#CBD5E1" stroke-width="2"/>',
            f'<text x="85" y="790" font-family="Malgun Gothic,sans-serif" font-size="19" font-weight="700" fill="#B45309">주의: {html.escape(warning)}</text>',
            '<text x="85" y="828" font-family="Malgun Gothic,sans-serif" font-size="18" fill="#64748B">각 모드 1회 표본이므로 평균 추정의 기준선. embedding 응답은 token usage를 제공하지 않아 해당 비용이 0으로 기록됨.</text>',
            '<text x="85" y="862" font-family="Malgun Gothic,sans-serif" font-size="18" fill="#64748B">세금·환율·재시도·모델 가격 변경에 따라 실제 청구액은 달라질 수 있음.</text>',
            "</svg>",
        ]
    )
    path.write_text("\n".join(parts) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--offline", type=Path, required=True)
    parser.add_argument("--ragas-offline", type=Path, required=True)
    parser.add_argument("--ragas-online", type=Path, required=True)
    parser.add_argument("--actual-cycle", type=Path, required=True)
    parser.add_argument("--simulation-cycle", type=Path, required=True)
    parser.add_argument("--extraction-gemini", type=Path, required=True)
    parser.add_argument("--retrieval-provider", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()

    offline = _load(args.offline)
    ragas_offline = _load(args.ragas_offline)
    ragas_online = _load(args.ragas_online)
    extraction_gemini = _load(args.extraction_gemini)
    retrieval_provider = _load(args.retrieval_provider)
    actual = _load(args.actual_cycle)
    simulation = _load(args.simulation_cycle)
    args.output_dir.mkdir(parents=True, exist_ok=True)

    evaluation_rows = [
        {
            "metric": "필드 추출 정확도 (Gemini)",
            "score": _nested(extraction_gemini, "accuracy"),
            "sample": f'{extraction_gemini["field_count"]} fields · 10 cases',
            "evaluation_type": "provider",
            "tier": "provider",
            "caveat": (
                "운영 추출 경로 실측. 로컬 폴백 "
                f'{extraction_gemini["local_fallback_case_count"]}건. '
                "PII 토크나이저 버그 2건 수정 후 값"
            ),
        },
        {
            "metric": "R01–R10 규칙 상태 정확도 (Gemini 추출 입력)",
            "score": _nested(
                extraction_gemini, "rules_on_provider_extraction", "status_accuracy"
            ),
            "sample": "100 items / 10 cases",
            "evaluation_type": "provider",
            "tier": "provider",
            "caveat": "규칙 엔진은 결정론. 남은 감점 3건은 추출 오류가 전파된 것",
        },
        {
            "metric": "R01–R10 시급도 정확도 (Gemini 추출 입력)",
            "score": _nested(
                extraction_gemini, "rules_on_provider_extraction", "urgency_accuracy"
            ),
            "sample": "27 items",
            "evaluation_type": "provider",
            "tier": "provider",
            "caveat": "PII 버그로 62.96%까지 떨어졌던 값이 수정 후 회복",
        },
        {
            "metric": "특약 RAG Source Precision (운영 검색)",
            "score": _nested(
                retrieval_provider, "special_clauses", "source_macro_context_precision"
            ),
            "sample": "6 cases",
            "evaluation_type": "provider",
            "tier": "provider",
            "caveat": "gemini-embedding-001 + BM25 hybrid → Cohere rerank",
        },
        {
            "metric": "특약 RAG Source+Section Precision (운영 검색)",
            "score": _nested(
                retrieval_provider, "special_clauses", "section_macro_context_precision"
            ),
            "sample": "6 cases",
            "evaluation_type": "provider",
            "tier": "provider",
            "caveat": "BM25 단독(66.67%) 대비 개선된 값",
        },
        {
            "metric": "필드 추출 정확도 (정규식 폴백)",
            "score": _nested(offline, "extraction", "accuracy"),
            "sample": f'{offline["extraction"]["field_count"]} fields',
            "evaluation_type": "offline",
            "tier": "regression",
            "caveat": "합성 템플릿 문서를 정규식으로 되읽은 값. 14필드는 정답이 null",
        },
        {
            "metric": "R01–R10 규칙 상태 정확도 (정규식 입력)",
            "score": _nested(offline, "rules", "status", "accuracy"),
            "sample": "100 items / 10 cases",
            "evaluation_type": "offline",
            "tier": "regression",
            "caveat": "추출이 완벽하다는 가정 위의 값. R11–R24는 goldset 없음",
        },
        {
            "metric": "J01–J13 판정 상태 정확도",
            "score": _nested(offline, "judgments", "status", "accuracy"),
            "sample": "51 items / 13 judgments",
            "evaluation_type": "offline",
            "tier": "regression",
            "caveat": "사용자 확인 완료 입력 기준이라 추출 오류가 전파되지 않음. 판정당 3~5건",
        },
        {
            "metric": "End-to-End 무오류 실행",
            "score": _nested(offline, "end_to_end", "completion_rate"),
            "sample": f'{offline["end_to_end"]["case_count"]} cases',
            "evaluation_type": "offline",
            "tier": "structural",
            "caveat": "정확도 아님. 케이스 실패 시 평가가 중단되므로 100% 미만이 나올 수 없음",
        },
        {
            "metric": "일반 RAG 정답 출처 Recall",
            "score": _nested(
                ragas_offline, "general_rag_sources", "macro_context_recall"
            ),
            "sample": "27 queries · 6 sources",
            "evaluation_type": "offline_ragas",
            "tier": "structural",
            "caveat": "허용 출처 화이트리스트(=정답 출처) 안에서만 검색되므로 precision은 항상 1.0",
        },
        {
            "metric": "특약 RAG Source Precision",
            "score": _nested(
                ragas_offline, "special_clause_sources", "macro_context_precision"
            ),
            "sample": "6 cases",
            "evaluation_type": "offline_ragas",
            "tier": "regression",
            "caveat": "BM25 단독 기준선. 운영 검색 값은 위 그룹 참조",
        },
        {
            "metric": "특약 RAG Source+Section Precision",
            "score": _nested(
                ragas_offline, "special_clause_sections", "macro_context_precision"
            ),
            "sample": "6 cases",
            "evaluation_type": "offline_ragas",
            "tier": "regression",
            "caveat": "BM25 단독 기준선. 운영 검색은 77.78%",
        },
        {
            "metric": "Faithfulness",
            "score": _nested(
                ragas_online, "metrics", "faithfulness", "macro_average"
            ),
            "sample": f'{ragas_online["evaluated_case_count"]} cases',
            "evaluation_type": "online_ragas",
            "tier": "quality",
            "caveat": "손으로 쓴 고정 QA 3건에 대한 judge 점수. 파이프라인 생성 결과 아님",
        },
        {
            "metric": "Answer Relevancy",
            "score": _nested(
                ragas_online, "metrics", "answer_relevancy", "macro_average"
            ),
            "sample": f'{ragas_online["evaluated_case_count"]} cases',
            "evaluation_type": "online_ragas",
            "tier": "quality",
            "caveat": "손으로 쓴 고정 QA 3건에 대한 judge 점수. 파이프라인 생성 결과 아님",
        },
    ]
    _write_csv(args.output_dir / "02-evaluation-summary.csv", evaluation_rows)
    _evaluation_svg(
        evaluation_rows, args.output_dir / "02-evaluation-summary.svg"
    )

    cycle_rows = _cycle_rows(actual, simulation)
    _write_csv(args.output_dir / "03-mode-cycle-summary.csv", cycle_rows)
    _cycle_svg(
        cycle_rows, actual, args.output_dir / "03-mode-cycle-cost.svg"
    )
    print(f"PPT metrics assets: {args.output_dir}")


if __name__ == "__main__":
    main()
