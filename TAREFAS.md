# TAREFAS - Trabalho C2.A2 (RAG Distribuido)

Entrega: **qui 29/10/2026** (Aula 12). PR de cada um ate **sab 24/10, 23h59**.
Contratos entre os servicos: [docs/CONTRATOS.md](docs/CONTRATOS.md).
Cada um trabalha na branch `feat/<seu-nome>` e abre PR para a `main`.

## Nucleo obrigatorio

- [x] **1. Persistir o indice** - `servicos/ingestao/armazenamento.py` - **Elia**
      O indice nao pode sumir ao reiniciar. Guarde em arquivo ou banco vetorial.

- [x] **2. Busca por similaridade** - `servicos/recuperacao/app.py` - **Lucas**
      Vetorizar a pergunta, comparar com cada documento e devolver os top_k. (Aula 9/10)

- [x] **3. Circuit breaker no LLM** - `servicos/geracao/app.py` - **Daniel**
      Envolver a chamada `gerar(...)` com `disjuntor.chamar(...)`, retentativa,
      tempo-limite e 503 quando o circuito estiver aberto. (Aula 11)

- [x] **3b. Resiliencia entre servicos + testes de falha** - **Vinicius**
      Timeout/retentativa/disjuntor nas chamadas REST internas e roteiro de testes de falha.

- [x] **4. Mensageria** - `servicos/ingestao/worker.py` + `servicos/comum/fila.py` - **Tiago**
      A indexacao passa por fila Redis, com retentativa e dead-letter. (Aula 8)

- [ ] **4b. Docker** - `Dockerfile` + `docker-compose.yml` - **Luis Felipe**
      Os tres servicos + worker + Redis sobem com `docker compose up --build`.
      Arquivos prontos; falta executar o compose em uma maquina com Docker.

- [x] **5. Fluxo completo** - de ponta a ponta - **Davi**
      Pergunta entra em /perguntar e sai uma resposta fundamentada nos documentos.

- [x] **6. README com diagrama** da arquitetura dos tres servicos - **Davi** (todos mandam a sua secao)

## Extensoes opcionais

- [ ] Reordenar os trechos por relevancia (reranking) - **Lucas**
- [x] Citar quais documentos embasaram a resposta - **Daniel / Elia**
- [x] Avaliacao automatica simples da qualidade da resposta - **Davi**
- [ ] Trocar TF-IDF por embeddings de verdade (sentence-transformers)

## Antes de entregar

- [x] Desligue a internet: o modo simulado do LLM mantem o sistema de pe?
- [x] Derrube o servico de recuperacao: o disjuntor abre como esperado?
- [x] A chave da API esta FORA do codigo (em variavel de ambiente)?
- [ ] Apague a pasta, clone do zero e siga o README - funciona? (qua 28/10)
