"""Timeout, retentativa e circuito por dependencia HTTP interna."""
import time

import requests

from servicos.comum.circuit_breaker import CircuitBreaker, CircuitoAberto
from servicos.comum.logging_utils import configurar_log

log = configurar_log("http_resiliente")
STATUS_TRANSITORIOS = {429, 500, 502, 503, 504}


class ServicoIndisponivel(Exception):
    """Falha de dependencia que a API deve apresentar como HTTP 503."""


class ClienteHTTPResiliente:
    def __init__(self, servico, timeout=(1, 2), tentativas=3,
                 backoff_segundos=0.2, limite_falhas=3, espera_segundos=20):
        if tentativas < 1 or backoff_segundos < 0:
            raise ValueError("tentativas deve ser positivo e backoff nao negativo")
        self.servico = servico
        self.timeout = timeout
        self.tentativas = tentativas
        self.backoff_segundos = backoff_segundos
        self.disjuntor = CircuitBreaker(limite_falhas, espera_segundos)

    def solicitar_json(self, metodo, url, *, campo_lista, **kwargs):
        """Somente GET e POST de consulta, seguros para repetir (ex.: /buscar)."""
        metodo = metodo.upper()
        if metodo not in {"GET", "POST"}:
            raise ValueError("metodo nao suportado")
        try:
            return self.disjuntor.chamar(
                self._consultar, metodo, url, campo_lista, kwargs
            )
        except (CircuitoAberto, requests.RequestException, ValueError) as erro:
            # Nao registra pergunta, documentos, credenciais ou corpo da resposta.
            log.warning("servico=%s | falha=%s | circuito=%s",
                        self.servico, type(erro).__name__, self.disjuntor.estado)
            raise ServicoIndisponivel(
                f"{self.servico} indisponivel, tente novamente em instantes"
            ) from erro

    def _consultar(self, metodo, url, campo_lista, kwargs):
        for tentativa in range(1, self.tentativas + 1):
            resposta = None
            try:
                # get/post preservam os pontos de simulacao dos testes existentes.
                resposta = getattr(requests, metodo.lower())(
                    url, timeout=self.timeout, **kwargs
                )
                resposta.raise_for_status()
                dados = resposta.json()
                if not isinstance(dados, dict) or not isinstance(dados.get(campo_lista), list):
                    raise ValueError("resposta fora do contrato: lista ausente")
                if any(not isinstance(item, dict)
                       or not isinstance(item.get("texto"), str)
                       or not isinstance(item.get("origem"), str)
                       for item in dados[campo_lista]):
                    raise ValueError("resposta fora do contrato: documento invalido")
                return dados
            except requests.HTTPError:
                if resposta.status_code not in STATUS_TRANSITORIOS:
                    raise
                if tentativa == self.tentativas:
                    raise
            except (requests.Timeout, requests.ConnectionError):
                if tentativa == self.tentativas:
                    raise
            finally:
                if resposta is not None:
                    resposta.close()

            espera = self.backoff_segundos * (2 ** (tentativa - 1))
            log.warning("servico=%s | tentativa=%s/%s | backoff_s=%.2f",
                        self.servico, tentativa, self.tentativas, espera)
            time.sleep(espera)
