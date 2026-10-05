"""
Create
Read
Update
Delete
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from market.service.db.models.predictions_model import Predictions
from market.service.schemas.predictions import (
    PredictionCreate,
    PredictionUpdate,
    PredictionUpdatePartial,
)


async def get_predictions(session: AsyncSession | None) -> list[Predictions]:
    if session is None:
        return []
    stmt = select(Predictions).order_by(Predictions.request_id)
    res = await session.execute(stmt)
    return list(res.scalars().all())


async def get_prediction(
    session: AsyncSession | None,
    request_id: int,
) -> Predictions | None:
    if session is None:
        return None
    return await session.get(Predictions, request_id)


async def create_prediction(
    session: AsyncSession | None,
    pred_in: PredictionCreate,
) -> Predictions:
    pred = Predictions(**pred_in.model_dump())
    if session is not None:
        session.add(pred)
        await session.commit()
        await session.refresh(pred)
    return pred


async def update_item(
    session: AsyncSession | None,
    pred: Predictions,
    pred_update: PredictionUpdate | PredictionUpdatePartial,
    partial: bool = False,
) -> Predictions:
    for name, value in pred_update.model_dump(exclude_unset=partial).items():
        setattr(pred, name, value)
    if session is not None:
        await session.commit()
    return pred


async def delete_item(
    session: AsyncSession | None,
    pred: Predictions,
) -> None:
    if session is None:
        return
    await session.delete(pred)
    await session.commit()