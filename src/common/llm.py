"""LangChain structured-output boundary; business services never import an SDK."""
import os
from typing import TypeVar
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()
T = TypeVar("T", bound=BaseModel)

class LLMClient:
    def __init__(self) -> None:
        self.provider = os.getenv("LLM_PROVIDER", "local").lower()
        self.model = os.getenv("LLM_MODEL", "")
        self.seed = int(os.getenv("LLM_SEED", "42"))
    @property
    def enabled(self) -> bool:
        return self.provider in {"openai", "openai_compatible"} and bool(os.getenv("LLM_API_KEY")) and bool(self.model)
    def structured(self, system: str, user: str, schema: type[T]) -> T:
        if not self.enabled:
            raise RuntimeError("No structured LLM provider is configured; local deterministic policy is active.")
        # LangChain's OpenAI adapter also supports OpenAI-compatible endpoints via
        # LLM_BASE_URL, allowing the provider endpoint/model to be swapped in .env.
        from langchain_core.prompts import ChatPromptTemplate
        from langchain_openai import ChatOpenAI
        options = {"model": self.model, "api_key": os.environ["LLM_API_KEY"], "temperature": 0, "seed": self.seed}
        if os.getenv("LLM_BASE_URL"):
            options["base_url"] = os.environ["LLM_BASE_URL"]
        model = ChatOpenAI(**options)
        chain = ChatPromptTemplate.from_messages([("system", system), ("human", "{input}")]) | model.with_structured_output(schema, method="function_calling")
        result = chain.invoke({"input": user})
        if not isinstance(result, schema):
            return schema.model_validate(result)
        return result
