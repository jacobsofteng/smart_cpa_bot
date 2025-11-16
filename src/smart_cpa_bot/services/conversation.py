"""Conversation orchestration for bot #1."""

from __future__ import annotations
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Iterable, Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import DialogTurn, User
from .balances import BalanceService
from .llm import LLMService
from .offers import OfferPresentation, OfferService
from .rate_limit import RateLimitRule, RateLimiter
from .users import UserService

OFFER_KEYWORDS = ("задани", "оффер", "квест", "балл", "работ", "подбор")
BALANCE_KEYWORDS = ("баланс", "сколько", "начисл", "осталось", "покажи")
PAYOUT_KEYWORDS = ("вывести", "сертификат", "подароч", "ozon", "wb", "вывод")
DECLINE_WORDS = {"пропустить", "нет", "позже", "skip"}
PHONE_RE = re.compile(r"[+]?\d{9,15}")


class ConversationPhase(str, Enum):
    NAME = "name"
    AGE = "age"
    CITY = "city"
    PHONE = "phone"
    DIALOG = "dialog"


@dataclass(slots=True)
class ConversationResponse:
    text: str
    offers: list[OfferPresentation] = field(default_factory=list)
    balance: dict | None = None
    payout_requested: bool = False


class ConversationService:
    def __init__(
        self,
        session: AsyncSession,
        *,
        llm: LLMService,
        rate_limiter: RateLimiter | None = None,
    ) -> None:
        self.session = session
        self.user_service = UserService(session)
        self.offer_service = OfferService(session)
        self.balance_service = BalanceService(session)
        self.llm = llm
        self.rate_limiter = rate_limiter or RateLimiter()
        self._rule = RateLimitRule(window_seconds=10, max_events=5)

    async def handle(self, user: User, message: str) -> ConversationResponse:
        if not self.rate_limiter.check(user.id, self._rule):
            return ConversationResponse(text="Чуть замедлимся, чтобы все сообщения успевали обрабатываться.")

        phase = self._detect_phase(user)
        if phase != ConversationPhase.DIALOG:
            return await self._handle_onboarding(user, phase, message)

        lowered = message.lower().strip()
        if self.llm.violates_policy(lowered):
            return ConversationResponse(text="С такими темами я помочь не смогу, но могу подсказать по заданиям и баллам.")
        if any(word in lowered for word in OFFER_KEYWORDS):
            offers = await self.offer_service.get_personalized_offers(user)
            text = self._format_offers_text(user, offers)
            return ConversationResponse(text=text, offers=offers)
        if any(word in lowered for word in BALANCE_KEYWORDS):
            snapshot = await self.balance_service.snapshot(user.id)
            payload = {
                "available": snapshot.available,
                "pending": snapshot.pending,
                "locked": snapshot.locked,
            }
            text = (
                f"Доступно {snapshot.available} баллов, "
                f"ожидает подтверждения {snapshot.pending}, временно удержано {snapshot.locked}."
            )
            return ConversationResponse(text=text, balance=payload)
        if any(word in lowered for word in PAYOUT_KEYWORDS):
            return ConversationResponse(
                text=(
                    "Для вывода нужно минимум 700 баллов. Выбираем между сертификатами Ozon, WB или Золотое яблоко."
                ),
                payout_requested=True,
            )

        await self._store_turn(user.id, "user", message)
        history = await self._history(user.id)
        llm_messages = [{"role": item.role, "content": item.content} for item in history]
        llm_messages.append({"role": "user", "content": message})
        reply = await self.llm.generate(llm_messages)
        await self._store_turn(user.id, "assistant", reply)
        return ConversationResponse(text=reply)

    def _detect_phase(self, user: User) -> ConversationPhase:
        if not (user.display_name and user.display_name.strip()):
            return ConversationPhase.NAME
        if not user.age:
            return ConversationPhase.AGE
        consents = user.consents or {}
        if not user.city and not consents.get("city_declined"):
            return ConversationPhase.CITY
        if not user.phone and not consents.get("phone_declined"):
            return ConversationPhase.PHONE
        return ConversationPhase.DIALOG

    async def _handle_onboarding(self, user: User, phase: ConversationPhase, message: str) -> ConversationResponse:
        text = message.strip()
        if phase == ConversationPhase.NAME:
            if len(text) < 2:
                return ConversationResponse(text="Как к вам обращаться?")
            await self.user_service.update_profile(user, name=text)
            return ConversationResponse(text="Спасибо! Укажите возраст цифрами, чтобы подобрать подходящие задания.")
        if phase == ConversationPhase.AGE:
            if not text.isdigit():
                return ConversationResponse(text="Возраст нужен целым числом, например 22.")
            age = int(text)
            await self.user_service.update_profile(user, age=age)
            return ConversationResponse(
                text="Отлично. Если хотите, напишите город — так будет больше локальных заданий."
            )
        consents = user.consents or {}
        if phase == ConversationPhase.CITY:
            if text.lower() in DECLINE_WORDS:
                consents.update({"city_declined": True})
                await self.user_service.update_profile(user, consents=consents)
                return ConversationResponse(text="Хорошо, оставим без города. Нужен номер телефона для отправки сертификатов?")
            await self.user_service.update_profile(user, city=text)
            return ConversationResponse(text="Принято! Нужен номер телефона для сертификатов. Можно пропустить.")
        if phase == ConversationPhase.PHONE:
            if text.lower() in DECLINE_WORDS:
                consents.update({"phone_declined": True})
                await self.user_service.update_profile(user, consents=consents)
                return ConversationResponse(text="Спасибо, онбординг завершён. Могу подобрать задания с бонусами.")
            match = PHONE_RE.search(text)
            if not match:
                return ConversationResponse(text="Нужен номер в формате +79990000000. Можно написать 'пропустить'.")
            await self.user_service.update_profile(user, phone=match.group(0))
            return ConversationResponse(text="Супер! Рассказывайте, какие задания интересны — подберу варианты.")
        return ConversationResponse(text="Готов продолжать, чем помочь?")

    async def _store_turn(self, user_id: int, role: str, content: str) -> None:
        turn = DialogTurn(user_id=user_id, role=role, content=content)
        self.session.add(turn)
        await self.session.flush()

    async def _history(self, user_id: int, limit: int = 6) -> Sequence[DialogTurn]:
        stmt = (
            select(DialogTurn)
            .where(DialogTurn.user_id == user_id)
            .order_by(DialogTurn.id.desc())
            .limit(limit)
        )
        rows = list((await self.session.execute(stmt)).scalars())
        rows.reverse()
        return rows

    def _format_offers_text(self, user: User, offers: Iterable[OfferPresentation]) -> str:
        if not offers:
            return "Пока нет релевантных заданий, но я отправлю уведомление как только они появятся."
        balance_hint = "Баланс пополнится сразу после подтверждения CPA."
        lines = ["Подобрала несколько вариантов с бонусами:" ]
        for offer in offers:
            lines.append(f"• {offer.title} ~{offer.payout} баллов")
        lines.append("Полные карточки пришлю во втором боте, можно перейти оттуда.")
        lines.append(balance_hint)
        return "\n".join(lines)


__all__ = [
    "ConversationService",
    "ConversationResponse",
    "ConversationPhase",
]
