"""추출 정확도 채점기 — ②필드 추출 층 (텍스트 → 구조화 JSON).

"추출이 잘 되는지"를 vibes가 아니라 숫자로 답하는 자(尺).
예측 JSON을 extraction_goldset과 필드별로 대조해 정확도를 낸다.

사용:
    # 실측: API로 뽑은 예측을 넣어 채점
    python data/evaluation/extraction/eval_extraction.py <predictions.jsonl>
    # 자체 검증(인자 없음): 하네스 로직이 맞는지 self-check
    python data/evaluation/extraction/eval_extraction.py

predictions.jsonl 포맷 = goldset와 같은 구조, 줄마다:
    {"case_id": "CASE-001", "extraction": {"contract": {...}, "registry": {...}}}

범위: 필드 추출 층만 채점한다. OCR 텍스트 정확도(CER/WER)는 별도 지표다.
ponytail: exact-match(정규화 후) 채점. 부분점수·의미유사도 필요하면 그때 확장.
"""
import json
import os
import re
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
GOLD = os.path.join(BASE, "..", "..", "sample", "expected-results", "extraction_goldset.jsonl")
SECTIONS = ("contract", "registry")
_MISSING = object()


def read_jsonl(path):
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def norm(v):
    """비교용 정규화: 문자열 공백·쉼표 통일, 리스트 정렬, 나머지 원값."""
    if isinstance(v, str):
        return re.sub(r"\s+", " ", v.replace(",", " ")).strip()
    if isinstance(v, list):
        return sorted(norm(x) for x in v)
    return v  # int·bool·None·float


def extraction_of(record):
    """gold_extraction 또는 extraction 키 양쪽 허용."""
    return record.get("extraction") or record.get("gold_extraction") or {}


def score(predictions, gold):
    """필드별 일치 집계. 반환: overall·per_field·mismatches."""
    gold_by_id = {g["case_id"]: extraction_of(g) for g in gold}
    per_field = {}   # field -> [matched, total]
    mismatches = []
    matched = total = 0

    for pred in predictions:
        cid = pred["case_id"]
        if cid not in gold_by_id:
            raise KeyError(f"goldset에 없는 case_id: {cid}")
        gext, pext = gold_by_id[cid], extraction_of(pred)
        for sec in SECTIONS:
            gsec = gext.get(sec, {})
            psec = pext.get(sec, {})
            for field, gv in gsec.items():
                pv = psec.get(field, _MISSING)
                ok = pv is not _MISSING and norm(gv) == norm(pv)
                slot = per_field.setdefault(field, [0, 0])
                slot[1] += 1
                total += 1
                if ok:
                    slot[0] += 1
                    matched += 1
                else:
                    shown = "(누락)" if pv is _MISSING else pv
                    mismatches.append({"case_id": cid, "field": field, "gold": gv, "pred": shown})

    return {
        "overall": {"matched": matched, "total": total,
                    "accuracy": round(matched / total, 4) if total else 0.0},
        "per_field": {f: {"matched": m, "total": t, "accuracy": round(m / t, 4)}
                      for f, (m, t) in sorted(per_field.items())},
        "mismatches": mismatches,
    }


def report(result):
    o = result["overall"]
    print(f"\n== 추출 정확도 ==  {o['matched']}/{o['total']} = {o['accuracy']:.1%}\n")
    print("필드별:")
    for f, s in result["per_field"].items():
        flag = "" if s["accuracy"] == 1.0 else "  <-- 확인"
        print(f"  {f:<28} {s['matched']}/{s['total']} = {s['accuracy']:.0%}{flag}")
    if result["mismatches"]:
        print(f"\n불일치 {len(result['mismatches'])}건:")
        for m in result["mismatches"]:
            print(f"  [{m['case_id']}] {m['field']}: gold={m['gold']!r}  pred={m['pred']!r}")


def _self_check(gold):
    # 1) gold를 그대로 예측하면 100%
    perfect = [{"case_id": g["case_id"], "extraction": extraction_of(g)} for g in gold]
    r = score(perfect, gold)
    assert r["overall"]["accuracy"] == 1.0, "gold 자기대조가 100%가 아님"
    assert not r["mismatches"]
    # 2) 한 필드 틀리면 정확도 하락 + 그 필드 불일치 포착
    import copy
    bad = copy.deepcopy(perfect)
    bad[0]["extraction"]["contract"]["landlord_name"] = "틀린이름"
    r2 = score(bad, gold)
    assert r2["overall"]["accuracy"] < 1.0
    assert any(m["field"] == "landlord_name" for m in r2["mismatches"])
    # 3) 필드 누락도 불일치로 잡힘
    miss = copy.deepcopy(perfect)
    del miss[0]["extraction"]["registry"]["mortgage_present"]
    r3 = score(miss, gold)
    assert any(m["field"] == "mortgage_present" and m["pred"] == "(누락)" for m in r3["mismatches"])
    print("self-check OK: 정답대조 100%, 오답·누락 포착 확인")


def main():
    gold = read_jsonl(GOLD)
    if len(sys.argv) > 1:
        preds = read_jsonl(sys.argv[1])
        report(score(preds, gold))
    else:
        _self_check(gold)


if __name__ == "__main__":
    main()
