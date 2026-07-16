"""자유이용이 확인된 국가법령정보센터 법령 본문을 정규화해 수집한다."""

from __future__ import annotations

import argparse
import re
import urllib.request
from html.parser import HTMLParser
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "data" / "rag" / "sources"
USER_AGENT = "lease-companion-rag-source-collector/1.0"

LAW_SOURCES = {
    "SRC-HTA-LAW": {
        "title": "주택임대차보호법",
        "url": "https://www.law.go.kr/LSW/lsInfoR.do?lsiSeq=276291&efYd=20260102",
        "output": "SRC-HTA-LAW.txt",
    },
    "SRC-HTA-DECREE": {
        "title": "주택임대차보호법 시행령",
        "url": "https://law.go.kr/LSW/lsInfoR.do?lsiSeq=287183&efYd=20260701",
        "output": "SRC-HTA-DECREE.txt",
    },
}


class LawBodyParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._lawcon_depth = 0
        self._paragraph: list[str] | None = None
        self.paragraphs: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        if tag == "div":
            classes = (attributes.get("class") or "").split()
            if self._lawcon_depth:
                self._lawcon_depth += 1
            elif "lawcon" in classes:
                self._lawcon_depth = 1
        elif tag == "p" and self._lawcon_depth:
            self._paragraph = []

    def handle_endtag(self, tag: str) -> None:
        if tag == "p" and self._paragraph is not None:
            text = re.sub(r"\s+", " ", "".join(self._paragraph)).strip()
            if text:
                self.paragraphs.append(text)
            self._paragraph = None
        elif tag == "div" and self._lawcon_depth:
            self._lawcon_depth -= 1

    def handle_data(self, data: str) -> None:
        if self._paragraph is not None:
            self._paragraph.append(data)


def fetch_normalized_law(url: str, *, timeout: float = 60.0) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        html = response.read().decode("utf-8")
    parser = LawBodyParser()
    parser.feed(html)
    if not parser.paragraphs or not any(text.startswith("제1조") for text in parser.paragraphs):
        raise RuntimeError("공식 법령 본문 구조를 확인할 수 없습니다.")
    return "\n".join(parser.paragraphs) + "\n"


def collect(output_dir: Path = OUTPUT_DIR) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    outputs: list[Path] = []
    for source_id, recipe in LAW_SOURCES.items():
        body = fetch_normalized_law(recipe["url"])
        content = (
            f"자료명: {recipe['title']}\n"
            f"source_id: {source_id}\n"
            f"공식 본문 URL: {recipe['url']}\n\n"
            f"{body}"
        )
        output = output_dir / recipe["output"]
        output.write_text(content, encoding="utf-8", newline="\n")
        outputs.append(output)
    return outputs


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR)
    args = parser.parse_args()
    outputs = collect(args.output_dir)
    for output in outputs:
        print(f"wrote {output.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
