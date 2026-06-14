from app.handlers.client import router as client_router
from app.handlers.common import router as common_router
from app.handlers.manager import router as manager_router
from app.handlers.orders import router as orders_router

__all__ = (
    "client_router",
    "common_router",
    "manager_router",
    "orders_router",
)
