import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from g2b.classify import classify_fields, classify_nature, classify_scope, classify_title


def test_scope_generative():
    assert classify_scope("생성형 AI 플랫폼 구축") == "생성형·Agent"
    assert classify_scope("RAG 기반 챗봇 고도화") == "생성형·Agent"


def test_scope_ai_sw():
    assert classify_scope("인공지능 영상 분석 시스템 구축") == "AI SW 확대"
    assert classify_scope("OCR 기반 문서 자동화") == "AI SW 확대"


def test_scope_none():
    assert classify_scope("사무실 청소 용역") is None


def test_fields_multi():
    fields = classify_fields("생성형AI 적용 내부망 보안체계 실증")
    assert "생성형·LLM" in fields
    assert "AI 보안" in fields


def test_fields_default_general():
    assert classify_fields("AI 일반 사업 고도화") == ["AI 일반"]


def test_nature_isp():
    assert classify_nature("생성형 AI 도입을 위한 ISP 수립") == "ISP·전략"


def test_classify_title_bundle():
    r = classify_title("JDC 사내 생성형 AI 언어모델(SLLM) 구축 사업")
    assert r["scope"] == "생성형·Agent"
    assert "생성형·LLM" in r["fields"]
