import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

import demo


class TestDemo(unittest.TestCase):
    @patch("demo.time.sleep")
    @patch("demo.requests.get")
    def test_aguarda_processamento_antes_de_considerar_pronto(self, requisicao, pausa):
        requisicao.side_effect = [Mock(json=lambda: {"status": "processando"}),
                                 Mock(json=lambda: {"status": "pronto"})]
        demo.aguardar_indexacao("tarefa-1")
        self.assertEqual(requisicao.call_count, 2)
        requisicao.assert_called_with(f"{demo.URL_INGESTAO}/indexacao/tarefa-1", timeout=demo.TIMEOUT_HTTP)
        self.assertEqual(pausa.call_count, 1)

    @patch("demo.requests.post")
    @patch("demo.requests.get")
    def test_payload_e_lista_e_falha_do_worker_interrompe(self, consultar, enviar):
        enviar.return_value = Mock(status_code=202, json=lambda: {"id": "tarefa-1"})
        consultar.return_value = Mock(json=lambda: {"status": "falhou"})
        with tempfile.TemporaryDirectory() as pasta, patch("sys.stdout", new_callable=io.StringIO):
            (Path(pasta) / "cap.txt").write_text("Teorema CAP", encoding="utf-8")
            with patch.object(demo, "PASTA_DOCS", Path(pasta)):
                self.assertFalse(demo.indexar_documentos())
        self.assertEqual(enviar.call_args.kwargs["json"], [{"texto": "Teorema CAP", "origem": "cap.txt"}])

    @patch("demo.requests.post")
    def test_fontes_sao_nomes_e_cobertura_usa_contexto(self, requisicao):
        requisicao.return_value = Mock(json=lambda: {"resposta": "teorema CAP",
            "contexto": ["teorema CAP"], "fontes": ["cap.txt"], "degradado": False})
        with patch("sys.stdout", new_callable=io.StringIO) as saida:
            self.assertTrue(demo.fazer_perguntas())
        self.assertIn("100.0%", saida.getvalue())
        self.assertIn("cap.txt", saida.getvalue())

    @patch("demo.time.monotonic", side_effect=[0, 61])
    @patch("demo.requests.get")
    def test_indexacao_tem_limite_de_espera(self, requisicao, relogio):
        with self.assertRaises(TimeoutError):
            demo.aguardar_indexacao("lenta", limite_segundos=60)
        requisicao.assert_not_called()

    @patch("demo.fazer_perguntas")
    @patch("demo.indexar_documentos", return_value=False)
    def test_main_nao_pergunta_quando_indexacao_falha(self, indexar, perguntar):
        with patch("sys.stdout", new_callable=io.StringIO):
            self.assertEqual(demo.main(), 1)
        perguntar.assert_not_called()


if __name__ == "__main__":
    unittest.main()
