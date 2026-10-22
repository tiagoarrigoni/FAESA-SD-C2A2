import os
import time
import requests

URL_INGESTAO = "http://localhost:8001/indexar"
URL_GERACAO = "http://localhost:8003/perguntar"
PASTA_DOCS = "documentos"

def avaliar_cobertura(resposta: str, trechos_recuperados: list[str]) -> float:
    palavras_resposta = set(resposta.lower().split())
    texto_fontes = " ".join(trechos_recuperados).lower()
    palavras_fontes = set(texto_fontes.split())
    
    if not palavras_resposta:
        return 0.0
        
    intersecao = palavras_resposta.intersection(palavras_fontes)
    percentual = (len(intersecao) / len(palavras_resposta)) * 100
    return round(percentual, 2)

def indexar_documentos():
    print("=== Iniciando Ingestão de Documentos ===")
    if not os.path.exists(PASTA_DOCS):
        print(f"Erro: Pasta '{PASTA_DOCS}' não encontrada.")
        return

    for arquivo in os.listdir(PASTA_DOCS):
        caminho = os.path.join(PASTA_DOCS, arquivo)
        if os.path.isfile(caminho) and arquivo.endswith(".txt"):
            with open(caminho, 'r', encoding='utf-8') as f:
                texto = f.read()
                
            payload = {"texto": texto, "origem": arquivo}
            try:
                res = requests.post(URL_INGESTAO, json=payload)
                print(f"Enviado {arquivo}: Status {res.status_code}")
            except Exception as e:
                print(f"Erro ao enviar {arquivo}: {e}")

def fazer_perguntas():
    print("\n=== Iniciando Teste de Perguntas ===")
    perguntas = [
        "O que diz o teorema CAP?",
        "Quais são os desafios da consistência eventual?",
        "Como funciona a replicação em sistemas distribuídos?"
    ]

    for p in perguntas:
        print(f"\nPergunta: {p}")
        try:
            res = requests.post(URL_GERACAO, json={"pergunta": p})
            
            if res.status_code == 200:
                dados = res.json()
                resposta = dados.get("resposta", "")
                fontes = dados.get("fontes", [])
                
                textos_fontes = [f["texto"] for f in fontes if "texto" in f]
                cobertura = avaliar_cobertura(resposta, textos_fontes)
                
                print(f"Resposta: {resposta}")
                print(f"Cobertura Lexical: {cobertura}% das palavras estão nas fontes.")
                print(f"Fontes Utilizadas: {[f.get('origem') for f in fontes]}")
            else:
                print(f"Falha na geração (Status {res.status_code}): {res.text}")
        except Exception as e:
            print(f"Erro ao fazer pergunta: {e}")

if __name__ == "__main__":
    indexar_documentos()
    print("\nAguardando 3 segundos para o worker processar a fila Redis...")
    time.sleep(3)
    fazer_perguntas()