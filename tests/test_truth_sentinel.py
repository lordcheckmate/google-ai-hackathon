import pytest
from backend.truth_sentinel import TruthSentinel


def test_timeline_contradiction():
    sentinel = TruthSentinel()
    
    # Speaker 1 says Q3
    alert1 = sentinel.ingest_statement("Alice", "Our target release date is strictly in Q3.")
    assert alert1 is None, "First statement should not trigger contradiction"
    
    # Speaker 2 contradicts with Q2
    alert2 = sentinel.ingest_statement("Bob", "Since we agreed to ship this in Q2, we need to hurry.")
    assert alert2 is not None, "Contradiction should be detected"
    assert "Q2" in alert2.options or "Q2" in alert2.clarification_question
    assert "Q3" in alert2.options or "Q3" in alert2.clarification_question
    assert "Which one do you mean" in alert2.clarification_question
    assert "Discrepancy detected" in alert2.auto_chat_message


def test_budget_contradiction():
    sentinel = TruthSentinel()
    
    sentinel.ingest_statement("Finance", "The approved budget for this quarter is $50k.")
    alert = sentinel.ingest_statement("Lead", "Since we only have $30k available for cloud costs...")
    
    assert alert is not None
    assert "$50k" in alert.options or "$50k" in alert.clarification_question
    assert "$30k" in alert.options or "$30k" in alert.clarification_question
    assert "Which one do you mean" in alert.clarification_question


def test_architecture_contradiction():
    sentinel = TruthSentinel()
    
    sentinel.ingest_statement("Architect", "We are choosing Postgres for all relational storage.")
    alert = sentinel.ingest_statement("Dev", "I am configuring our MySQL database replication.")
    
    assert alert is not None
    assert alert.category == "architecture"
    assert "Postgres" in alert.options
    assert "Mysql" in alert.options or "MySQL" in alert.options


def test_multilingual_timeline_contradiction():
    sentinel = TruthSentinel()
    
    # Japanese Q3
    sentinel.ingest_statement("Tanaka", "新機能のリリースは第3四半期を予定しています。", language="ja")
    # Japanese Q2 contradiction
    alert = sentinel.ingest_statement("Suzuki", "第2四半期のローンチに向けて準備を進めましょう。", language="ja")
    
    assert alert is not None
    assert "第3四半期" in alert.options or "Q3" in alert.options or "第3四半期" in alert.clarification_question


def test_non_conflicting_statements():
    sentinel = TruthSentinel()
    
    a1 = sentinel.ingest_statement("Alice", "Hello everyone, welcome to the weekly standup.")
    a2 = sentinel.ingest_statement("Bob", "The weather is really nice today.")
    a3 = sentinel.ingest_statement("Charlie", "I finished the documentation yesterday.")
    
    assert a1 is None
    assert a2 is None
    assert a3 is None
    assert len(sentinel.contradictions) == 0
