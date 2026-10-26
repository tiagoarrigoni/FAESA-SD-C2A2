"""
Circuit breaker de referencia - Aula 13.

Compartilhado pelo LLM e pelas chamadas HTTP internas, com uma instancia
independente para cada dependencia.

Estados:
  fechado  -> deixa passar (normal)
  aberto   -> recusa na hora, sem tentar (servico esta quebrado)
  meio     -> deixa passar UMA chamada de teste para ver se voltou
"""
import time
from threading import Lock


class CircuitoAberto(Exception):
    """Levantada quando o disjuntor esta aberto e recusa a chamada."""


class CircuitBreaker:

    def __init__(self, limite_falhas=5, espera_segundos=30):
        if limite_falhas < 1 or espera_segundos < 0:
            raise ValueError("limite_falhas deve ser positivo e espera nao negativa")
        self.limite_falhas = limite_falhas
        self.espera_segundos = espera_segundos
        self.falhas = 0
        self.estado = "fechado"
        self.aberto_em = 0.0
        self._trava = Lock()
        self._geracao = 0

    def chamar(self, funcao, *args, **kwargs):
        with self._trava:
            if self.estado == "aberto":
                if time.monotonic() - self.aberto_em >= self.espera_segundos:
                    self.estado = "meio"
                    self._geracao += 1
                else:
                    raise CircuitoAberto("disjuntor aberto: chamada recusada")
            elif self.estado == "meio":
                raise CircuitoAberto("disjuntor em teste: chamada recusada")
            geracao = self._geracao
        try:
            resultado = funcao(*args, **kwargs)
        except Exception:
            with self._trava:
                if geracao == self._geracao:
                    self._registrar_falha()
            raise
        with self._trava:
            # Uma resposta antiga nao pode fechar um circuito recem-aberto.
            if geracao == self._geracao:
                self._registrar_sucesso()
        return resultado

    def _registrar_falha(self):
        self.falhas += 1
        if self.falhas >= self.limite_falhas or self.estado == "meio":
            self.estado = "aberto"
            self.aberto_em = time.monotonic()
            self._geracao += 1

    def _registrar_sucesso(self):
        if self.estado == "meio":
            self._geracao += 1
        self.falhas = 0
        self.estado = "fechado"
