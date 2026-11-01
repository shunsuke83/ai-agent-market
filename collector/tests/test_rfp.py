import io
import json
import struct
import zipfile
from datetime import datetime

from g2b import rfp
from g2b.render import KST


def _hwpx(paragraphs):
    xml = "".join(f"<hp:p><hp:run><hp:t>{p}</hp:t></hp:run></hp:p>" for p in paragraphs)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("mimetype", "application/hwp+zip")
        z.writestr("Contents/section0.xml", f'<hs:sec xmlns:hp="x" xmlns:hs="y">{xml}</hs:sec>')
    return buf.getvalue()


def _record(tag, payload):
    return struct.pack("<I", tag | (len(payload) << 20)) + payload


def test_hwpx_text():
    text = rfp.extract_text(_hwpx(["제안요청서", "사업기간 : 계약일로부터 8개월", "A &amp; B"]))
    assert text.splitlines() == ["제안요청서", "사업기간 : 계약일로부터 8개월", "A & B"]


def test_hwp_records_skip_inline_controls():
    inline = struct.pack("<8H", 11, 0, 0, 0, 0, 0, 0, 11)
    para = inline + "과업 범위".encode("utf-16-le") + struct.pack("<H", 13)
    stream = _record(66, b"\x00" * 6) + _record(rfp.HWPTAG_PARA_TEXT, para)
    assert rfp.hwp_records_text(stream).strip() == "과업 범위"


def test_unsupported_bytes_give_empty_text():
    assert rfp.extract_text(b"\x89PNG....") == ""
    assert rfp.extract_text(b"PK\x03\x04broken") == ""


def test_extract_fields():
    text = (
        "수행기간은 아래와 같다\n사업기간 : 계약일로부터 8개월\n"
        "본 사업은 중소기업자간 경쟁제품 대상\n대기업인 소프트웨어사업자의 참여를 제한\n"
        "하도급은 불가하다\n제안서 발표 일정은 별도 통보"
    )
    f = rfp.extract_fields(text)
    assert f == {
        "period": "계약일로부터 8개월",
        "sme_only": True,
        "big_firm_limit": True,
        "subcontract_limit": True,
        "presentation": True,
    }
    assert "period" not in rfp.extract_fields("사업기간 을 제시한 경우")


def test_document_files_prefers_notice_then_prespec():
    n = {"notice_files": [{"name": "공고서.hwp", "url": "u1"}]}
    assert rfp.document_files(n, [{"spec_files": ["p1"]}]) == ("notice", n["notice_files"])
    assert rfp.document_files({}, [{"spec_files": ["p1"]}]) == ("prespec", [{"name": "규격서 1", "url": "p1"}])
    assert rfp.document_files({}, []) == ("", [])


def test_pending_and_retry_rules():
    now = datetime(2026, 11, 1, 12, 0, tzinfo=KST)
    notices = [
        {"bid_no": "A", "bid_ord": "000", "close_at": "2026-11-10 10:00", "notice_date": "2026-10-30",
         "notice_files": [{"name": "x", "url": "a0"}]},
        {"bid_no": "A", "bid_ord": "001", "close_at": "2026-11-10 10:00", "notice_date": "2026-10-31",
         "notice_files": [{"name": "x", "url": "a1"}]},
        {"bid_no": "B", "close_at": "2026-10-31 10:00", "notice_files": [{"name": "x", "url": "b"}]},
        {"bid_no": "C", "close_at": "2026-11-10 10:00", "notice_date": "2026-10-29"},
    ]
    todo = rfp.pending(notices, {"C": [{"spec_files": ["c"]}]}, {}, now, True)
    assert [(n["bid_no"], src, [f["url"] for f in files]) for n, src, files in todo] == [
        ("A", "notice", ["a1"]),
        ("C", "prespec", ["c"]),
    ]
    assert not rfp.needs_work({"source_urls": ["a1"], "status": "ok"}, ["a1"], True)
    assert rfp.needs_work({"source_urls": ["a0"], "status": "ok"}, ["a1"], True)
    assert rfp.needs_work({"source_urls": ["a1"], "status": "error", "attempts": 2}, ["a1"], True)
    assert not rfp.needs_work({"source_urls": ["a1"], "status": "error", "attempts": 3}, ["a1"], True)
    assert rfp.needs_work({"source_urls": ["a1"], "status": "fields_only"}, ["a1"], True)
    assert not rfp.needs_work({"source_urls": ["a1"], "status": "fields_only"}, ["a1"], False)


