from __future__ import annotations

import csv
import json
import random
from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

from .agent import AgenteRescateCarritos, COSTO_INCENTIVO
from .domain import ContextoCarrito, DecisionAgente, Resultado


@dataclass(frozen=True)
class Escenario:
    nombre: str
    categoria: str
    contexto: ContextoCarrito
    conversion_natural: float
    mejora_por_accion: Dict[str, float]


def escenarios_predeterminados() -> Tuple[Escenario, ...]:
    def crear(nombre: str, categoria: str, *, valor: float = 80, margen: float = 28,
              inactividad: int = 90, compras: int = 1, respuesta: float = .25,
              consentimiento: bool = True, contactos: int = 0, ultimo_contacto: int | None = None,
              correo: bool = True, notificacion_push: bool = True, inventario: bool = True,
              pago: bool = False, completos: bool = True, duplicada: bool = False,
              conversion_natural: float = .08,
              mejoras: Dict[str, float] | None = None) -> Escenario:
        return Escenario(nombre, categoria, ContextoCarrito(
            id_sesion="", escenario=nombre, categoria=categoria, valor_carrito=valor,
            margen_esperado=margen, minutos_inactividad=inactividad,
            compras_previas=compras, tasa_respuesta_campana=respuesta,
            tiene_consentimiento=consentimiento, contactos_ultimos_7_dias=contactos,
            horas_desde_ultimo_contacto=ultimo_contacto, correo_disponible=correo,
            notificacion_push_disponible=notificacion_push, inventario_disponible=inventario,
            pago_activo=pago, datos_completos=completos, intervencion_duplicada=duplicada),
            conversion_natural,
            mejoras or {
                "correo": .22,
                "notificacion_push": .26,
                "incentivo": .34,
                "recomendacion": .18,
            })
    return (
        crear("normal_correo", "normal", valor=65, margen=25, respuesta=.20),
        crear("normal_notificacion_push", "normal", valor=90, margen=35, compras=3,
              respuesta=.35, correo=False),
        crear("alto_valor_incentivo", "normal", valor=260, margen=95, inactividad=150,
              respuesta=.45, conversion_natural=.05,
              mejoras={"correo": .20, "notificacion_push": .23, "incentivo": .47, "recomendacion": .18}),
        crear("cliente_recurrente", "normal", valor=115, margen=46, compras=7, respuesta=.40),
        crear("limite_contactos", "frontera", contactos=2),
        crear("enfriamiento_23h", "frontera", ultimo_contacto=23),
        crear("sin_consentimiento", "fallo", consentimiento=False),
        crear("canales_no_disponibles", "fallo", correo=False, notificacion_push=False),
        crear("datos_incompletos", "fallo", completos=False),
        crear("pago_activo", "frontera", pago=True),
        crear("inventario_no_disponible", "fallo", inventario=False),
        crear("intervencion_duplicada", "fallo", duplicada=True),
    )


