from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    openai_api_key: str = ""
    langchain_api_key: str = ""
    langchain_tracing_v2: bool = False
    langchain_project: str = "TUTTOP-agent"

    serpapi_api_key: str = ""

    model_name: str = "gpt-4o-mini"
    model_temperature: float = 0.1

    max_schools_per_run: int = 50
    request_timeout: int = 15
    rate_limit_delay: float = 1.0

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
