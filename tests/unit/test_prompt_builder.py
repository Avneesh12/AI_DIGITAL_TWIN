"""tests/unit/test_prompt_builder.py — Verify prompt structure with mock data."""
import pytest

from app.services.prompt_builder import PromptBuilder


@pytest.fixture
def builder():
    return PromptBuilder()


class TestPromptBuilder:

    def test_build_system_prompt_contains_username(self, builder, sample_user, sample_personality, sample_memories):
        prompt = builder.build_system_prompt(
            username=sample_user.username,
            profile=sample_personality,
            memories=sample_memories,
        )
        assert "testuser" in prompt

    def test_identity_block_contains_all_traits(self, builder, sample_user, sample_personality, sample_memories):
        prompt = builder.build_system_prompt(
            username=sample_user.username,
            profile=sample_personality,
            memories=sample_memories,
        )
        assert "casual" in prompt               # tone
        assert "concise and direct" in prompt   # communication_style
        assert "honesty" in prompt              # values
        assert "analytical" in prompt           # decision_style
        assert "0.80" in prompt                 # openness
        assert "pragmatic technologist" in prompt  # persona_summary

    def test_memory_block_shows_memories(self, builder, sample_user, sample_personality, sample_memories):
        prompt = builder.build_system_prompt(
            username=sample_user.username,
            profile=sample_personality,
            memories=sample_memories,
        )
        assert "job offer at the startup" in prompt
        assert "0.91" in prompt   # relevance score
        assert "career" in prompt  # topic tags

    def test_empty_memories_shows_no_memories_message(self, builder, sample_user, sample_personality):
        prompt = builder.build_system_prompt(
            username=sample_user.username,
            profile=sample_personality,
            memories=[],
        )
        assert "No relevant past memories" in prompt

    def test_rules_block_contains_first_person_instruction(self, builder, sample_user, sample_personality, sample_memories):
        prompt = builder.build_system_prompt(
            username=sample_user.username,
            profile=sample_personality,
            memories=sample_memories,
        )
        assert "first person" in prompt
        assert "Never break character" in prompt

    def test_build_messages_returns_correct_structure(self, builder, sample_user, sample_personality, sample_memories):
        messages = builder.build_messages(
            username=sample_user.username,
            profile=sample_personality,
            memories=sample_memories,
            user_message="What should I do about my career?",
        )
        assert len(messages) == 2
        assert messages[0]["role"] == "system"
        assert messages[1]["role"] == "user"
        assert messages[1]["content"] == "What should I do about my career?"

    def test_recent_turns_included_when_provided(self, builder, sample_user, sample_personality, sample_memories):
        recent_turns = [
            {"role": "user", "content": "Hello, how are you?"},
            {"role": "assistant", "content": "Doing great, thanks."},
        ]
        prompt = builder.build_system_prompt(
            username=sample_user.username,
            profile=sample_personality,
            memories=sample_memories,
            recent_turns=recent_turns,
        )
        assert "Hello, how are you?" in prompt

    def test_importance_scoring_prompt_contains_required_json_keys(self):
        prompt = PromptBuilder.importance_scoring_prompt(
            user_message="test message",
            assistant_response="test response",
        )
        assert "importance_score" in prompt
        assert "topic_tags" in prompt
        assert "emotional_tone" in prompt
        assert "JSON" in prompt

    def test_personality_extraction_prompt_contains_big_five(self):
        prompt = PromptBuilder.personality_extraction_prompt("some chat transcript")
        for trait in ["openness", "conscientiousness", "extraversion", "agreeableness", "neuroticism"]:
            assert trait in prompt
