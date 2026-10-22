
import unittest
from unittest.mock import patch, Mock

from servicos.recuperacao.app import buscar, Consulta


class TestRecuperacao(unittest.TestCase):

    def setUp(self):
        # Documentos simulados da ingestao
        self.documentos = [
            {
                "texto": "O teorema CAP aborda consistencia, disponibilidade e tolerancia a particoes em sistemas distribuidos.",
                "origem": "cap.txt",
                "vetor": []
            },
            {
                "texto": "Docker permite executar aplicacoes em containers.",
                "origem": "docker.txt",
                "vetor": []
            },
            {
                "texto": "Redes de computadores permitem a comunicacao entre dispositivos.",
                "origem": "redes.txt",
                "vetor": []
            }
        ]

    @patch("servicos.recuperacao.app.requests.get")
    def test_documento_cap_em_primeiro(self, mock_get):
        resposta = Mock()
        resposta.json.return_value = {
            "itens": self.documentos
        }
        mock_get.return_value = resposta

        consulta = Consulta(
            pergunta="O que diz o teorema CAP?",
            top_k=3
        )

        resultado = buscar(consulta)

        self.assertEqual(
            resultado["resultados"][0]["origem"],
            "cap.txt"
        )

    @patch("servicos.recuperacao.app.requests.get")
    def test_respeita_top_k(self, mock_get):
        resposta = Mock()
        resposta.json.return_value = {
            "itens": self.documentos
        }
        mock_get.return_value = resposta

        consulta = Consulta(
            pergunta="O que diz o teorema CAP?",
            top_k=2
        )

        resultado = buscar(consulta)

        self.assertEqual(
            len(resultado["resultados"]), 2
        )

    @patch("servicos.recuperacao.app.requests.get")
    def test_indice_vazio(self, mock_get):
        resposta = Mock()
        resposta.json.return_value = {
            "itens": []
        }
        mock_get.return_value = resposta

        consulta = Consulta(
            pergunta="O que e o teorema CAP?"
        )

        resultado = buscar(consulta)

        self.assertEqual(resultado["resultados"], [])


    @patch("servicos.recuperacao.app.requests.get")
    def test_resultados_ordenados_por_score(self, mock_get):
        resposta = Mock()
        resposta.json.return_value = {
            "itens": self.documentos
        }
        mock_get.return_value = resposta

        consulta = Consulta(
            pergunta="O que diz o teorema CAP?",
            top_k=3
        )

        resultado = buscar(consulta)

        resultados = resultado["resultados"]
        scores = [item["score"] for item in resultados]

        self.assertEqual(
            scores,
            sorted(scores, reverse=True)
        )


    @patch("servicos.recuperacao.app.requests.get")
    def test_pergunta_sem_palavras_em_comum(self, mock_get):
        resposta = Mock()
        resposta.json.return_value = {
            "itens": self.documentos
        }
        mock_get.return_value = resposta

        consulta = Consulta(
            pergunta="fotossintese clorofila vegetacao",
            top_k=3
        )

        resultado = buscar(consulta)

        self.assertEqual(
            len(resultado["resultados"]), 3
        )

        for item in resultado["resultados"]:
            self.assertAlmostEqual(item["score"], 0.0)


if __name__ == "__main__":
    unittest.main()


