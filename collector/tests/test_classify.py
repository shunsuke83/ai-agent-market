import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from g2b.classify import (
    classify_fields,
    classify_nature,
    classify_scope,
    classify_title,
    load_keywords,
)
from g2b.seed import load_seed

ROOT = Path(__file__).resolve().parents[2]


def test_scope_generative():
    assert classify_scope("생성형 AI 플랫폼 구축") == "생성형·Agent"
    assert classify_scope("RAG 기반 챗봇 고도화") == "생성형·Agent"


def test_scope_ai_counsel_and_platform():
    # deliverables: AI 상담·챗봇·플랫폼 → 생성형·Agent
    assert classify_scope("지방세 AI 상담 서비스") == "생성형·Agent"
    assert classify_scope("전기안전 AI플랫폼 구축 용역") == "생성형·Agent"
    assert classify_scope("한국투자공사 내부 인공지능 플랫폼 고도화") == "생성형·Agent"
    assert classify_scope("에이전틱 AI 기반의 전국민 맞춤형 민원상담") == "생성형·Agent"


def test_scope_ai_sw():
    assert classify_scope("인공지능 영상 분석 시스템 구축") == "AI SW 확대"
    assert classify_scope("OCR 기반 문서 자동화") == "AI SW 확대"


def test_scope_intelligent_as_ai_sw():
    # band.html labels 지능형-* as AI SW 확대
    assert classify_scope("2026년 지능형 통합시스템 고도화 용역") == "AI SW 확대"
    assert classify_scope("영상정보 지능형 선별관제시스템 구축 사업") == "AI SW 확대"
    assert classify_scope("NPU기반 지능형 영상감시체계 시범 구축") == "AI SW 확대"
    assert classify_scope("국내외 비즈매칭 에이전트 서비스 위탁용역") == "AI SW 확대"


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
    assert classify_nature("해양데이터 분석 기술 개발 사업 기획연구") == "ISP·전략"


def test_nature_ops_and_infra():
    assert classify_nature("AI 시스템 운영 및 유지관리 용역") == "운영·유지보수"
    assert classify_nature("거대 생성형 모델 학습용 GPU Server 구매") == "인프라"


def test_classify_title_bundle():
    r = classify_title("JDC 사내 생성형 AI 언어모델(SLLM) 구축 사업")
    assert r["scope"] == "생성형·Agent"
    assert "생성형·LLM" in r["fields"]


def test_search_keywords_configured():
    rules = load_keywords()
    kws = rules.get("search_keywords") or []
    assert "지능형" in kws
    assert "AI" in kws


def test_bootstrap_scope_accuracy_floor():
    """Tuned keywords should stay ≥90% vs editorial band.html labels."""
    boot = load_seed(ROOT)
    rules = load_keywords()
    agree = disagree = 0
    for n in boot.get("band_notices") or []:
        gold = n.get("scope")
        if not gold:
            continue
        pred = classify_scope(n.get("title") or "", rules)
        if pred == gold:
            agree += 1
        else:
            disagree += 1
    total = agree + disagree
    assert total >= 400
    acc = agree / total
    assert acc >= 0.90, f"scope accuracy {acc:.1%} below 90% floor ({agree}/{total})"
