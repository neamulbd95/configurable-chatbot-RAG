from ragchatbot.db.session_store import apply_history_budget


def test_keeps_all_messages_within_budget():
    rows = [
        {"role": "assistant", "content": "b"},  # most recent
        {"role": "user", "content": "a"},
    ]

    result = apply_history_budget(rows, max_chars=100)

    assert result == [{"role": "user", "content": "a"}, {"role": "assistant", "content": "b"}]


def test_truncates_older_messages_beyond_char_budget():
    rows = [
        {"role": "assistant", "content": "recent" * 5},  # most recent, 30 chars
        {"role": "user", "content": "older" * 20},  # 100 chars, should be dropped
    ]

    result = apply_history_budget(rows, max_chars=50)

    assert result == [{"role": "assistant", "content": "recent" * 5}]


def test_always_keeps_at_least_the_most_recent_message():
    rows = [{"role": "user", "content": "x" * 1000}]

    result = apply_history_budget(rows, max_chars=10)

    assert result == [{"role": "user", "content": "x" * 1000}]


def test_empty_history_returns_empty():
    assert apply_history_budget([], max_chars=100) == []
