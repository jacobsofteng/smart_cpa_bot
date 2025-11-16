"""Router for the offer board bot."""

from __future__ import annotations

import re

from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from aiogram.filters.callback_data import CallbackData
from sqlalchemy.ext.asyncio import AsyncSession

from ...services.feedback import FeedbackService
from ...services.recommendations import RecommendationService
from ...services.users import UserService

router = Router(name="offers")


class FeedbackForm(StatesGroup):
    rating = State()


class OfferDoneCallback(CallbackData, prefix="done"):
    offer_id: int
    click_id: int


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext, session: AsyncSession) -> None:
    args = message.text.split(" ", 1)
    token = args[1] if len(args) > 1 else None
    user_service = UserService(session)
    await user_service.get_or_create(
        telegram_id=message.from_user.id,
        username=message.from_user.username,
        first_name=message.from_user.first_name,
        last_name=message.from_user.last_name,
    )
    if not token:
        await message.answer("Здесь появляются карточки заданий от первого бота. Попроси его подобрать варианты.")
        return
    rec_service = RecommendationService(session)
    session_model = await rec_service.get_session(token)
    if not session_model:
        await message.answer("Сессия устарела. Запроси подбор ещё раз в основном боте.")
        return
    for item in session_model.payload.get("items", []):
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="Открыть", url=item["tracking_link"])],
                [
                    InlineKeyboardButton(
                        text="Сообщить о выполнении",
                        callback_data=OfferDoneCallback(
                            offer_id=item["offer_id"],
                            click_id=item["click_id"],
                        ).pack(),
                    )
                ],
            ]
        )
        await message.answer(
            f"{item['title']}\nВознаграждение: ~{item['payout']} баллов",
            reply_markup=kb,
        )


@router.callback_query(OfferDoneCallback.filter())
async def handle_done(callback: CallbackQuery, callback_data: OfferDoneCallback, state: FSMContext) -> None:
    await callback.answer()
    await state.update_data(offer_id=callback_data.offer_id, click_id=callback_data.click_id)
    await state.set_state(FeedbackForm.rating)
    await callback.message.answer(
        "Отлично! Напиши оценку от 1 до 5 и пару слов, всё ли прошло гладко."
    )


@router.message(FeedbackForm.rating)
async def handle_feedback(message: Message, state: FSMContext, session: AsyncSession) -> None:
    data = await state.get_data()
    await state.clear()
    offer_id = data.get("offer_id")
    if not offer_id:
        await message.answer("Не нашли задание, попробуй снова через кнопку.")
        return
    text = message.text or ""
    match = re.search(r"([1-5])", text)
    if not match:
        await message.answer("Укажи оценку от 1 до 5 в сообщении.")
        return
    rating = int(match.group(1))
    comment = text
    feedback_service = FeedbackService(session)
    user_service = UserService(session)
    user = await user_service.get_or_create(
        telegram_id=message.from_user.id,
        username=message.from_user.username,
        first_name=message.from_user.first_name,
        last_name=message.from_user.last_name,
    )
    await feedback_service.submit(
        user_id=user.id,
        offer_id=int(offer_id),
        rating=rating,
        comment=comment,
        ready_to_repeat="ещё" in text.lower(),
    )
    await message.answer(
        "Спасибо! Поставили задачу на проверку и сообщим, как только партнёр подтвердит начисление."
    )
