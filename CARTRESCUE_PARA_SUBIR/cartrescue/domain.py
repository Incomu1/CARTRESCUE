from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class ContextoCarrito:
    """Señales sintéticas y no identificables disponibles en un punto de decisión."""

    id_sesion: str
    escenario: str
    categoria: str
    valor_carrito: float
    margen_esperado: float
    minutos_inactividad: int
    compras_previas: int
    tasa_respuesta_campana: float
    tiene_consentimiento: bool
    contactos_ultimos_7_dias: int
    horas_desde_ultimo_contacto: Optional[int]
    correo_disponible: bool
    notificacion_push_disponible: bool
    inventario_disponible: bool
    pago_activo: bool
    datos_completos: bool
    intervencion_duplicada: bool = False


@dataclass(frozen=True)
class DecisionAgente:
    accion: str
    motivo: str
    probabilidad_estimada: float
    utilidad_esperada: float


@dataclass(frozen=True)
class Resultado:
    recuperado: bool
    ingreso_atribuible: float
    costo_incentivo: float
