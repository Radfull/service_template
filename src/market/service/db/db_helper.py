from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from market.config import settings


class DatabaseHelper:
    def __init__(self, url: str, echo: bool = False):
        self.engine = create_async_engine(
            url=url,
            echo=echo
        )
        self.session_factory = async_sessionmaker(
            bind=self.engine,
            autoflush=False,
            autocommit=False,
            expire_on_commit=False,
        )
    async def session_dependency(self) -> AsyncGenerator[AsyncSession, None]:
        async with self.session_factory() as session:
            yield session

    async def dispose(self) -> None:
        await self.engine.dispose()

db_helper: DatabaseHelper | None = (
    DatabaseHelper(url=settings.db_url, echo=settings.db_echo)
    if settings.db_url
    else None
)

async def get_session() -> AsyncGenerator[AsyncSession | None, None]:
    if db_helper is None:
        yield None
        return
    async with db_helper.session_factory() as session:
        yield session