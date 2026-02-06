from pydantic import BaseModel, Field
from typing import List, Optional


class SecurityReview(BaseModel):
    """Resultado de la revisión de seguridad del código Terraform."""
    approved: bool = Field(
        ...,
        description="True si el código pasa la revisión (sin hallazgos Critical/High que obliguen a rechazar); False en caso contrario."
    )
    risk_analysis: str = Field(...)
    required_changes: Optional[List[str]] = Field(
        default=[],
        description="Lista de cambios requeridos cuando approved=False."
    )
