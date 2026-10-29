"""Mini-script asíncrono: un caso normal y una prueba de estrés con texto ambiguo."""
import asyncio
import json

from chain import process_text

EJEMPLOS = {
    "arquitectura": (
        "CRITICAL - 2026-10-28 18:45:12 - Outbound HTTP Call to [https://api.auth-service.com/v1/oauth/token](https://api.auth-service.com/v1/oauth/token) failed. Reason: java.net.SocketTimeoutException: Read timed out after 5000ms. Retries exhausted (3/3)."
    ),
    "log_error": (
        "[2026-10-28 21:14:02,104] [ERROR] [pyspark.sql.utils.AnalysisException] Failed to merge schema for table gold_profuturo.afore_movimientos: Failed to merge fields 'monto' (DecimalType(18,2)) and 'monto' (StringType). Job run_id: 849201. Executor node ip-10-0-4-12.ec2.internal."
    ),
    "ambiguo (estrés)": "Procesamos archivos raw CSV de transacciones bancarias desde un bucket S3 landing en la capa Bronze guardando en formato Delta. En la capa Silver aplicamos deduplicación por transaction_id, casteos de fechas y validación de nulos. Finalmente, en Gold generamos tablas agregadas diarias por cliente cargadas a Synapse.",
}


async def main() -> None:
    resultados = await asyncio.gather(
        *(process_text(t) for t in EJEMPLOS.values()), return_exceptions=True
    )
    salidas = {}
    for nombre, res in zip(EJEMPLOS, resultados):
        print(f"\n=== {nombre} ===")
        if isinstance(res, Exception):
            print(f"FALLÓ: {type(res).__name__}: {res}")
            salidas[nombre] = {"error": f"{type(res).__name__}: {res}"}
        else:
            print(res.model_dump_json(indent=2))
            salidas[nombre] = res.model_dump(mode="json")

    with open("salidas.json", "w", encoding="utf-8") as f:
        json.dump(salidas, f, ensure_ascii=False, indent=2)
    print("\nSalidas guardadas en salidas.json")


if __name__ == "__main__":
    asyncio.run(main())
