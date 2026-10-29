# Pipeline de Extracción de Entidades Técnicas

Recibe texto crudo (descripción de arquitectura, log de error) y devuelve un objeto Pydantic validado.

## Estructura

| Archivo | Contenido |
|---|---|
| `schemas.py` | Modelo `ExtraccionTecnica` (`tecnologias` no vacía, `nivel_de_criticidad` enum, `resumen_tecnico`) |
| `chain.py` | `ChatPromptTemplate` + `prompt \| model.with_structured_output(...)` + `.with_retry()` + `process_text()` async |
| `test_pipeline.py` | Script asíncrono con 2 casos normales y 1 texto ambiguo (prueba de estrés) |

## Uso

```bash
python -m venv .venv && .venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env      # completar la API key
python test_pipeline.py
```

`LLM_PROVIDER=openai|anthropic|gemini` y `LLM_MODEL` en `.env` eligen el cliente.

## Ejemplo de salida

```json
{
  "tecnologias": ["FastAPI", "Redis", "PostgreSQL"],
  "nivel_de_criticidad": "alta",
  "resumen_tecnico": "API con caché en Redis y persistencia en PostgreSQL; cuello de botella en conexiones concurrentes."
}
```

## Resiliencia

- La cadena usa `with_structured_output(..., include_raw=True)` y un paso final que valida el resultado.
- Se lanza excepción (y `.with_retry()` reintenta, hasta `MAX_ATTEMPTS`, con backoff exponencial) si:
  - el JSON es inválido o no cumple el esquema (`ValidationError` / `OutputParserException`);
  - `finish_reason`/`stop_reason` indica corte (`length`, `max_tokens`, `content_filter`);
  - el modelo no devuelve objeto.
- Los logs (`pipeline`) muestran cada advertencia de reintento, la validación OK y el fallo final.
- Los prompts usan `ChatPromptTemplate` con variable `{texto}`; sin f-strings.
