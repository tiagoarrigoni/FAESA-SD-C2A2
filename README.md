# Kit de Partida — C2.A2: RAG Distribuído em Microsserviços

**Sistemas Distribuídos e Computação em Nuvem · FAESA · 2026/2**
Prof. Howard Cruz Roatti · Lançado na Aula 8 (24/09) · Entrega na Aula 12 (29/10)

---

## O que é isto

RAG (geração aumentada por recuperação) permite que um modelo de linguagem responda
com base em documentos **seus**, sem retreinar nada. Do ponto de vista de sistemas
distribuídos é um caso perfeito: **três responsabilidades distintas** que conversam
entre si, com uma **dependência externa lenta e instável** (a API do LLM) que precisa
ser protegida.

> **Sobre a IA neste trabalho:** todo contato com inteligência artificial aqui é
> **chamada de biblioteca ou de API**. Você **não vai treinar modelos** nem precisar de
> matemática de aprendizado de máquina. O modelo já vem pronto e configurado.
> A sua nota vem da **engenharia distribuída**: arquitetura, comunicação, resiliência e
> execução reproduzível — a sofisticação do modelo **não pontua**.

---

## Como começar

```bash
# 1. Clone o kit e entre na pasta
git clone https://github.com/howardroatti/sd-2026-2-kit-c2a2.git
cd sd-2026-2-kit-c2a2

# 2. Crie e ative o ambiente virtual
python -m venv .venv
# Windows:
.venv\Scripts\activate
# Linux/macOS:
source .venv/bin/activate

# 3. Instale as dependências
pip install -r requirements.txt
```

```bash
# 4. Copie o arquivo de ambiente (funciona offline sem chave de LLM)
cp .env.example .env

# 5. Suba os três serviços, cada um em um terminal
uvicorn servicos.ingestao.app:app     --port 8001
uvicorn servicos.recuperacao.app:app  --port 8002
uvicorn servicos.geracao.app:app      --port 8003

# 6. Indexe os documentos de teste
curl -X POST http://localhost:8001/indexar -H "Content-Type: application/json" \
  -d '[{"texto":"O teorema CAP trata de consistencia e disponibilidade.","origem":"aula11"}]'

# 7. Pergunte (funciona depois da TAREFA 2)
curl -X POST http://localhost:8003/perguntar -H "Content-Type: application/json" \
  -d '{"pergunta":"o que diz o teorema CAP?"}'
```

---

## Estrutura do projeto

```
sd-2026-2-kit-c2a2/
├── servicos/
│   ├── comum/
│   │   ├── embeddings.py       # PRONTO - vetorização offline
│   │   ├── llm.py              # PRONTO - com modo simulado
│   │   └── circuit_breaker.py  # PRONTO - modelo de referência
│   ├── ingestao/app.py         # TAREFA 1
│   ├── recuperacao/app.py      # TAREFA 2
│   └── geracao/app.py          # TAREFA 3
├── documentos/                 # base de teste para indexar
├── docker-compose.yml          # TAREFA 4
└── TAREFAS.md                  # <- comece por aqui
```

## Resiliência entre serviços — Vinicius (tarefa 3b)

As chamadas `geração → POST /buscar → recuperação` e
`recuperação → GET /indice → ingestão` usam o cliente compartilhado em
`servicos/comum/http_resiliente.py`. A busca por similaridade, a persistência,
a fila Redis e a chamada ao LLM mantêm suas implementações próprias.

| Proteção | Comportamento |
|---|---|
| Timeout de conexão/leitura por tentativa | ingestão: 1 s / 2 s; recuperação: 1 s / 12 s |
| Retentativa | até 3 tentativas, incluindo a primeira |
| Backoff exponencial | espera de 0,2 s e 0,4 s entre tentativas |
| Falhas repetidas | conexão, timeout e HTTP 429, 500, 502, 503, 504 |
| Circuit breaker | abre após 3 consultas consecutivas malsucedidas, contando uma falha após esgotar as tentativas |
| Recuperação do circuito | após 20 s, admite uma consulta de teste; sucesso fecha, falha reabre |
| HTTP 503 | conexão, timeout, erro HTTP, JSON inválido, resposta fora do contrato ou circuito aberto |

Outros erros HTTP (por exemplo, 400/404) e respostas inválidas não são repetidos.
Cada dependência tem seu próprio circuito, em memória, por processo. O circuito
do LLM (`disjuntor`) continua separado dos clientes HTTP. O estado `meio` admite
uma única consulta lógica, incluindo suas tentativas, mesmo com requisições
simultâneas. Respostas de chamadas antigas não fecham um circuito recém-aberto.

Os 12 s de leitura da recuperação permitem que ela termine suas tentativas de
acesso à ingestão (até aproximadamente 9,6 s somando os timeouts e o backoff).
Esses valores são limites de conexão e inatividade de leitura do Requests,
não um prazo total rígido. As retentativas das duas camadas podem produzir até
9 acessos à ingestão para uma pergunta antes da abertura do circuito.
O cliente deve ser usado somente para consultas seguras de repetir, como
`GET /indice` e `POST /buscar`; não deve envolver `POST /indexar`.

Tentativas, pausas e falhas são registradas em `logs/http_resiliente.log`,
sem gravar perguntas ou documentos. O formato das respostas de sucesso e os
campos de `/saude` foram preservados; o log mostra o estado dos circuitos HTTP.

### Testes automatizados

Na raiz do repositório, com o ambiente virtual ativado:

```powershell
python -m unittest discover -s tests -v
```

