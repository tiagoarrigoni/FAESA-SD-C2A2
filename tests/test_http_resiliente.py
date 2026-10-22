import unittest
from unittest.mock import Mock, call, patch

import requests

from servicos.comum.http_resiliente import ClienteHTTPResiliente, ServicoIndisponivel


def resposta_http(status=200, dados=None):
    resposta = Mock(status_code=status)
    resposta.json.return_value = {"itens": []} if dados is None else dados
    if status >= 400:
        resposta.raise_for_status.side_effect = requests.HTTPError(response=resposta)
    return resposta


class TestHTTPResiliente(unittest.TestCase):
    def setUp(self):
        self.cliente = ClienteHTTPResiliente("ingestao")
        self.pausa = patch("servicos.comum.http_resiliente.time.sleep").start()
        self.addCleanup(patch.stopall)

    def consultar(self):
        return self.cliente.solicitar_json("GET", "http://ingestao/indice", campo_lista="itens")

    @patch("servicos.comum.http_resiliente.requests.get")
    def test_sucesso_aplica_timeout_e_fecha_resposta(self, requisicao):
        resposta = resposta_http()
        requisicao.return_value = resposta
        self.assertEqual(self.consultar(), {"itens": []})
        requisicao.assert_called_once_with("http://ingestao/indice", timeout=(1, 2))
        resposta.close.assert_called_once()
        self.pausa.assert_not_called()

    @patch("servicos.comum.http_resiliente.requests.get")
    def test_falha_transitoria_recupera_com_backoff_exponencial(self, requisicao):
        requisicao.side_effect = [requests.ConnectionError(), requests.Timeout(), resposta_http()]
        self.assertEqual(self.consultar(), {"itens": []})
        self.assertEqual(requisicao.call_count, 3)
        self.assertEqual(self.pausa.call_args_list, [call(0.2), call(0.4)])
        self.assertEqual(self.cliente.disjuntor.falhas, 0)

    def test_status_transitorios_sao_repetidos(self):
        for status in (429, 500, 502, 503, 504):
            with self.subTest(status=status), patch(
                "servicos.comum.http_resiliente.requests.get"
            ) as requisicao:
                resposta = resposta_http(status)
                requisicao.side_effect = [resposta, resposta_http()]
                self.assertEqual(self.consultar(), {"itens": []})
                self.assertEqual(requisicao.call_count, 2)
                resposta.close.assert_called_once()

    @patch("servicos.comum.http_resiliente.requests.get")
    def test_erro_400_nao_e_repetido(self, requisicao):
        requisicao.return_value = resposta_http(400)
        with self.assertRaises(ServicoIndisponivel):
            self.consultar()
        requisicao.assert_called_once()
        self.pausa.assert_not_called()

    @patch("servicos.comum.http_resiliente.requests.get")
    def test_esgotamento_conta_uma_falha_por_consulta_e_abre(self, requisicao):
        requisicao.side_effect = requests.Timeout()
        for falhas in (1, 2, 3):
            with self.assertRaisesRegex(ServicoIndisponivel, "ingestao indisponivel"):
                self.consultar()
            self.assertEqual(self.cliente.disjuntor.falhas, falhas)
        self.assertEqual(requisicao.call_count, 9)
        self.assertEqual(self.cliente.disjuntor.estado, "aberto")
        self.pausa.reset_mock()
        with self.assertRaises(ServicoIndisponivel):
            self.consultar()
        self.assertEqual(requisicao.call_count, 9)
        self.pausa.assert_not_called()

    @patch("servicos.comum.http_resiliente.requests.get")
    def test_json_invalido_vira_indisponibilidade_sem_retry(self, requisicao):
        resposta = resposta_http()
        resposta.json.side_effect = ValueError("JSON invalido")
        requisicao.return_value = resposta
        with self.assertRaises(ServicoIndisponivel):
            self.consultar()
        requisicao.assert_called_once()
        resposta.close.assert_called_once()

    def test_resposta_fora_do_contrato_vira_indisponibilidade(self):
        for dados in ([], {"outro": []}, {"itens": {}}, {"itens": [None]},
                      {"itens": [{"texto": "ok"}]}):
            with self.subTest(dados=dados), patch(
                "servicos.comum.http_resiliente.requests.get", return_value=resposta_http(dados=dados)
            ):
                self.cliente = ClienteHTTPResiliente("ingestao")
                with self.assertRaises(ServicoIndisponivel):
                    self.consultar()

    @patch("servicos.comum.http_resiliente.requests.post")
    def test_post_preserva_corpo_da_consulta(self, requisicao):
        requisicao.return_value = resposta_http(dados={"resultados": []})
        cliente = ClienteHTTPResiliente("recuperacao", timeout=(1, 12))
        corpo = {"pergunta": "CAP?", "top_k": 3}
        cliente.solicitar_json("POST", "http://recuperacao/buscar", campo_lista="resultados", json=corpo)
        requisicao.assert_called_once_with("http://recuperacao/buscar", timeout=(1, 12), json=corpo)


if __name__ == "__main__":
    unittest.main()