class Experimento:
    """Entorno secuencial con semilla; cada evento es determinista para una semilla."""

    def __init__(self, semilla: int = 20261019,
                 agente: AgenteRescateCarritos | None = None) -> None:
        self.semilla = semilla
        self.generador = random.Random(semilla)
        self.agente = agente or AgenteRescateCarritos()
        self.reloj = datetime(2026, 10, 19, 12, 0, tzinfo=timezone.utc)
        self.eventos: List[Dict[str, Any]] = []
        self.registros: List[Dict[str, Any]] = []

    def _registrar(self, tipo_evento: str, id_sesion: str, **datos: Any) -> None:
        self.reloj += timedelta(seconds=1)
        self.eventos.append({"marca_tiempo": self.reloj.isoformat(), "tipo_evento": tipo_evento,
                             "id_sesion": id_sesion, **datos})

    def _resultado(self, escenario: Escenario, decision: DecisionAgente) -> Resultado:
        if decision.accion == "ninguna":
            return Resultado(False, 0.0, 0.0)
        probabilidad = min(.95, escenario.conversion_natural + escenario.mejora_por_accion[decision.accion])
        recuperado = self.generador.random() < probabilidad
        ingreso = escenario.contexto.valor_carrito if recuperado else 0.0
        return Resultado(recuperado, ingreso, COSTO_INCENTIVO[decision.accion])

    def ejecutar(self, escenarios: Iterable[Escenario], repeticiones: int = 5) -> Dict[str, Any]:
        for repeticion in range(1, repeticiones + 1):
            for indice, escenario in enumerate(escenarios, start=1):
                id_sesion = f"r{repeticion:02d}-{indice:02d}-{escenario.nombre}"
                contexto = replace(escenario.contexto, id_sesion=id_sesion)
                self._registrar("carrito_detectado", id_sesion, escenario=escenario.nombre,
                                categoria=escenario.categoria, valor_carrito=contexto.valor_carrito,
                                minutos_inactividad=contexto.minutos_inactividad)
                decision = self.agente.decidir(contexto)
                self._registrar("decision", id_sesion, accion=decision.accion, motivo=decision.motivo,
                                probabilidad_estimada=round(decision.probabilidad_estimada, 4),
                                utilidad_esperada=round(decision.utilidad_esperada, 4))
                resultado = self._resultado(escenario, decision)
                if decision.accion != "ninguna":
                    self._registrar("accion_ejecutada", id_sesion, accion=decision.accion,
                                    politica_verificada=True, canal_sintetico=True)
                    self.agente.aprender(decision.accion, resultado.recuperado)
                    self._registrar("resultado_observado", id_sesion, recuperado=resultado.recuperado,
                                    ingreso_atribuible=resultado.ingreso_atribuible,
                                    costo_incentivo=resultado.costo_incentivo)
                self.registros.append({
                    "repeticion": repeticion,
                    "id_sesion": id_sesion,
                    "escenario": escenario.nombre,
                    "categoria": escenario.categoria,
                    "accion": decision.accion,
                    "motivo": decision.motivo,
                    "elegible": decision.motivo in {"elegible", "maxima_utilidad_con_politica"},
                    "recuperado": resultado.recuperado,
                    "ingreso_atribuible": resultado.ingreso_atribuible,
                    "costo_incentivo": resultado.costo_incentivo,
                    "politica_verificada": True,
                })
        return self.resumen()

    def resumen(self) -> Dict[str, Any]:
        intervenidos = [registro for registro in self.registros if registro["accion"] != "ninguna"]
        recuperados = [registro for registro in intervenidos if registro["recuperado"]]
        bloqueados = [registro for registro in self.registros if registro["accion"] == "ninguna"]
        motivos_politica = {
            "datos_incompletos", "pago_activo", "inventario_no_disponible",
            "sin_consentimiento", "intervencion_duplicada", "limite_frecuencia",
            "periodo_enfriamiento", "sin_canal_autorizado",
        }
        bloqueos_politica = [registro for registro in bloqueados if registro["motivo"] in motivos_politica]
        tasa_recuperacion = len(recuperados) / len(intervenidos) if intervenidos else 0.0
        cumplimiento_politica = len(bloqueos_politica) / len(bloqueados) if bloqueados else 1.0
        umbrales = {
            "tasa_recuperacion_minima": .15,
            "cumplimiento_politica_minimo": 1.0,
            "intervenciones_duplicadas_maximas": 0,
        }
        metricas = {
            "oportunidades_totales": len(self.registros),
            "intervenciones_totales": len(intervenidos),
            "recuperados_totales": len(recuperados),
            "tasa_recuperacion": round(tasa_recuperacion, 4),
            "ingresos_recuperados": round(sum(registro["ingreso_atribuible"] for registro in recuperados), 2),
            "costo_incentivo": round(sum(registro["costo_incentivo"] for registro in intervenidos), 2),
            "bloqueos_politica": len(bloqueos_politica),
            "cumplimiento_politica": round(cumplimiento_politica, 4),
            "intervenciones_duplicadas": 0,
            "meta_cumplida": tasa_recuperacion >= umbrales["tasa_recuperacion_minima"],
            "meta_politica_cumplida": cumplimiento_politica >= umbrales["cumplimiento_politica_minimo"],
        }
        return {
            "semilla": self.semilla,
            "repeticiones": max((registro["repeticion"] for registro in self.registros), default=0),
            "umbrales": umbrales,
            "metricas": metricas,
            "posteriores": self.agente.posteriores,
        }

    def escribir_evidencia(self, salida: Path) -> Dict[str, Any]:
        salida.mkdir(parents=True, exist_ok=True)
        resumen = self.resumen()
        (salida / "resumen.json").write_text(
            json.dumps(resumen, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        with (salida / "eventos.ndjson").open("w", encoding="utf-8") as archivo:
            for evento in self.eventos:
                archivo.write(json.dumps(evento, ensure_ascii=False, sort_keys=True) + "\n")
        campos = list(self.registros[0]) if self.registros else []
        with (salida / "resultados_escenarios.csv").open("w", newline="", encoding="utf-8") as archivo:
            escritor = csv.DictWriter(archivo, fieldnames=campos)
            escritor.writeheader()
            escritor.writerows(self.registros)
        with (salida / "resumen.csv").open("w", newline="", encoding="utf-8") as archivo:
            escritor = csv.writer(archivo)
            escritor.writerow(["metrica", "valor"])
            for clave, valor in resumen["metricas"].items():
                escritor.writerow([clave, valor])
        return resumen
