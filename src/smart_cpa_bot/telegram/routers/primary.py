"""Router for the onboarding / LLM bot."""

from __future__ import annotations

import re
from typing import Optional

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from aiogram.filters.callback_data import CallbackData
from sqlalchemy.ext.asyncio import AsyncSession

from ...config import settings
from ...models import Offer
from ...services.clicks import ClickService
from ...services.conversation import ConversationResponse, ConversationService
from ...services.llm import LLMService
from ...services.payouts import PayoutMethod, PayoutService, PayoutValidationError
from ...services.recommendations import RecommendationService
from ...services.users import UserService

router = Router(name="primary")


class PayoutForm(StatesGroup):
    method = State()
    amount = State()
    phone = State()
    email = State()


class PayoutMethodCallback(CallbackData, prefix="payout"):
    method: str


def _method_keyboard() -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text="Ozon", callback_data=PayoutMethodCallback(method="ozon").pack())],
        [InlineKeyboardButton(text="Wildberries", callback_data=PayoutMethodCallback(method="wb").pack())],
        [InlineKeyboardButton(text="Золотое яблоко", callback_data=PayoutMethodCallback(method="golden_apple").pack())],
        [InlineKeyboardButton(text="Прямой перевод", callback_data=PayoutMethodCallback(method="direct").pack())],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def _build_bot2_link(token: str) -> str:
    username = settings.offers_bot.name
    return f"https://t.me/{username}?start={token}"


def _bot2_hint(token: str) -> str:
    return f"Полные карточки ждут во втором боте: {_build_bot2_link(token)}"


async def _get_or_create_user(message: Message, session: AsyncSession) -> tuple[UserService, ConversationService]:
    user_service = UserService(session)
    llm: LLMService = message.bot['llm_service']  # type: ignore[index]
    conversation = ConversationService(session, llm=llm)
    user = await user_service.get_or_create(
        telegram_id=message.from_user.id,
        username=message.from_user.username,
        first_name=message.from_user.first_name,
        last_name=message.from_user.last_name,
    )
    message.conf["current_user"] = user  # type: ignore[attr-defined]
    return user_service, conversation


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext, session: AsyncSession) -> None:
    user_service = UserService(session)
    args = message.text.split(" ", 1)
    ref_code: Optional[str] = None
    if len(args) > 1:
        ref_code = args[1].strip()
    user = await user_service.get_or_create(
        telegram_id=message.from_user.id,
        username=message.from_user.username,
        first_name=message.from_user.first_name,
        last_name=message.from_user.last_name,
    )
    if ref_code:
        await user_service.update_profile(user, referral_code=ref_code)
    await state.clear()
    greeting = (
        "Привет! Я помогу подобрать задания с бонусами. "
        "Для старта давай познакомимся. Как к тебе обращаться?"
    )
    await message.answer(greeting)


@router.message(Command("withdraw"))
async def cmd_withdraw(message: Message, state: FSMContext, session: AsyncSession) -> None:
    await state.set_state(PayoutForm.method)
    await message.answer(
        "Выбирай, какой сертификат нужен. После этого запросим сумму, телефон и почту.",
        reply_markup=_method_keyboard(),
    )


@router.callback_query(PayoutMethodCallback.filter())
async def handle_method(callback: CallbackQuery, callback_data: PayoutMethodCallback, state: FSMContext) -> None:
    await callback.answer()
    await state.update_data(method=callback_data.method)
    await state.set_state(PayoutForm.amount)
    await callback.message.answer("Введи сумму вывода цифрами.")


@router.message(PayoutForm.amount)
async def handle_amount(message: Message, state: FSMContext) -> None:
    if not message.text or not message.text.isdigit():
        await message.answer("Нужна сумма цифрами, например 1000.")
        return
    await state.update_data(amount=int(message.text))
    await state.set_state(PayoutForm.phone)
    await message.answer("Укажи номер телефона для доставки сертификата.")


@router.message(PayoutForm.phone)
async def handle_phone(message: Message, state: FSMContext) -> None:
    if not message.text:
        await message.answer("Введите номер телефона.")
        return
    digits = re.sub(r"\D", "", message.text)
    if len(digits) < 10:
        await message.answer("Номер не похож на телефон. Попробуй ещё раз.")
        return
    await state.update_data(phone="+" + digits)
    await state.set_state(PayoutForm.email)
    await message.answer("Теперь почта для отправки кода.")


@router.message(PayoutForm.email)
async def handle_email(message: Message, state: FSMContext, session: AsyncSession) -> None:
    if not message.text or "@" not in message.text:
        await message.answer("Нужен формата name@example.com")
        return
    data = await state.get_data()
    await state.clear()
    method_value = data.get("method")
    try:
        method = PayoutMethod(method_value)
    except ValueError:
        await message.answer("Выбор метода устарел. Попробуй снова.")
        return
    amount = int(data.get("amount", 0))
    phone = data.get("phone")
    if not phone:
        await message.answer("Нужно указать телефон.")
        return
    user_service = UserService(session)
    user = await user_service.get_or_create(
        telegram_id=message.from_user.id,
        username=message.from_user.username,
        first_name=message.from_user.first_name,
        last_name=message.from_user.last_name,
    )
    payout_service = PayoutService(session)
    try:
        result = await payout_service.create_request(
            user_id=user.id,
            method=method,
            amount=amount,
            phone=phone,
            email=message.text.strip(),
        )
    except PayoutValidationError as exc:
        await message.answer(f"Не получилось создать заявку: {exc}")
        return
    await message.answer(
        "Заявка создана. Как только сертификат будет готов, вернёмся с уведомлением.",
    )


@router.message()
async def handle_text(message: Message, state: FSMContext, session: AsyncSession, llm_service: LLMService) -> None:
    if await state.get_state():
        await message.answer("Сначала завершим текущий процесс вывода.")
        return
    user_service = UserService(session)
    conversation = ConversationService(session, llm=llm_service)
    user = await user_service.get_or_create(
        telegram_id=message.from_user.id,
        username=message.from_user.username,
        first_name=message.from_user.first_name,
        last_name=message.from_user.last_name,
    )
    response = await conversation.handle(user, message.text)
    text = response.text
    if response.offers:
        text = await _deliver_offers(response, session, user.id, text)
    elif response.payout_requested:
        await state.set_state(PayoutForm.method)
        await message.answer(
            text + "\n\n" + "Выбери метод вывода:",
            reply_markup=_method_keyboard(),
        )
        return
    await message.answer(text)


async def _deliver_offers(
    response: ConversationResponse,
    session: AsyncSession,
    user_id: int,
    base_text: str,
) -> str:
    click_service = ClickService(session)
    recommendation_items = []
    for presentation in response.offers:
        offer = await session.get(Offer, presentation.id)
        if not offer:
            continue
        click, tracking_link = await click_service.create_click(
            user_id=user_id,
            offer=offer,
            slot="primary",
        )
        recommendation_items.append(
            {
                "offer_id": offer.id,
                "title": offer.title,
                "payout": presentation.payout,
                "tracking_link": tracking_link,
                "click_id": click.id,
            }
        )
    if not recommendation_items:
        return base_text
    rec_service = RecommendationService(session)
    session_model = await rec_service.create_session(user_id=user_id, items=recommendation_items)
    return base_text + "\n\n" + _bot2_hint(session_model.token)