Os testes incluem os existentes de persistência e similaridade, falhas e
backoff simulados, concorrência do circuit breaker e testes HTTP reais em
portas locais temporárias. Verificam 503 quando ingestão ou recuperação estão
inacessíveis, propagação do 503, abertura e recuperação dos circuitos, além do
fluxo normal com LLM simulado. Não exigem Redis, Docker, chave de API, pytest
ou httpx. A ingestão dos testes HTTP é uma API controlada com índice fixo.

### Roteiro manual de falhas no PowerShell

Reinicie os serviços após atualizar o código. Em três terminais na raiz do
repositório, com o ambiente virtual ativado, execute respectivamente:

```powershell
uvicorn servicos.ingestao.app:app --port 8001
uvicorn servicos.recuperacao.app:app --port 8002
uvicorn servicos.geracao.app:app --port 8003
```

Em um quarto terminal, defina a função abaixo para exibir o código HTTP e o
corpo, inclusive quando o PowerShell 5 recebe um erro:

```powershell
function Consultar-API([string]$Url) {
    $body = @{ pergunta = "O que diz o teorema CAP?" } | ConvertTo-Json
    try {
        $r = Invoke-WebRequest -UseBasicParsing -Uri $Url -Method POST `
            -ContentType "application/json" -Body $body
        [PSCustomObject]@{ status = [int]$r.StatusCode; corpo = $r.Content }
    } catch {
        $r = $_.Exception.Response
        if ($null -eq $r) { throw }
        $leitor = New-Object System.IO.StreamReader($r.GetResponseStream())
        try {
            [PSCustomObject]@{ status = [int]$r.StatusCode; corpo = $leitor.ReadToEnd() }
        } finally { $leitor.Dispose() }
    }
}

Consultar-API "http://localhost:8003/perguntar"
```

1. Com os três serviços ligados e sem `LLM_API_KEY`, espere **200** em
   `/perguntar`, com resposta simulada. Um índice vazio também permite o teste
   de disponibilidade, mas retorna contexto vazio.
2. Desligue apenas a recuperação com `Ctrl+C` no terminal da porta 8002.
   Execute o comando abaixo: as três consultas falham com **503**; a quarta
   é recusada pelo circuito, sem novas tentativas HTTP. Confira o log para
   distinguir `ConnectionError`/`ConnectTimeout` de `CircuitoAberto`.

   ```powershell
   1..4 | ForEach-Object { Consultar-API "http://localhost:8003/perguntar" }
   Get-Content logs\http_resiliente.log -Tail 20
   ```

3. Religue a recuperação com o comando da porta 8002. Aguarde 21 s após a
   última abertura e consulte `/perguntar` novamente: espere **200**.
4. Desligue apenas a ingestão com `Ctrl+C` no terminal da porta 8001.
   Execute quatro consultas diretas à recuperação e uma à geração:

   ```powershell
   1..4 | ForEach-Object { Consultar-API "http://localhost:8002/buscar" }
   Consultar-API "http://localhost:8003/perguntar"
   ```

   Espere **503** nos dois endpoints, com `detail` indicando a dependência
   indisponível. As chamadas diretas abrem o circuito da ingestão.
5. Religue a ingestão. Aguarde 21 s após a última abertura de cada circuito e
   repita as consultas: espere **200** e retomada automática, sem reiniciar os
   consumidores. Guarde o retorno HTTP e o trecho do log como evidência.

Redis indisponível continua sendo tratado pela ingestão: `POST /indexar`
deve devolver 503, enquanto `GET /indice` lê o disco e pode continuar
atendendo a busca. A proteção da API real do LLM é a tarefa 3 do Daniel;
não é validada pelos testes desta seção. O teste com containers depende do
Compose do Luis Felipe: quando os serviços estiverem definidos, repita o
roteiro usando `docker compose stop/start recuperacao` ou `ingestao`.

---

## O que você precisa fazer

Abra o arquivo **`TAREFAS.md`**: ele lista o núcleo obrigatório item a item, indicando
o arquivo e a aula de referência de cada um.

---

## Como você será avaliado

| Critério | Pontos |
|---|---|
| Arquitetura e decomposição em serviços | 1,5 |
| Comunicação funcionando (REST / gRPC / mensageria) | 1,5 |
| Resiliência e tratamento de falhas | 1,0 |
| Execução reproduzível (README, container, deploy) | 1,0 |
| **Sofisticação do modelo de IA** | **não pontua** |
| **Total** | **5,0** |

**Entrega:** no seu repositório do GitHub, **sem apresentação oral**. Grupos livres.

---

## Aulas de referência

- **Aula 8** — Mensageria, eventos e API Gateway
- **Aula 10** — Replicação, consistência e CAP
- **Aula 11** — Consenso (Raft) e resiliência: circuit breaker
- **Aula 6** — IA como serviço (vocabulário: embedding, inferência, LLM)

---

## Dúvidas frequentes

**Preciso saber machine learning?** Não. O modelo já está pronto e você só chama uma função.

**E se eu não tiver internet no laboratório?** Tudo neste kit funciona offline. O modelo é
treinado localmente e o cliente de LLM tem modo simulado.

**Posso trocar a linguagem?** O kit é em Python porque é o ecossistema usado nas aulas.
Se quiser usar outra linguagem, converse com o professor antes.

**Posso usar IA para me ajudar a programar?** Sim. Este é um trabalho prático feito fora de
sala, e usar ferramentas de IA é realista. O que se avalia é o **sistema funcionando** e as
**decisões de arquitetura** — que você precisa saber explicar.
