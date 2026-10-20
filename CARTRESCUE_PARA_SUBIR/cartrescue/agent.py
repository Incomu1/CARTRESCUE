from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Iterable, Tuple

from .domain import ContextoCarrito, DecisionAgente

ACCIONES = ("correo", "notificacion_push", "incentivo", "recomendacion")
COSTO_INCENTIVO = {"correo": 0.02, "notificacion_push": 0.01, "incentivo": 8.00, "recomendacion": 0.05}


@dataclass
class AgenteRescateCarritos:
    """Agente de aprendizaje basado en utilidad con reglas explícitas de contacto.

    El aprendizaje usa una posterior Beta-Bernoulli por acción. Se mantiene simple,
    auditable y apropiada para una simulación académica sintética; no es un modelo de
    propensión para producción.
    """

    posteriores: Dict[str, list[float]] = field(
        default_factory=lambda: {accion: [3.0, 7.0] for accion in ACCIONES}
    )
    maximo_contactos_7_dias: int = 2
    horas_enfriamiento: int = 24

    def es_elegible(self, contexto: ContextoCarrito) -> Tuple[bool, str]:
        if not contexto.datos_completos:
            return False, "datos_incompletos"
        if contexto.pago_activo:
            return False, "pago_activo"
        if not contexto.inventario_disponible:
            return False, "inventario_no_disponible"
        if not contexto.tiene_consentimiento:
            return False, "sin_consentimiento"
        if contexto.intervencion_duplicada:
            return False, "intervencion_duplicada"
        if contexto.contactos_ultimos_7_dias >= self.maximo_contactos_7_dias:
            return False, "limite_frecuencia"
        if (contexto.horas_desde_ultimo_contacto is not None
                and contexto.horas_desde_ultimo_contacto < self.horas_enfriamiento):
            return False, "periodo_enfriamiento"
        if not (contexto.correo_disponible or contexto.notificacion_push_disponible):
            return False, "sin_canal_autorizado"
        return True, "elegible"

    @staticmethod
    def _ajuste_segmento(contexto: ContextoCarrito) -> float:
        # Solo usa señales observables; los motivos privados de la persona no se conocen.
        inactividad = min(contexto.minutos_inactividad / 180.0, 1.0)
        valor = min(contexto.valor_carrito / 300.0, 1.0)
        historial = min(contexto.compras_previas / 8.0, 1.0)
        return (-0.08 + 0.16 * inactividad + 0.08 * valor + 0.12 * historial
                + 0.12 * contexto.tasa_respuesta_campana)

    def probabilidad(self, accion: str, contexto: ContextoCarrito) -> float:
        alfa, beta = self.posteriores[accion]
        media_posterior = alfa / (alfa + beta)
        ajuste_accion = {
            "correo": 0.00,
            "notificacion_push": 0.02,
            "incentivo": 0.10,
            "recomendacion": 0.04,
        }[accion]
        return max(0.01, min(0.95, media_posterior + self._ajuste_segmento(contexto) + ajuste_accion))

    def decidir(self, contexto: ContextoCarrito) -> DecisionAgente:
        elegible, motivo = self.es_elegible(contexto)
        if not elegible:
            return DecisionAgente("ninguna", motivo, 0.0, 0.0)
        candidatas: Iterable[str] = ACCIONES
        if not contexto.correo_disponible:
            candidatas = tuple(accion for accion in candidatas if accion != "correo")
        if not contexto.notificacion_push_disponible:
            candidatas = tuple(accion for accion in candidatas if accion != "notificacion_push")
        # No se consideran incentivos cuando el margen del carrito es bajo.
        if contexto.margen_esperado < 12:
            candidatas = tuple(accion for accion in candidatas if accion != "incentivo")
        puntuadas = []
        for accion in candidatas:
            probabilidad = self.probabilidad(accion, contexto)
            costo_fatiga = 0.12 * contexto.contactos_ultimos_7_dias
            utilidad = probabilidad * contexto.margen_esperado - COSTO_INCENTIVO[accion] - costo_fatiga
            puntuadas.append((utilidad, accion, probabilidad))
        utilidad, accion, probabilidad = max(puntuadas)
        if utilidad <= 0:
            return DecisionAgente("ninguna", "utilidad_no_positiva", probabilidad, utilidad)
        return DecisionAgente(accion, "maxima_utilidad_con_politica", probabilidad, utilidad)

    def aprender(self, accion: str, recuperado: bool) -> None:
        if accion not in self.posteriores:
            return
        self.posteriores[accion][0 if recuperado else 1] += 1.0
