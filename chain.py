"""Cadena LCEL: prompt | model.with_structured_output(Schema) con reintentos."""
import logging
import os

try:  # usa el almacén de certificados del SO (útil tras proxies/antivirus con TLS)
    import truststore

    truststore.inject_into_ssl()
except ImportError:
    pass

from dotenv import load_dotenv
from langchain_core.exceptions import OutputParserException
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableLambda
from pydantic import ValidationError

from schemas import ExtraccionTecnica

load_dotenv()

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger("pipeline")

MAX_ATTEMPTS = int(os.getenv("MAX_ATTEMPTS", "3"))  # 1 intento + reintentos

# finish_reason (OpenAI) / stop_reason (Anthropic) que indican respuesta cortada
TRUNCATED_REASONS = {"length", "max_tokens", "content_filter", "MAX_TOKENS", "SAFETY"}


class IncompleteResponseError(Exception):
    """El LLM cortó la respuesta (tokens agotados, filtro) o no devolvió objeto."""


def get_model():
    """Cliente según LLM_PROVIDER (openai | anthropic | gemini)."""
    provider = os.getenv("LLM_PROVIDER", "openai").lower()
    if provider == "anthropic":
        from langchain_anthropic import ChatAnthropic

        return ChatAnthropic(
            model=os.getenv("LLM_MODEL", "claude-haiku-5-5"),
            temperature=0,
            max_tokens=1024,
        )
    if provider == "gemini":
        from langchain_google_genai import ChatGoogleGenerativeAI

        return ChatGoogleGenerativeAI(
            model=os.getenv("LLM_MODEL", "gemini-3.8-flash"),
            temperature=0,
            max_output_tokens=1024,
        )
    from langchain_openai import ChatOpenAI

    return ChatOpenAI(
        model=os.getenv("LLM_MODEL", "gpt-4o-mini"),
        temperature=0,
        max_tokens=1024,
    )


prompt = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "Eres un ingeniero de software senior. Extrae entidades técnicas del texto "
            "del usuario y devuelve SOLO la estructura solicitada.\n"
            "- tecnologias: lista no vacía de tecnologías mencionadas (o claramente implícitas).\n"
            "- nivel_de_criticidad: 'baja', 'media' o 'alta' según impacto y urgencia.\n"
            "- resumen_tecnico: 1-2 oraciones en español.\n"
            "Si el texto es ambiguo, infiere lo más razonable; no inventes tecnologías.",
        ),
        ("human", "Texto a analizar:\n\n{texto}"),
    ]
)

# include_raw=True permite inspeccionar finish_reason y el error de parseo.
_structured = get_model().with_structured_output(ExtraccionTecnica, include_raw=True)


def _validar(result: dict) -> ExtraccionTecnica:
    """Detecta truncado / JSON mal formado / esquema incompleto y lanza para que
    with_retry reintente."""
    raw = result.get("raw")
    meta = getattr(raw, "response_metadata", {}) or {}
    reason = meta.get("finish_reason") or meta.get("stop_reason")
    if reason in TRUNCATED_REASONS:
        logger.warning("Respuesta truncada (finish_reason=%s)", reason)
        raise IncompleteResponseError(f"finish_reason={reason}")

    if result.get("parsing_error") is not None:
        logger.warning("Salida inválida: %s", result["parsing_error"])
        raise result["parsing_error"]

    parsed = result.get("parsed")
    if parsed is None:
        logger.warning("El modelo no devolvió un objeto estructurado")
        raise IncompleteResponseError("parsed=None")

    logger.info("Validación OK (finish_reason=%s)", reason)
    return parsed


chain = (prompt | _structured | RunnableLambda(_validar)).with_retry(
    retry_if_exception_type=(
        ValidationError,
        OutputParserException,
        IncompleteResponseError,
    ),
    wait_exponential_jitter=True,
    stop_after_attempt=MAX_ATTEMPTS,
)


async def process_text(text: str) -> ExtraccionTecnica:
    """Procesa texto crudo y devuelve un ExtraccionTecnica validado."""
    logger.info("Procesando texto (%d caracteres)", len(text))
    try:
        result = await chain.ainvoke({"texto": text})
    except Exception as exc:
        logger.error("Fallo tras %d intentos: %s: %s", MAX_ATTEMPTS, type(exc).__name__, exc)
        raise
    logger.info("Resultado: %s", result.model_dump_json())
    return result
