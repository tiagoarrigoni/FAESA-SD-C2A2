import json
import os
import tempfile
import unittest

from servicos.ingestao import armazenamento


class TestArmazenamento(unittest.TestCase):
    def setUp(self):
        self.diretorio = tempfile.TemporaryDirectory()
        self.caminho_original = armazenamento.CAMINHO_INDICE

        armazenamento.CAMINHO_INDICE = os.path.join(
            self.diretorio.name, "indice.json"
        )

    def tearDown(self):
        armazenamento.CAMINHO_INDICE = self.caminho_original
        self.diretorio.cleanup()

    def test_indice_inexistente_retorna_lista_vazia(self):
        self.assertEqual(armazenamento.carregar(), [])

    def test_salvar_e_carregar_preserva_documentos_e_origens(self):
        documentos = [
            {
                "texto": "O teorema CAP trata de consistencia.",
                "origem": "aula11",
                "vetor": [0.5, 0.8],
            },
            {
                "texto": "Disponibilidade e uma propriedade do sistema.",
                "origem": "aula12",
                "vetor": [0.3, 0.7],
            },
        ]

        armazenamento.salvar(documentos)

        self.assertEqual(armazenamento.carregar(), documentos)

    def test_json_invalido_gera_erro_claro(self):
        with open(
            armazenamento.CAMINHO_INDICE, "w", encoding="utf-8"
        ) as arquivo:
            arquivo.write("{json invalido")

        with self.assertRaisesRegex(ValueError, "JSON invalido"):
            armazenamento.carregar()

    def test_estrutura_invalida_gera_erro_claro(self):
        with open(
            armazenamento.CAMINHO_INDICE, "w", encoding="utf-8"
        ) as arquivo:
            json.dump({"documento": "teste"}, arquivo)

        with self.assertRaisesRegex(ValueError, "lista de documentos"):
            armazenamento.carregar()


if __name__ == "__main__":
    unittest.main()
