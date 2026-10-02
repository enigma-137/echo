from app.providers.base import ModelProvider


class ConversationSummarizer:
    """Creates concise summaries instead of storing raw transcripts."""

    def __init__(self, provider: ModelProvider) -> None:
        self.provider = provider

    async def summarize(self, user_message: str, assistant_response: str) -> str:
        prompt = (
            "Summarize this exchange as durable conversation memory in 1-3 short bullet points. "
            "Keep useful decisions, preferences, plans, and follow-ups. Do not include trivia.\n\n"
            f"User: {user_message}\n\nAssistant: {assistant_response}"
        )
        summary = await self.provider.complete_text(prompt)
        return summary.strip()
