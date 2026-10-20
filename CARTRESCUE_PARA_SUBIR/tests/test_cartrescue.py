import tempfile
import unittest
from pathlib import Path

from cartrescue.agent import AgenteRescateCarritos
from cartrescue.simulation import Experimento, escenarios_predeterminados


class PruebasRescateCarritos(unittest.TestCase):
    def test_bloquea_contacto_sin_consentimiento(self):
        escenario = next(item for item in escenarios_predeterminados() if item.nombre == "sin_consentimiento")
        decision = AgenteRescateCarritos().decidir(escenario.contexto)
        self.assertEqual((decision.accion, decision.motivo), ("ninguna", "sin_consentimiento"))

    def test_bloquea_limite_de_frecuencia(self):
        escenario = next(item for item in escenarios_predeterminados() if item.nombre == "limite_contactos")
        self.assertEqual(AgenteRescateCarritos().decidir(escenario.contexto).motivo, "limite_frecuencia")

    def test_la_corrida_con_semilla_es_reproducible(self):
        def ejecutar():
            experimento = Experimento(semilla=20261019)
            experimento.ejecutar(escenarios_predeterminados(), repeticiones=5)
            return experimento.resumen()["metricas"]
        self.assertEqual(ejecutar(), ejecutar())

    def test_la_evidencia_tiene_eventos_con_marca_tiempo_y_umbrales(self):
        experimento = Experimento(semilla=20261019)
        experimento.ejecutar(escenarios_predeterminados(), repeticiones=5)
        with tempfile.TemporaryDirectory() as directorio_temporal:
            resumen = experimento.escribir_evidencia(Path(directorio_temporal))
            self.assertTrue((Path(directorio_temporal) / "eventos.ndjson").exists())
            self.assertEqual(len(experimento.registros), 60)  # 12 escenarios x 5 repeticiones
            self.assertGreaterEqual(resumen["metricas"]["tasa_recuperacion"], .15)
            self.assertEqual(resumen["metricas"]["cumplimiento_politica"], 1.0)


if __name__ == "__main__":
    unittest.main()
