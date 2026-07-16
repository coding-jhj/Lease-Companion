from scripts.collect_verified_law_sources import LawBodyParser


def test_law_body_parser_collects_only_lawcon_paragraphs():
    parser = LawBodyParser()
    parser.feed(
        """
        <p>메뉴 문구</p>
        <div class="lawcon">
          <p><label>제1조(목적)</label> 공식 <a>본문</a></p>
          <p>  ①   공백 정규화  </p>
        </div>
        """
    )

    assert parser.paragraphs == ["제1조(목적) 공식 본문", "① 공백 정규화"]
