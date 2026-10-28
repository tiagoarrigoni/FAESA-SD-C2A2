# FAESA - Sistemas Distribuídos (C2.A2)
## Sistema RAG Distribuído com Microsserviços, Mensageria e Resiliência

Este repositório contém a implementação do trabalho C2.A2 da disciplina de **Sistemas Distribuídos** da FAESA. O projeto consiste em uma arquitetura de **Geração Aumentada por Recuperação (RAG)** construída em microsserviços desacoplados, orientada a eventos com mensageria assíncrona via Redis, mecanismos de resiliência e validação ponta a ponta.

---

## Arquitetura e Fluxo de Dados

```mermaid
flowchart TD
    subgraph Cliente [" Cliente / Demonstração"]
        A[demo.py]
    end

    subgraph Ingestao [" Serviço de Ingestão (Porta 8001)"]
        B[API /indexar]
    end

    subgraph Mensageria [" Fila de Mensagens"]
        C[(Redis Queue)]
    end

    subgraph WorkerService ["Processamento Assíncrono"]
        D[Worker de Ingestão]
    end

    subgraph Armazenamento ["Persistência Vetorial"]
        G[(dados/indice.json)]
    end

    subgraph Recuperacao ["Serviço de Recuperação (Porta 8002)"]
        E[API /buscar]
    end

    subgraph Geracao [" Serviço de Geração (Porta 8003)"]
        F[API /perguntar]
    end

    A -->|1. POST /indexar| B
    B -->|2. Enfileira Tarefa| C
    B -.->|Devolve 202 Accepted| A
    C -->|3. Consome Tarefa| D
    D -->|4. Vetoriza & Grava| G
    A -->|5. POST /perguntar| F
    F -->|6. Busca Contexto (Circuit Breaker)| E
    E -->|7. Consulta Índice| G
    E -->|8. Retorna Trechos| F
    F -->|9. Resposta + Fontes| A
```

---

## Estrutura do Projeto

```text
FAESA-SD-C2A2/
├── servicos/
│   ├── ingestao/       # API 8001, armazenamento.py e worker.py (Fila Redis)
│   ├── recuperacao/    # API 8002 e logica de similaridade
│   └── geracao/        # API 8003 e integracao com LLM via Circuit Breaker
├── documentos/         # Arquivos .txt base para ingestao
├── dados/              # Volume persistente do indice.json compartilhado
├── tests/              # Testes unitarios e de integracao
├── docker-compose.yml  # Orquestracao completa (Servicos, Worker, Redis)
├── Dockerfile          # Configuracao de imagem por microsservico
├── demo.py             # Script de validacao ponta a ponta com metrica
└── README.md
```

---

##  Divisão de Tarefas e Integrantes

### 1. Tiago – Mensageria + Integração
* Criar o repo a partir do kit, convidar todos e definir os contratos.
* `POST /indexar` publica os documentos na fila Redis, e um worker de ingestão consome, vetoriza e salva (com retry + dead-letter).
* Revisar e aprovar os PRs, e integrar tudo na `main`.

### 2. Luis Felipe – Docker
* Um Dockerfile por serviço (ingestão, recuperação, geração, worker).
* `docker-compose` completo: Redis, os 3 serviços, worker com 2 réplicas, healthchecks, `depends_on`, volume para o índice e `.env`.

### 3. Eliã – Ingestão (Tarefa 1)
* Persistir o índice em disco (JSON no volume ou ChromaDB), para que ele não suma ao reiniciar.
* Corrigir o bug do `INDICE.clear()`, que apaga os documentos antigos a cada `/indexar`.
* Guardar e devolver a "origem" de cada documento (para citar as fontes).

### 4. Lucas – Recuperação (Tarefa 2)
* Implementar o `/buscar`: pegar o `/indice` da ingestão, vetorizar a pergunta, calcular `similaridade()` e devolver os `top_k` com score.

### 5. Daniel – Resiliência do LLM (Tarefa 3)
* Envolver o `gerar()` com o circuit breaker (`disjuntor.chamar`).
* Retentativa com backoff (3 tentativas) + tempo-limite.
* Circuito aberto devolve 503 com mensagem clara, e se o LLM falhar o sistema responde de forma degradada, sem quebrar.

### 6. Vinicius – Resiliência entre serviços + testes de falha
* Timeout + retentativa + disjuntor nas chamadas REST internas (geração → recuperação e recuperação → ingestão).
* Se um serviço estiver fora, devolver erro claro (503), sem estourar 500.
* Roteiro/script de testes de falha: simular quedas de containers.

### 7. Davi – Fluxo ponta a ponta + README
* Script de demonstração (`demo.py`): indexa os arquivos validando status do worker e faz perguntas extraindo fontes e métricas via campo `contexto`.
* Avaliação automática simples (Cobertura Lexical).
* Diagrama da arquitetura e README consolidado.

---

##  Como Executar do Zero (Passo a Passo)

**Pré-requisitos:** Docker, Docker Compose e Python 3.10+ instalados.

### 1. Clonar o Repositório do Grupo
```bash
git clone https://github.com/tiagoarrigoni/FAESA-SD-C2A2.git
cd FAESA-SD-C2A2
```

### 2. Subir a Infraestrutura
```bash
docker compose up --build -d
```
*Isto irá compilar as imagens e iniciar o Redis, o Worker e os 3 microsserviços. Verifique com `docker compose ps` se todos estão ativos.*

### 3. Preparar o Ambiente e Rodar a Demonstração
No seu terminal local (fora do Docker), crie um ambiente virtual para não gerar conflitos:
```bash
python -m venv .venv

# Windows:
.venv\Scripts\activate
# Linux/Mac:
source .venv/bin/activate

# Instale os requisitos e rode o fluxo RAG completo:
pip install requests
python demo.py
```

---

##  Resiliência e Testes de Falha

1. **Teste de Queda da Recuperação (`docker compose stop recuperacao`):** O Serviço de Geração orquestrará a falha via Circuit Breaker e retornará HTTP `503` graciosamente.
2. **Teste de Queda do Redis (`docker compose stop redis`):** O Serviço de Ingestão alertará sobre a indisponibilidade da fila (HTTP `503`), impedindo o enfileiramento cego de requisições.