from pydantic import BaseModel, Field
from typing import List, Optional


class SecurityReview(BaseModel):
    """Result of the Terraform code security review."""
    approved: bool = Field(
        ...,
        description="True if the code passes the review (no Critical/High findings that require rejection); False otherwise."
    )
    risk_analysis: str = Field(...)
    required_changes: Optional[List[str]] = Field(
        default=[],
        description="List of required changes when approved=False."
    )
