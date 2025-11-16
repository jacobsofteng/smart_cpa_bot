import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from smart_cpa_bot.models import Base
from smart_cpa_bot.services.conversation import ConversationService
from smart_cpa_bot.services.llm import LLMService
from smart_cpa_bot.services.users import UserService


class DummyLLM(LLMService):
    def __init__(self) -> None:  # type: ignore[call-arg]
        pass

    async def generate(self, messages):  # type: ignore[override]
        return "Расскажи, какие задания интересны — подберу варианты."

    def violates_policy(self, text: str) -> bool:  # type: ignore[override]
        return False


@pytest_asyncio.fixture
async def session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    Session = async_sessionmaker(engine, expire_on_commit=False)
    async with Session() as session:
        yield session
    await engine.dispose()


@pytest.mark.asyncio
async def test_onboarding_flow(session):
    user_service = UserService(session)
    user = await user_service.get_or_create(
        telegram_id=1,
        username="tester",
        first_name="Test",
        last_name=None,
    )
    svc = ConversationService(session, llm=DummyLLM())

    # Expect age prompt because name already known from profile
    response = await svc.handle(user, "")
    assert "Возраст" in response.text

    response = await svc.handle(user, "не число")
    assert "Возраст" in response.text

    await user_service.update_profile(user, age=21)
    response = await svc.handle(user, "пропустить")
    assert "город" in response.text.lower()
