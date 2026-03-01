from typing import List, Dict

from pydantic import BaseModel, Field

class TerraformDesign(BaseModel):
    """
    Represents a complete Terraform design ready for review.

    hcl_code must be a JSON object where keys are filenames and values are HCL content.
    """
    rationale: str = Field(..., description="Justification of architectural decisions and trade-offs.")
    hcl_code: Dict[str, str] = Field(
        ...,
        description="Dictionary of Terraform files. Keys are filenames (e.g. 'main.tf', 'variables.tf', 'outputs.tf') and values are the HCL content for each file."
    )
    required_providers: List[str] = Field(default=["hashicorp/aws"], description="List of required providers.")