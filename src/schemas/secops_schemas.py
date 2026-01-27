from pydantic import BaseModel, Field
from typing import List, Optional

class SecurityReview(BaseModel):
    """Resultado de la revisión de seguridad del código Terraform."""
    
    is_approved: bool = Field(..., description="True si el código cumple los estándares de seguridad.")
    risk_analysis: str = Field(..., description="Análisis detallado de riesgos y cumplimiento de benchmarks.")
    required_changes: Optional[List[str]] = Field(default=[], description="Cambios requeridos para aprobar el diseño.")