"""Contrato de salida del pipeline de extracción de entidades técnicas."""
from enum import Enum

from pydantic import BaseModel, Field, field_validator


class NivelCriticidad(str, Enum):
    baja = "baja"
    media = "media"
    alta = "alta"


class ExtraccionTecnica(BaseModel):
    """Entidades técnicas extraídas de un texto (arquitectura, log de error, etc.)."""

    tecnologias: list[str] = Field(
        ...,
        min_length=1,
        description="Tecnologías, frameworks, servicios o herramientas mencionadas. No puede estar vacía.",
    )
    nivel_de_criticidad: NivelCriticidad = Field(
        ...,
        description="Criticidad del problema o sistema descrito: baja, media o alta.",
    )
    resumen_tecnico: str = Field(
        ...,
        min_length=10,
        max_length=500,
        description="Resumen técnico conciso (1-2 oraciones) en español.",
    )

    @field_validator("tecnologias")
    @classmethod
    def _limpiar_tecnologias(cls, v: list[str]) -> list[str]:
        limpias = list(dict.fromkeys(t.strip() for t in v if t and t.strip()))
        if not limpias:
            raise ValueError("tecnologias no puede estar vacía")
        return limpias
