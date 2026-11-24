"""'Tell me everything' questions (in any of the 3 languages) get ALL memories, so the first answer is complete."""
import pytest

from app.routers.chat import BROAD


@pytest.mark.parametrize("text", [
    "mere reminders and mere baare mein batao?", "or kuch bhi nhi hai?", "aur kya yaad hai", "kya kya yaad hai",
    "Tell me about me", "what do you know about me", "show me everything", "anything else?",
    "मेरे बारे में बताओ", "सब कुछ बताओ",
])
def test_everything_questions(text):
    assert BROAD.search(text)


@pytest.mark.parametrize("text", [
    "Where does my son live?", "Rajesh ka number kya hai?", "Remind me at 9 pm", "मेरा बेटा कहाँ रहता है?", "hello",
])
def test_normal_questions_stay_focused(text):
    assert not BROAD.search(text)
