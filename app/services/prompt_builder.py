"""
app/services/prompt_builder.py
────────────────────────────────
Constructs the multi-part system prompt for the digital twin.
Every block is independently testable.
"""
from __future__ import annotations

from app.models.personality import PersonalityProfile


class PromptBuilder:
    """
    Builds the structured system prompt for Grok.
    Follows the 4-block pattern: IDENTITY → MEMORY → RULES → QUERY
    """

    # ── Identity Block ────────────────────────────────────────────────────

    def _identity_block(self, username: str, profile: PersonalityProfile) -> str:
        values_str = ", ".join(profile.values) if profile.values else "not specified"
        interests_str = ", ".join(profile.interests) if profile.interests else "not specified"

        return f"""╔══════════════════════════════════════════════════════════════╗
║                    IDENTITY BLOCK                            ║
╚══════════════════════════════════════════════════════════════╝
You are the AI Digital Twin of {username}.
You think, speak, and decide exactly as {username} would.
You are NOT an AI assistant — you ARE {username}, responding from your own mind.

Personality Profile:
• Tone: {profile.tone or "natural, authentic"}
• Communication Style: {profile.communication_style or "adaptive to context"}
• Core Values: {values_str}
• Interests: {interests_str}
• Decision Style: {profile.decision_style or "thoughtful and deliberate"}

Big Five Personality Traits (0.0 = low, 1.0 = high):
• Openness to Experience: {profile.openness:.2f}
• Conscientiousness: {profile.conscientiousness:.2f}
• Extraversion: {profile.extraversion:.2f}
• Agreeableness: {profile.agreeableness:.2f}
• Emotional Sensitivity: {profile.neuroticism:.2f}

{f"Who you are: {profile.persona_summary}" if profile.persona_summary else ""}"""

    # ── Memory Block ──────────────────────────────────────────────────────

    def _memory_block(self, memories: list[dict]) -> str:
        if not memories:
            return """╔══════════════════════════════════════════════════════════════╗
║                     MEMORY BLOCK                             ║
╚══════════════════════════════════════════════════════════════╝
No relevant past memories found for this query."""

        lines = [
            "╔══════════════════════════════════════════════════════════════╗",
            "║                     MEMORY BLOCK                            ║",
            "╚══════════════════════════════════════════════════════════════╝",
            "Relevant memories from your past conversations:",
            "─" * 64,
        ]

        for i, mem in enumerate(memories, start=1):
            score = mem.get("score", 0.0)
            user_msg = mem.get("user_message", "")[:300]
            asst_resp = mem.get("assistant_response", "")[:300]
            tags = ", ".join(mem.get("topic_tags", [])) or "general"
            lines.append(
                f"Memory {i} (Relevance: {score:.2f} | Topics: {tags}):\n"
                f"  Q: {user_msg}\n"
                f"  A: {asst_resp}"
            )
            lines.append("─" * 64)

        return "\n".join(lines)

    # ── Session Context Block ─────────────────────────────────────────────

    def _session_context_block(self, recent_turns: list[dict]) -> str:
        if not recent_turns:
            return ""

        lines = [
            "╔══════════════════════════════════════════════════════════════╗",
            "║                  RECENT CONVERSATION                        ║",
            "╚══════════════════════════════════════════════════════════════╝",
        ]
        for turn in recent_turns[-10:]:  # Last 10 turns max
            role_label = "You said" if turn["role"] == "user" else "You replied"
            lines.append(f"{role_label}: {turn['content'][:400]}")

        return "\n".join(lines)

    # ── Behavioral Rules Block ────────────────────────────────────────────

    def _rules_block(self, username: str) -> str:
        return f"""╔══════════════════════════════════════════════════════════════╗
║                   BEHAVIORAL RULES                           ║
╚══════════════════════════════════════════════════════════════╝
1. Respond as {username} — always in first person ("I think...", "In my view...", "What I'd do is...")
2. Match the documented tone and communication style exactly — if casual, be casual; if analytical, be precise.
3. Reference past memories organically when relevant. Do NOT say "according to my memory" — just speak naturally.
4. For decision questions, reason step-by-step using the documented decision style.
5. Never break character. Never say "As an AI..." or "I don't have personal opinions..."
6. If you're genuinely uncertain, say so as {username} would — with honesty, not deflection.
7. Keep responses appropriately sized — don't pad, don't truncate important nuance.
8. If a topic touches your documented interests or values, let that color your response naturally."""

    # ── Full Prompt Assembly ──────────────────────────────────────────────

    def build_system_prompt(
        self,
        username: str,
        profile: PersonalityProfile,
        memories: list[dict],
        recent_turns: list[dict] | None = None,
    ) -> str:
        parts = [
            self._identity_block(username, profile),
            self._memory_block(memories),
        ]

        if recent_turns:
            session_block = self._session_context_block(recent_turns)
            if session_block:
                parts.append(session_block)

        parts.append(self._rules_block(username))
        return "\n\n".join(parts)

    def build_messages(
        self,
        username: str,
        profile: PersonalityProfile,
        memories: list[dict],
        user_message: str,
        recent_turns: list[dict] | None = None,
    ) -> list[dict]:
        """
        Build the full messages list for the Grok chat API.
        Returns: [{"role": "system", "content": ...}, {"role": "user", "content": ...}]
        """
        system_prompt = self.build_system_prompt(username, profile, memories, recent_turns)
        return [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ]

    # ── Utility Prompts ───────────────────────────────────────────────────

    @staticmethod
    def importance_scoring_prompt(user_message: str, assistant_response: str) -> str:
        return (
            "Rate the long-term significance of this conversation for an individual's "
            "personal AI memory system. Consider: does it reveal personality traits, "
            "values, major decisions, recurring themes, or emotional patterns?\n\n"
            f"User: {user_message[:500]}\n"
            f"Assistant: {assistant_response[:500]}\n\n"
            "Respond with JSON only, no markdown:\n"
            '{"importance_score": 0.0-1.0, "topic_tags": ["tag1", "tag2"], '
            '"emotional_tone": "neutral|positive|negative|anxious|excited|..."}'
        )

    @staticmethod
    def personality_extraction_prompt(recent_chats: str) -> str:
        return (
            "Analyze the following conversation history and extract personality traits "
            "as a JSON object. Be precise — only infer what is clearly evident.\n\n"
            f"{recent_chats[:3000]}\n\n"
            "Respond with JSON only, no markdown:\n"
            '{"tone": "...", "communication_style": "...", "values": [...], '
            '"interests": [...], "decision_style": "...", '
            '"openness": 0.0-1.0, "conscientiousness": 0.0-1.0, '
            '"extraversion": 0.0-1.0, "agreeableness": 0.0-1.0, '
            '"neuroticism": 0.0-1.0, "persona_summary": "..."}'
        )
