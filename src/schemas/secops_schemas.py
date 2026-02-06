from pydantic import BaseModel, Field
from typing import List, Optional
from enum import Enum

class ReviewVerdict(str, Enum):
    APPROVED = "approved"
    APPROVED_WITH_WARNINGS = "approved_with_warnings"
    REJECTED = "rejected"

class SecurityReview(BaseModel):
    """Resultado de la revisión de seguridad del código Terraform."""
    verdict: ReviewVerdict = Field(..., description="approved: sin hallazgos. approved_with_warnings: hallazgos medium/low. rejected: solo si hay hallazgos Critical o High.")
    risk_analysis: str = Field(...)
    critical_findings: Optional[List[str]] = Field(default=[])
    warnings: Optional[List[str]] = Field(default=[])