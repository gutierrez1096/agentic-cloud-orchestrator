from typing import Dict

from pydantic import BaseModel, Field


class TerraformFix(BaseModel):
    """
    Corrected Terraform HCL ready to be written to the workspace.
    Only non-protected .tf files (e.g. main.tf, variables.tf, outputs.tf).
    Do not include provider.tf or localstack_providers_override.tf.
    """
    hcl_code: Dict[str, str] = Field(
        ...,
        description="Dictionary of Terraform files. Keys are filenames (e.g. 'main.tf', 'variables.tf', 'outputs.tf') and values are the corrected HCL content for each file."
    )
    changes_summary: str = Field(
        default="",
        description="Brief description of what was fixed (optional)."
    )
