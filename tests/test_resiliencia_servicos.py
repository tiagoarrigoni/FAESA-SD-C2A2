"""Contratos HTTP reais em portas temporarias, sem Redis, LLM externo ou httpx."""
import importlib
import socket
import time
import unittest
from contextlib import ExitStack, contextmanager
from threading import Thread
from unittest.mock import patch

import requests
import uvicorn
from fastapi import FastAPI, HTTPException

from servicos.comum.http_resiliente import ClienteHTTPResiliente

geracao = importlib.import_module("servicos.geracao.app")
recuperacao = importlib.import_module("servicos.recuperacao.app")


@contextmanager
def servir(app):
    with socket.socket() as escuta:
        escuta.bind(("127.0.0.1", 0))
        porta = escuta.getsockname()[1]
        servidor = uvicorn.Server(uvicorn.Config(app, log_level="critical", access_log=False))
        thread = Thread(target=servidor.run, kwargs={"sockets": [escuta]}, daemon=True)
        thread.start()
        try:
            prazo = time.monotonic() + 5
            while not servidor.started:
                if not thread.is_alive() or time.monotonic() >= prazo:
                    raise RuntimeError("servidor de teste nao iniciou")
                time.sleep(0.01)
            yield f"http://127.0.0.1:{porta}"
        finally:
            servidor.should_exit = True
            thread.join(timeout=5)
            if thread.is_alive():
                raise RuntimeError("servidor de teste nao encerrou")


class TestResilienciaServicos(unittest.TestCase):
    def setUp(self):
        self.recursos = ExitStack()
        self.addCleanup(self.recursos.close)
        self.estado = {"status": 200, "chamadas": 0}
        ingestao_simulada = FastAPI()

        @ingestao_simulada.get("/indice")
        def indice():
            self.estado["chamadas"] += 1
            if self.estado["status"] != 200:
                raise HTTPException(self.estado["status"], "falha simulada")
            return {"total": 1, "itens": [{"texto": "CAP: consistencia e disponibilidade",
                                            "origem": "cap.txt", "vetor": []}]}

        self.ingestao_url = self.recursos.enter_context(servir(ingestao_simulada))
        self.recursos.enter_context(patch.object(recuperacao, "URL_INGESTAO", self.ingestao_url))
        self.recursos.enter_context(patch.object(
            recuperacao, "cliente_ingestao", ClienteHTTPResiliente("ingestao", backoff_segundos=0)
        ))
        self.recuperacao_url = self.recursos.enter_context(servir(recuperacao.app))
        self.recursos.enter_context(patch.object(geracao, "URL_RECUPERACAO", self.recuperacao_url))
        self.recursos.enter_context(patch.object(
            geracao, "cliente_recuperacao",
            ClienteHTTPResiliente("recuperacao", timeout=(1, 12), backoff_segundos=0)
        ))
        self.recursos.enter_context(patch("servicos.comum.llm.API_KEY", ""))
        self.geracao_url = self.recursos.enter_context(servir(geracao.app))

    def perguntar(self):
        return requests.post(f"{self.geracao_url}/perguntar", json={"pergunta": "CAP?"}, timeout=15)

    def buscar(self):
        return requests.post(f"{self.recuperacao_url}/buscar", json={"pergunta": "CAP?"}, timeout=10)

    def test_fluxo_normal_preserva_contexto_e_modo_simulado(self):
        resposta = self.perguntar()
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.json()["contexto"], ["CAP: consistencia e disponibilidade"])
        self.assertIn("MODO SIMULADO", resposta.json()["resposta"])
        self.assertEqual(self.estado["chamadas"], 1)

    def test_ingestao_falha_503_abre_e_volta_apos_sondagem(self):
        self.estado["status"] = 503
        for _ in range(3):
            resposta = self.buscar()
            self.assertEqual(resposta.status_code, 503)
            self.assertIn("ingestao indisponivel", resposta.json()["detail"])
        self.assertEqual(self.estado["chamadas"], 9)
        self.assertEqual(recuperacao.cliente_ingestao.disjuntor.estado, "aberto")
        self.assertEqual(self.buscar().status_code, 503)
        self.assertEqual(self.estado["chamadas"], 9)
        # Avanca so o instante de abertura; nao espera 20 segundos no teste.
        self.estado["status"] = 200
        recuperacao.cliente_ingestao.disjuntor.aberto_em -= 21
        self.assertEqual(self.buscar().status_code, 200)
        self.assertEqual(recuperacao.cliente_ingestao.disjuntor.estado, "fechado")

    def test_falha_da_ingestao_propaga_503_na_geracao_sem_chamar_llm(self):
        self.estado["status"] = 503
        with patch.object(geracao, "gerar") as llm:
            resposta = self.perguntar()
        self.assertEqual(resposta.status_code, 503)
        self.assertIn("recuperacao indisponivel", resposta.json()["detail"])
        llm.assert_not_called()
        self.assertEqual(self.estado["chamadas"], 9)
        self.assertEqual(geracao.disjuntor.estado, "fechado")

    def test_ingestao_fora_503_em_ambas_apis(self):
        with socket.socket() as indisponivel:
            indisponivel.bind(("127.0.0.1", 0))
            porta = indisponivel.getsockname()[1]
            recuperacao.cliente_ingestao.timeout = (0.05, 0.1)
            with patch.object(recuperacao, "URL_INGESTAO", f"http://127.0.0.1:{porta}"):
                self.assertEqual(self.buscar().status_code, 503)
                self.assertEqual(self.perguntar().status_code, 503)

    def test_recuperacao_fora_503_circuito_independente_e_retorno(self):
        # Porta reservada, sem servidor: recusa real de conexao.
        with socket.socket() as indisponivel:
            indisponivel.bind(("127.0.0.1", 0))
            porta = indisponivel.getsockname()[1]
            with patch.object(geracao, "URL_RECUPERACAO", f"http://127.0.0.1:{porta}"), \
                    patch.object(geracao, "gerar") as llm:
                # Timeout curto mantem a recusa rapida tambem no Windows.
                geracao.cliente_recuperacao.timeout = (0.05, 0.1)
                for _ in range(4):
                    resposta = self.perguntar()
                    self.assertEqual(resposta.status_code, 503)
                    self.assertIn("recuperacao indisponivel", resposta.json()["detail"])
                llm.assert_not_called()
        self.assertEqual(geracao.cliente_recuperacao.disjuntor.estado, "aberto")
        self.assertEqual(geracao.disjuntor.estado, "fechado")
        self.assertEqual(recuperacao.cliente_ingestao.disjuntor.estado, "fechado")
        geracao.cliente_recuperacao.timeout = (1, 12)
        geracao.cliente_recuperacao.disjuntor.aberto_em -= 21
        self.assertEqual(self.perguntar().status_code, 200)
        self.assertEqual(geracao.cliente_recuperacao.disjuntor.estado, "fechado")


if __name__ == "__main__":
    unittest.main()
