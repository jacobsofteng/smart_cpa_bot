"""User service layer."""

from __future__ import annotations

import random
import string
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..models import Referral, ReferralStatus, User, UserStatus


def _generate_referral_code(length: int = 8) -> str:
    alphabet = string.ascii_lowercase + string.digits
    return "ref" + "".join(random.choice(alphabet) for _ in range(length))


class UserService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_or_create(self, *, telegram_id: int, username: str | None, first_name: str | None, last_name: str | None) -> User:
        stmt = select(User).where(User.telegram_id == telegram_id)
        result = await self.session.execute(stmt)
        user = result.scalar_one_or_none()
        if user:
            return user
        referral_code = _generate_referral_code()
        user = User(
            telegram_id=telegram_id,
            username=username,
            first_name=first_name,
            last_name=last_name,
            display_name=first_name or username or "",
            referral_code=referral_code,
            status=UserStatus.NEW,
        )
        self.session.add(user)
        await self.session.flush()
        return user

    async def update_profile(
        self,
        user: User,
        *,
        name: Optional[str] = None,
        age: Optional[int] = None,
        city: Optional[str] = None,
        phone: Optional[str] = None,
        email: Optional[str] = None,
        consents: Optional[dict] = None,
        referral_code: Optional[str] = None,
    ) -> User:
        if name:
            user.display_name = name
        if age:
            user.age = age
        if city:
            user.city = city
        if phone:
            user.phone = phone
        if email:
            user.email = email
        if consents:
            user.consents = consents
        if referral_code:
            await self._bind_referral(user, referral_code)
        if user.status == UserStatus.NEW and user.age:
            user.status = UserStatus.ONBOARDED
        await self.session.flush()
        return user

    async def _bind_referral(self, user: User, code: str) -> None:
        if code == user.referral_code:
            return
        stmt = select(User).where(User.referral_code == code)
        referrer = (await self.session.execute(stmt)).scalar_one_or_none()
        if not referrer:
            return
        user.referred_by_id = referrer.id
        referral = Referral(
            referrer_user_id=referrer.id,
            referee_user_id=user.id,
            code=code,
            status=ReferralStatus.ATTRIBUTED,
        )
        self.session.add(referral)
        await self.session.flush()


__all__ = ["UserService"]
