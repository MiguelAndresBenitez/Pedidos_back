"""Chequeo de vida para Docker y el balanceador."""

from fastapi import APIRouter

router_de_salud = APIRouter()


@router_de_salud.get("/salud")
async def consultar_salud() -> dict[str, str]:
    return {"estado": "ok"}
