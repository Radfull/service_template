from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

class BaseDbModel(DeclarativeBase):
    __abstract__ = True

    request_id: Mapped[int] = mapped_column(primary_key=True)
