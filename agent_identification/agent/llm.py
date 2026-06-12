import os
from pathlib import Path
from dotenv import load_dotenv

env_path = Path(__file__).parent.parent / ".env"
if env_path.exists():
    load_dotenv(env_path)


def get_llm(provider: str = "auto", temperature: float = 0.1):
    if provider == "ollama":
        from langchain_ollama import ChatOllama

        return ChatOllama(model="qwen2.5:1.5b", temperature=temperature)

    groq_key = os.getenv("GROQ_API_KEY")
    google_key = os.getenv("GOOGLE_API_KEY")
    openai_key = os.getenv("OPENAI_API_KEY")

    if provider == "groq" and groq_key:
        from langchain_groq import ChatGroq

        return ChatGroq(model="llama-3.1-8b-instant", temperature=temperature)

    if provider == "gemini" and google_key:
        from langchain_google_genai import ChatGoogleGenerativeAI

        return ChatGoogleGenerativeAI(model="gemini-2.0-flash", temperature=temperature)

    if provider == "openai" and openai_key:
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(model="gpt-4o-mini", temperature=temperature)

    if provider == "auto":
        if groq_key:
            from langchain_groq import ChatGroq

            return ChatGroq(model="llama-3.1-8b-instant", temperature=temperature)
        if google_key:
            from langchain_google_genai import ChatGoogleGenerativeAI

            return ChatGoogleGenerativeAI(
                model="gemini-2.0-flash", temperature=temperature
            )
        if openai_key:
            from langchain_openai import ChatOpenAI

            return ChatOpenAI(model="gpt-4o-mini", temperature=temperature)

    raise ValueError(
        "Aucune clé API trouvée. Configure GROQ_API_KEY, GOOGLE_API_KEY "
        "ou OPENAI_API_KEY dans le fichier .env, ou utilise provider='ollama'"
    )
