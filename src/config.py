import os

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import MemorySaver

load_dotenv()

INFRA_WORKSPACE = "./infra_workspace"
PROTECTED_TERRAFORM_FILES = frozenset({"provider.tf"})


def get_model(model_name: str = "gpt-5-mini-2025-08-07", timeout: int = 60):

    openai_api_key = os.getenv("OPENAI_API_KEY")
    if not openai_api_key:
        raise RuntimeError(
            "OPENAI_API_KEY no está definido. Configúralo en el entorno o en un fichero .env."
        )

    model = ChatOpenAI(
            model=model_name,
            temperature=0.7,
            max_tokens=None,
            timeout=timeout
        )

    return model

def get_checkpointer():
    return MemorySaver()
