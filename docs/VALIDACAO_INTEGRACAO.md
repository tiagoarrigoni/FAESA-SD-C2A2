# Validacao da integracao — 26/10/2026

## Contribuicoes preservadas

- Base `origin/main` em `abbeaf8`, incluindo os Dockerfiles e Compose do Luis Felipe.
- LLM do Daniel, commit `0efedfb`, integrado com o cliente REST do Vinicius.
- Demonstracao do Davi, commit `6b67329` (PR #6), integrada e ajustada ao contrato HTTP.
- Persistencia, similaridade e mensageria dos colegas mantidas.

O conflito em `servicos/geracao/app.py` foi resolvido combinando os circuitos independentes para recuperacao e LLM. As respostas preservam `contexto` e adicionam `fontes` e `degradado` conforme a contribuicao do Daniel.

A demonstracao agora envia uma lista ao `/indexar`, acompanha `/indexacao/{id}` ate `pronto`, interpreta fontes como nomes de arquivo e mede cobertura sobre o contexto. Uma falha de indexacao interrompe o script antes das perguntas.

## Verificacao automatizada

**35 testes passando em 6.956 segundos.**

```powershell
python -m unittest discover -s tests -v
```

Inclui persistencia e similaridade originais, timeout, retry/backoff, concorrencia do circuit breaker, falhas HTTP entre servicos, contingencia e recuperacao do LLM, e o contrato da demonstracao assincrona.

## Processos reais

Foram feitas 25 verificacoes em portas temporarias, com indice separado, sem alterar o indice de uso normal. Ingestao e recuperacao foram encerradas e reiniciadas; os circuitos foram testados aguardando 21 segundos reais. A API do LLM foi substituida por um servidor local controlado, com chave ficticia, para validar falha e recuperacao sem enviar dados a uma API externa. Todos os processos temporarios foram encerrados.

| Cenario | HTTP observado | Duracao (s) |
|---|---:|---:|
| Fluxo normal, LLM simulado e Redis fora | 200 | 0.248 |
| Saude da ingestao com Redis fora | 200 | 2.051 |
| Indexar com Redis fora | 503 | 2.050 |
| Consultar tarefa com Redis fora | 503 | 2.041 |
| Indice em disco independe do Redis | 200 | 0.010 |
| Recuperacao fora, consulta 1 | 503 | 2.634 |
| Recuperacao fora, consulta 2 | 503 | 3.638 |
| Recuperacao fora, consulta 3 | 503 | 3.649 |
| Recuperacao fora, consulta 4 | 503 | 0.013 |
| Recuperacao religada e circuito recuperado | 200 | 0.250 |
| Ingestao fora, busca 1 | 503 | 3.646 |
| Ingestao fora, busca 2 | 503 | 3.653 |
| Ingestao fora, busca 3 | 503 | 3.636 |
| Ingestao fora, busca 4 | 503 | 0.014 |
| Ingestao fora propaga 503 ate geracao | 503 | 0.655 |
| Ingestao religada e busca recuperada | 200 | 0.097 |
| Fluxo completo recuperado | 200 | 0.035 |
| LLM fora, consulta 1 | 200 | 2.610 |
| LLM fora, consulta 2 | 200 | 2.461 |
| LLM fora, consulta 3 | 503 | 2.461 |
| LLM fora, consulta 4 | 503 | 0.042 |
| Circuito LLM aberto | 200 | 0.007 |
| LLM religado e circuito recuperado sem reiniciar geracao | 200 | 0.048 |
| Circuito LLM fechado apos sondagem | 200 | 0.009 |
| LLM simulado restaurado | 200 | 0.123 |

A contingencia do LLM nas duas primeiras consultas retorna 200 com `degradado: true`, `fontes` e `contexto`. A terceira consulta malsucedida abre o circuito e retorna 503; a quarta e recusada sem chamar o LLM. Apos religar o LLM local, a sondagem fecha o circuito e devolve 200 com `degradado: false`, sem reiniciar o servico de geracao. O baseline 500 de 22/10/2026 foi resolvido por esta integracao.

## Docker e limites

O Compose foi validado estaticamente: YAML legivel, cinco servicos (Redis, ingestao, worker, recuperacao, geracao), duas replicas do worker, Dockerfiles presentes e comandos Python dos healthchecks com sintaxe valida. Docker nao esta instalado nesta maquina; build de imagens e execucao de containers continuam sem validacao aqui.

Redis foi testado inacessivel: indexacao e consulta de tarefa retornam 503, enquanto o indice persistido e o fluxo de pergunta continuam operacionais. O consumo real da fila com Redis ativo e o fluxo completo da demonstracao com workers reais ainda precisam ser exercitados em um ambiente com Redis. O contrato e a espera da demonstracao foram cobertos pelos testes automatizados, com respostas controladas.

## Estado da publicacao

Este documento registra a validacao da branch de integracao. O merge remoto deve ser confirmado no PR #4; sua conclusao nao e pressuposta por estes testes.