class _Resp:
    def __init__(self, status, payload=None, content=b"", headers=None):
        self.status_code = status
        self._payload = payload
        self.content = content
        self.headers = headers or {}

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            import requests

            raise requests.HTTPError(str(self.status_code))


class _Session:
    def __init__(self, files, gemini):
        self.files, self.gemini, self.posts = files, list(gemini), []

    def get(self, url, timeout=None):
        return self.files[url]

    def post(self, url, json=None, timeout=None, headers=None):
        self.posts.append((url, json, headers))
        return self.gemini.pop(0)


def _gemini_ok(summary):
    return _Resp(200, {"candidates": [{"content": {"parts": [{"text": json.dumps(summary, ensure_ascii=False)}]}}]})


def test_gemini_falls_back_on_missing_model_and_clips():
    summary = {"overview": "개요", "tasks": [f"t{i}" for i in range(9)], "tech": ["LLM"],
               "requirements": [], "evaluation": "기술 90", "cautions": ["", "보안"]}
    s = _Session({}, [_Resp(404), _gemini_ok(summary)])
    out, model = rfp.gemini_summary("사업", "기관", "본문", "KEY", session=s, models=("m1", "m2"))
    assert model == "m2"
    assert out["tasks"] == [f"t{i}" for i in range(6)] and out["cautions"] == ["보안"]
    assert s.posts[1][2] == {"x-goog-api-key": "KEY"}
    assert "KEY" not in s.posts[1][0]


def test_run_summaries_writes_cache(tmp_path, monkeypatch):
    (tmp_path / "data").mkdir()
    notice = {"bid_no": "R26BK1", "bid_ord": "000", "title": "AI 챗봇 구축", "org": "기관",
              "close_at": "2026-11-20 10:00", "notice_date": "2026-11-01",
              "notice_files": [{"name": "제안요청서.hwpx", "url": "u1"}, {"name": "입찰참가 서약서.hwp", "url": "u2"}]}
    (tmp_path / "data" / "notices.json").write_text(json.dumps({"notices": [notice]}), encoding="utf-8")
    doc = _hwpx(["사업기간 : 계약일로부터 6개월"] + ["챗봇 과업 설명 문장입니다."] * 40)
    summary = {"overview": "챗봇 구축", "tasks": ["챗봇"], "tech": ["LLM"], "requirements": [],
               "evaluation": "", "cautions": []}
    s = _Session({"u1": _Resp(200, content=doc)}, [_gemini_ok(summary)])
    monkeypatch.delenv("GEMINI_MODEL", raising=False)
    now = datetime(2026, 11, 1, 12, 0, tzinfo=KST)
    counts = rfp.run_summaries(tmp_path, now=now, api_key="KEY", session=s, gap_sec=0)
    assert counts["ok"] == 1 and counts["stored"] == 1
    entry = rfp.load_summaries(tmp_path)["R26BK1"]
    assert entry["status"] == "ok" and entry["fields"]["period"] == "계약일로부터 6개월"
    assert entry["files"] == [{"name": "제안요청서.hwpx", "url": "u1"}]
    html = rfp.summary_block(entry)
    assert "제안요청서 요약" in html and "챗봇 구축" in html and "Gemini" in html
    again = rfp.run_summaries(tmp_path, now=now, api_key="KEY", session=s, gap_sec=0)
    assert again["pending"] == 0


def test_summary_block_hidden_without_content():
    assert rfp.summary_block(None) == ""
    assert rfp.summary_block({"status": "no_text"}) == ""
    assert rfp.summary_block({"status": "fields_only", "fields": {}}) == ""
    fields_only = rfp.summary_block({"status": "fields_only", "fields": {"sme_only": True}, "files": []})
    assert "중소기업 제한 언급" in fields_only and "규칙으로 추출" in fields_only
