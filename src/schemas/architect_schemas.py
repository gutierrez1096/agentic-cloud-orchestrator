from pydantic import BaseModel, Field, validator
from typing import List

class TerraformDesign(BaseModel):
    """
    Call this tool ONLY when you have a complete, secure, and validated Terraform design.
    This signals the end of the architecture phase.
    """
    rationale: str = Field(
        ..., 
        description="Explanation of module choices, cost trade-offs, and architectural decisions."
    )
    hcl_code: str = Field(
        ..., 
        description="The final, valid Terraform HCL code block."
    )
    required_providers: List[str] = Field(
        default=["hashicorp/aws"], 
        description="List of required providers."
    )