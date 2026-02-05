from typing import List, Dict

from pydantic import BaseModel, Field

class TerraformDesign(BaseModel):
    """
    Representa un diseño completo de Terraform listo para revisión.
    
    El hcl_code debe ser un objeto JSON donde las claves son nombres de archivos
    y los valores son el contenido HCL.
    """
    rationale: str = Field(..., description="Justificación de decisiones arquitectónicas y trade-offs.")
    hcl_code: Dict[str, str] = Field(
        ..., 
        description="Diccionario de archivos Terraform. Las claves son nombres de archivo (ej: 'main.tf', 'variables.tf', 'outputs.tf') y los valores son el contenido HCL de cada archivo."
    )
    required_providers: List[str] = Field(default=["hashicorp/aws"], description="Lista de providers requeridos.")