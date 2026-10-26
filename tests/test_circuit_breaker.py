import unittest
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from unittest.mock import Mock, patch

from servicos.comum.circuit_breaker import CircuitBreaker, CircuitoAberto


class TestCircuitBreaker(unittest.TestCase):
    def test_retorna_resultado_e_sucesso_zera_falhas(self):
        circuito = CircuitBreaker(limite_falhas=2)
        with self.assertRaises(OSError):
            circuito.chamar(Mock(side_effect=OSError))
        self.assertEqual(circuito.falhas, 1)
        self.assertEqual(circuito.chamar(lambda: 42), 42)
        self.assertEqual((circuito.estado, circuito.falhas), ("fechado", 0))

    @patch("servicos.comum.circuit_breaker.time.monotonic")
    def test_abre_recusa_sem_executar_e_recupera(self, relogio):
        relogio.return_value = 100
        circuito = CircuitBreaker(limite_falhas=2, espera_segundos=20)
        falha = Mock(side_effect=OSError)
        for _ in range(2):
            with self.assertRaises(OSError):
                circuito.chamar(falha)
        self.assertEqual(circuito.estado, "aberto")
        relogio.return_value = 119
        with self.assertRaises(CircuitoAberto):
            circuito.chamar(falha)
        self.assertEqual(falha.call_count, 2)
        relogio.return_value = 120
        self.assertEqual(circuito.chamar(lambda: "voltou"), "voltou")
        self.assertEqual((circuito.estado, circuito.falhas), ("fechado", 0))

    @patch("servicos.comum.circuit_breaker.time.monotonic")
    def test_falha_no_meio_reabre_e_reinicia_espera(self, relogio):
        relogio.return_value = 100
        circuito = CircuitBreaker(limite_falhas=1, espera_segundos=20)
        for instante in (100, 120):
            relogio.return_value = instante
            with self.assertRaises(OSError):
                circuito.chamar(Mock(side_effect=OSError))
        self.assertEqual((circuito.estado, circuito.aberto_em), ("aberto", 120))
        relogio.return_value = 139
        with self.assertRaises(CircuitoAberto):
            circuito.chamar(lambda: None)

    def test_meio_admite_somente_uma_sondagem_simultanea(self):
        circuito = CircuitBreaker(limite_falhas=1, espera_segundos=0)
        with self.assertRaises(OSError):
            circuito.chamar(Mock(side_effect=OSError))
        iniciou, liberar = Event(), Event()

        def sondar():
            iniciou.set()
            if not liberar.wait(3):
                raise TimeoutError("teste nao liberou sondagem")
            return "ok"

        with ThreadPoolExecutor(max_workers=1) as executor:
            futuro = executor.submit(circuito.chamar, sondar)
            try:
                self.assertTrue(iniciou.wait(3))
                self.assertEqual(circuito.estado, "meio")
                outra = Mock()
                with self.assertRaises(CircuitoAberto):
                    circuito.chamar(outra)
                outra.assert_not_called()
            finally:
                liberar.set()
            self.assertEqual(futuro.result(timeout=3), "ok")
        self.assertEqual(circuito.estado, "fechado")

    def test_sucesso_antigo_nao_fecha_circuito_aberto_por_outra_chamada(self):
        circuito = CircuitBreaker(limite_falhas=1)
        iniciou, liberar = Event(), Event()

        def chamada_lenta():
            iniciou.set()
            if not liberar.wait(3):
                raise TimeoutError("teste nao liberou chamada")
            return "ok"

        with ThreadPoolExecutor(max_workers=1) as executor:
            futuro = executor.submit(circuito.chamar, chamada_lenta)
            try:
                self.assertTrue(iniciou.wait(3))
                with self.assertRaises(OSError):
                    circuito.chamar(Mock(side_effect=OSError))
            finally:
                liberar.set()
            self.assertEqual(futuro.result(timeout=3), "ok")
        self.assertEqual(circuito.estado, "aberto")


if __name__ == "__main__":
    unittest.main()
