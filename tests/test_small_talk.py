import pytest

from ragchatbot.chat.small_talk import is_small_talk


@pytest.mark.parametrize(
    "message",
    [
        "hi",
        "Hi!",
        "hello",
        "hey",
        "good morning",
        "Good Morning!",
        "good afternoon.",
        "how are you",
        "How are you?",
        "how's it going",
        "what's up",
        "thanks",
        "thank you!",
        "bye",
        "goodbye",
        "good night",
        "who are you",
        "what can you do",
        "help",
        "  hello  ",
    ],
)
def test_recognizes_small_talk(message: str):
    assert is_small_talk(message) is True


@pytest.mark.parametrize(
    "message",
    [
        "What is the price of the Widget?",
        "hi, what's the price of the Widget?",
        "give a short summary on ESG Factsheet",
        "who is the owner of this asset?",
        "hello there, can you tell me about the products table",
        "",
        "   ",
    ],
)
def test_does_not_flag_data_questions_as_small_talk(message: str):
    assert is_small_talk(message) is False
