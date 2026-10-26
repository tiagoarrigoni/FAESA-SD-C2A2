import os
import time
import requests
import re

# Configurações de URL e Diretórios
URL_INGESTAO = "http://localhost:8001/indexar"
URL_GERACAO = "http://localhost:8003/perguntar"
PASTA_DOCUMENTOS = "documentos"

def calcular_cobertura_lexical(resposta, trechos_recuperados):
    """Calcula a porcentagem de palavras da resposta presentes nos trechos (fontes)."""
    if not trechos_recuperados or not resposta:
        return 0.0

    # Normaliza e extrai palavras (minúsculas, sem pontuação)
    palavras_resposta = set(re.findall(r'\b\w+\b', resposta.lower()))
    texto_fontes = " ".join(trechos_recuperados).lower()
    palavras_fontes = set(re.findall(r'\b\w+\b', texto_fontes))
    
    if not palavras_resposta:
        return 0.0

    # Interseção: palavras que estão na resposta E nas fontes
    intersecao = palavras_resposta.intersection(palavras_fontes)
    cobertura = (len(intersecao) / len(palavras_resposta)) * 100
    
    return round(cobertura, 2)

def executar_demonstracao():
    print("="*70)
    print("INICIANDO INGESTÃO AUTOMÁTICA DE DOCUMENTOS")
    print("="*70)

    # 1. Fase de Ingestão
    if not os.path.exists(PASTA_DOCUMENTOS):
        print(f" Erro: A pasta '{PASTA_DOCUMENTOS}' não existe neste diretório.")
        return

    arquivos = [f for f in os.listdir(PASTA_DOCUMENTOS) if f.endswith(".txt")]
    if not arquivos:
        print(f" Nenhum arquivo .txt encontrado na pasta '{PASTA_DOCUMENTOS}'.")
        return

    for arquivo in arquivos:
        caminho = os.path.join(PASTA_DOCUMENTOS, arquivo)
        with open(caminho, 'r', encoding='utf-8') as f:
            conteudo = f.read()

        # CORREÇÃO CRÍTICA: O contrato exige uma LISTA de objetos (array JSON)
        payload = [
            {
                "texto": conteudo,
                "origem": arquivo
            }
        ]
        
        try:
            resposta = requests.post(URL_INGESTAO, json=payload)
            if resposta.status_code in [200, 202]:
                print(f" Sucesso ao enviar {arquivo}: Status {resposta.status_code}")
            else:
                print(f"❌ Falha ao enviar {arquivo}: Status {resposta.status_code} - {resposta.text}")
        except Exception as e:
            print(f" Erro de conexão ao tentar acessar a Ingestão (8001): {e}")

    # 2. Aguarda o Worker e o Redis processarem os documentos
    print("\n Aguardando 8 segundos para o Worker processar a fila do Redis...")
    time.sleep(8)

    # 3. Fase de Perguntas (RAG)
    print("\n" + "="*70)
    print("EXECUÇÃO DAS PERGUNTAS DE DEMONSTRAÇÃO (RAG)")
    print("="*70 + "\n")

    perguntas = [
        "O que diz o teorema CAP?",
        "Quais são os desafios da consistência eventual?",
        "Como funciona a replicação em sistemas distribuídos?"
    ]

    for i, pergunta in enumerate(perguntas, 1):
        print(f"[Pergunta {i}]: {pergunta}")
        
        payload_pergunta = {"pergunta": pergunta}
        
        try:
            resposta = requests.post(URL_GERACAO, json=payload_pergunta)
            
            if resposta.status_code == 200:
                dados = resposta.json()
                texto_resposta = dados.get("resposta", "")
                fontes = dados.get("fontes", [])
                
                # Extrair apenas os textos das fontes para a métrica
                trechos_textuais = [f.get("texto", "") if isinstance(f, dict) else str(f) for f in fontes]
                cobertura = calcular_cobertura_lexical(texto_resposta, trechos_textuais)
                
                print(f"Resposta:\n  {texto_resposta.strip()}")
                print(f"\nCom base nos documentos recuperados:")
                print(f"Fontes Recuperadas: {len(fontes)} trecho(s)")
                
                # Tenta exibir de quais arquivos a resposta veio
                origens = list(set([f.get("origem", "Desconhecida") for f in fontes if isinstance(f, dict) and "origem" in f]))
                if origens:
                    print(f"Arquivos citados: {', '.join(origens)}")
                    
                print(f"Métrica - Cobertura Lexical Resposta/Fonte: {cobertura}%\n")
                print("-" * 70 + "\n")
            else:
                print(f" Falha na geração: Status {resposta.status_code} - {resposta.text}\n")
        except Exception as e:
            print(f"  Erro de conexão ao tentar acessar a Geração (8003): {e}\n")

if __name__ == "__main__":
    executar_demonstracao()