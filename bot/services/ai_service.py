"""
AI Service — handles OpenAI API calls for the chat assistant.
Supports bilingual UZ/RU responses based on user preference.
"""

from openai import AsyncOpenAI
from pathlib import Path
from bot.config import config


class AIService:
    def __init__(self):
        self.client = AsyncOpenAI(api_key=config.OPENAI_API_KEY)
        self._system_prompt_template = self._load_prompt()

    def _load_prompt(self) -> str:
        prompt_path = Path(__file__).parent.parent / "prompts" / "system_prompt.txt"
        return prompt_path.read_text(encoding="utf-8")

    def _get_system_prompt(self, lang: str = "uz", user_info: str = "") -> str:
        """Build system prompt with language, agency name, and user context."""
        return self._system_prompt_template.format(
            agency_name=config.AGENCY_NAME,
            lang=lang,
            user_info=user_info or "No info collected yet.",
        )

    async def get_response(
        self,
        conversation_history: list[dict],
        user_message: str,
        lang: str = "uz",
        user_info: str = "",
    ) -> str:
        """
        Get AI response for a user message.

        Args:
            conversation_history: List of {"role": "user"|"assistant", "message": "..."}
            user_message: The current message from the user
            lang: User's preferred language ("uz" or "ru")

        Returns:
            AI response text
        """
        messages = [{"role": "system", "content": self._get_system_prompt(lang, user_info)}]
        for msg in conversation_history:
            role = "assistant" if msg["role"] == "assistant" else "user"
            messages.append({"role": role, "content": msg["message"]})
        messages.append({"role": "user", "content": user_message})

        try:
            response = await self.client.chat.completions.create(
                model=config.OPENAI_MODEL,
                messages=messages,
                max_tokens=config.OPENAI_MAX_TOKENS,
            )
            return response.choices[0].message.content

        except Exception as e:
            print(f"AI Service error: {e}")
            if lang == "ru":
                return (
                    "Извините, произошла техническая ошибка. "
                    "Наша команда скоро свяжется с вами. "
                    "Или вы можете позвонить нам напрямую."
                )
            return (
                "Kechirasiz, texnik xatolik yuz berdi. "
                "Jamoamiz tez orada siz bilan bog'lanadi. "
                "Yoki bizga to'g'ridan-to'g'ri qo'ng'iroq qilishingiz mumkin."
            )


# Singleton instance
ai_service = AIService()
