from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.order import Order, OrderStatus


async def create_order(
    session: AsyncSession,
    *,
    user_id: int,
    event_id: int,
    quantity: int,
    customer_location: str,
) -> Order:
    order = Order(
        user_id=user_id,
        event_id=event_id,
        quantity=quantity,
        customer_location=customer_location,
        status=OrderStatus.NEW,
    )
    session.add(order)
    await session.flush()
    return order


async def list_user_orders(session: AsyncSession, user_id: int) -> list[Order]:
    result = await session.execute(
        select(Order)
        .where(Order.user_id == user_id)
        .options(selectinload(Order.event))
        .order_by(Order.created_at.desc())
    )
    return list(result.scalars().all())


async def get_order_with_details(session: AsyncSession, order_id: int) -> Order | None:
    result = await session.execute(
        select(Order)
        .where(Order.id == order_id)
        .options(selectinload(Order.user), selectinload(Order.event), selectinload(Order.manager))
    )
    return result.scalar_one_or_none()


async def update_order_status(
    session: AsyncSession,
    *,
    order_id: int,
    status: OrderStatus,
    manager_id: int | None,
) -> Order | None:
    order = await get_order_with_details(session, order_id)
    if order is None:
        return None

    order.status = status
    order.manager_id = manager_id
    await session.flush()
    return order
