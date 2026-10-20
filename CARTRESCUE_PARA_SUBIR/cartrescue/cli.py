from __future__ import annotations

import argparse
from pathlib import Path

from .simulation import Experimento, escenarios_predeterminados


def principal() -> int:
    analizador = argparse.ArgumentParser(description="Simulación reproducible de CARTRESCUE-AGENT")
    analizador.add_argument("--todo", action="store_true", help="ejecuta el catálogo completo de escenarios")
    analizador.add_argument("--repeticiones", type=int, default=5,
                            help="repeticiones por escenario (mínimo recomendado: 5)")
    analizador.add_argument("--semilla", type=int, default=20261019, help="semilla del entorno estocástico")
    analizador.add_argument("--salida", type=Path, default=Path("evidence/latest"),
                            help="directorio de evidencia")
    argumentos = analizador.parse_args()
    if not argumentos.todo:
        analizador.error("use --todo para ejecutar el catálogo de escenarios")
    if argumentos.repeticiones < 5:
        analizador.error("--repeticiones debe ser >= 5 para cumplir el protocolo de evaluación")
    experimento = Experimento(semilla=argumentos.semilla)
    experimento.ejecutar(escenarios_predeterminados(), repeticiones=argumentos.repeticiones)
    resumen = experimento.escribir_evidencia(argumentos.salida)
    metricas = resumen["metricas"]
    print(f"semilla={resumen['semilla']} escenarios={len(escenarios_predeterminados())} "
          f"repeticiones={resumen['repeticiones']}")
    print(f"tasa_recuperacion={metricas['tasa_recuperacion']:.2%} "
          f"meta>=15%: {metricas['meta_cumplida']}")
    print(f"cumplimiento_politica={metricas['cumplimiento_politica']:.2%} "
          f"meta=100%: {metricas['meta_politica_cumplida']}")
    print(f"evidencia={argumentos.salida}")
    return 0 if metricas["meta_cumplida"] and metricas["meta_politica_cumplida"] else 2


if __name__ == "__main__":
    raise SystemExit(principal())
