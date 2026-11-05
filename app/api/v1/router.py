from fastapi import APIRouter

from app.api.v1.routes.health import router as health_router
from app.api.v1.routes.products import router as products_router

router = APIRouter(prefix="/api/v1")

router.include_router(health_router)
router.include_router(products_router)
