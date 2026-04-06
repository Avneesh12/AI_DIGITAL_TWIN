"""
locustfile.py — Load testing for AI Digital Twin API.

Usage:
    locust -f locustfile.py --host=http://localhost:8000
    # Then open http://localhost:8089 and set users=100, spawn_rate=10

Target: p95 latency ≤ 3s under 100 concurrent users on /chat
"""
import json
import random
import uuid

from locust import HttpUser, between, task


TEST_MESSAGES = [
    "What should I focus on this week?",
    "How would I approach a difficult conversation with my manager?",
    "What are my thoughts on remote work vs office?",
    "How do I usually handle stress?",
    "What's my typical approach to learning something new?",
    "How would I decide between two job offers?",
    "What do I prioritize in my relationships?",
    "How do I deal with procrastination?",
]


class DigitalTwinUser(HttpUser):
    wait_time = between(1, 3)  # Simulate realistic inter-request delay
    token: str = ""
    session_id: str = ""

    def on_start(self):
        """Register + login to get auth token before running tasks."""
        username = f"loadtest_{uuid.uuid4().hex[:8]}"
        email = f"{username}@loadtest.example.com"

        # Register
        resp = self.client.post("/api/v1/auth/register", json={
            "email": email,
            "username": username,
            "password": "loadtest_password_123",
        })
        if resp.status_code == 201:
            self.token = resp.json()["access_token"]
            self.session_id = str(uuid.uuid4())

            # Create a basic personality profile
            self.client.post(
                "/api/v1/personality",
                json={
                    "tone": "casual",
                    "communication_style": "direct",
                    "values": ["efficiency", "clarity"],
                    "interests": ["technology"],
                    "decision_style": "analytical",
                    "persona_summary": "A pragmatic problem-solver.",
                },
                headers=self._auth_headers(),
            )

    def _auth_headers(self) -> dict:
        return {"Authorization": f"Bearer {self.token}"}

    @task(10)
    def send_chat_message(self):
        if not self.token:
            return
        message = random.choice(TEST_MESSAGES)
        with self.client.post(
            "/api/v1/chat",
            json={"message": message, "session_id": self.session_id},
            headers=self._auth_headers(),
            catch_response=True,
            name="/api/v1/chat",
        ) as resp:
            if resp.status_code == 200:
                resp.success()
            else:
                resp.failure(f"Status {resp.status_code}: {resp.text[:200]}")

    @task(2)
    def get_personality(self):
        if not self.token:
            return
        self.client.get(
            "/api/v1/personality",
            headers=self._auth_headers(),
            name="/api/v1/personality GET",
        )

    @task(1)
    def list_memories(self):
        if not self.token:
            return
        self.client.get(
            "/api/v1/memory",
            headers=self._auth_headers(),
            name="/api/v1/memory GET",
        )

    @task(1)
    def get_chat_history(self):
        if not self.token:
            return
        self.client.get(
            "/api/v1/chat/history",
            headers=self._auth_headers(),
            name="/api/v1/chat/history GET",
        )
