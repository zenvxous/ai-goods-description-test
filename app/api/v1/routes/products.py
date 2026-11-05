"""Product card generation endpoints (business logic is not implemented yet)."""

from fastapi import APIRouter

router = APIRouter(prefix="/products", tags=["products"])
