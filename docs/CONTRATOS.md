# Contratos entre os serviços

Este arquivo define **o que cada serviço recebe e devolve**. Ele existe para que
cada pessoa do grupo consiga trabalhar na sua parte sem esperar a do outro:
se você respeitar o contrato, a integração funciona.

Mudou algum campo? Atualize este arquivo **no mesmo PR** e avise no grupo.

---

## Visão geral do fluxo

```
cliente ──POST /indexar──► ingestao (8001) ──rpush──► Redis "ingestao:tarefas"
                                                            │ blpop
                                                            ▼
                                                    worker de ingestao
                                                    (vetoriza + salva índice)
                                                            │
                                                            ▼
                                                    dados/indice.json

cliente ──POST /perguntar──► geracao (8003) ──POST /buscar──► recuperacao (8002)
                                │                                  │
                                │                          GET /indice
                                │                                  ▼
                                │                            ingestao (8001)
                                ▼
                         LLM (API externa ou modo simulado)
                         protegido por circuit breaker + timeout + retentativa
```

A etapa que passa por **fila** (mensageria) é a **indexação**: quem envia os
documentos não espera a vetorização terminar.

---

## Ingestão — porta 8001

### `POST /indexar` → **202**

Coloca os documentos na fila e devolve um id para acompanhar. Não espera a
vetorização.

```json
// requisição
[{"texto": "O teorema CAP trata de consistencia e disponibilidade.", "origem": "teorema_cap.txt"}]

// resposta 202
{"id": "3f2b...", "status": "na_fila", "documentos": 1}
```

| Situação | Código |
|---|---|
| lista vazia ou algum `texto` vazio | 400 |
| Redis fora do ar | 503 |

### `GET /indexacao/{id}` → **200**

```json
{"status": "na_fila" | "processando" | "pronto" | "falhou",
 "indexados": 3,          // só quando "pronto": total de documentos no índice
 "erro": "..."}           // só quando "falhou"
```

`404` se o id não existir.

### `GET /indice` → **200** (consumido pela recuperação)

```json
{"total": 3,
 "itens": [{"texto": "...", "origem": "teorema_cap.txt", "vetor": [0.0, 0.12, ...]}]}
```

### `GET /saude`

```json
{"status": "ok", "documentos": 3, "fila": "ok" | "indisponivel"}
```

---

## Recuperação — porta 8002

### `POST /buscar` → **200**

```json
// requisição
{"pergunta": "o que diz o teorema CAP?", "top_k": 3}

// resposta (ordenado do mais para o menos parecido)
{"pergunta": "o que diz o teorema CAP?",
 "resultados": [{"texto": "...", "origem": "teorema_cap.txt", "score": 0.73}]}
```

`503` se a ingestão estiver fora do ar.

---

## Geração — porta 8003

### `POST /perguntar` → **200**

```json
// requisição
{"pergunta": "o que diz o teorema CAP?"}

// resposta
{"pergunta": "o que diz o teorema CAP?",
 "resposta": "...",
 "fontes": ["teorema_cap.txt"],
 "contexto": ["trecho 1", "trecho 2"],
 "degradado": false}     // true quando o LLM falhou e a resposta é de contingência
```

| Situação | Código |
|---|---|
| circuito do LLM aberto | 503 `{"detail": "LLM indisponivel: circuito aberto, tente em N s"}` |
| recuperação fora do ar | 503 |

### `GET /saude`

```json
{"status": "ok", "disjuntor": "fechado" | "aberto" | "meio"}
```

---

## Fila (Redis)

| Chave | Tipo | Uso |
|---|---|---|
| `ingestao:tarefas` | lista | tarefas de indexação pendentes |
| `ingestao:descarte` | lista | dead-letter: tarefas que falharam 3x |
| `ingestao:status:<id>` | string (JSON) | status de cada tarefa |
| `ingestao:trava-indice` | lock | impede dois workers de gravarem o índice ao mesmo tempo |

Formato de uma tarefa na fila:

```json
{"id": "3f2b...", "documentos": [{"texto": "...", "origem": "..."}]}
```

---

## Variáveis de ambiente

| Variável | Padrão | Quem usa |
|---|---|---|
| `REDIS_URL` | `redis://127.0.0.1:6379/0` | ingestão, worker |
| `INDICE_PATH` | `dados/indice.json` | ingestão, worker |
| `URL_INGESTAO` | `http://localhost:8001` | recuperação |
| `URL_RECUPERACAO` | `http://localhost:8002` | geração |
| `LLM_API_KEY` | vazio (modo simulado) | geração — **nunca no código** |
| `LLM_API_URL`, `LLM_MODELO`, `LLM_TIMEOUT` | ver `.env.example` | geração |

No Docker, use o nome do serviço no lugar de `localhost`
(ex.: `REDIS_URL=redis://redis:6379/0`, `URL_INGESTAO=http://ingestao:8001`).
