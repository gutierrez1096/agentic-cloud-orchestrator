import os

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import MemorySaver

load_dotenv()

INFRA_WORKSPACE = os.getenv("INFRA_WORKSPACE", "./infra_workspace")
PROTECTED_TERRAFORM_FILES = frozenset({"provider.tf", "localstack_providers_override.tf"})

MODEL_NAME = os.getenv("MODEL_NAME", "gpt-4.1-mini")
MODEL_TIMEOUT = int(os.getenv("MODEL_TIMEOUT", "60"))


def get_model(model_name: str | None = None, timeout: int | None = None):

    openai_api_key = os.getenv("OPENAI_API_KEY")
    if not openai_api_key:
        raise RuntimeError(
            "OPENAI_API_KEY is not set. Configure it in the environment or in a .env file."
        )


    model = ChatOpenAI(
            model=model_name or MODEL_NAME,
            temperature=0,
            max_tokens=None,
            timeout=timeout or MODEL_TIMEOUT
        )

    return model

def get_checkpointer():
    return MemorySaver()
