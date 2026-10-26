# Validação local da resiliência — 22/10/2026

Contribuição de Vinicius (tarefa 3b), branch `feat/vinicius`.

## Resultado

A resiliência HTTP entre serviços passou nos testes. Foram feitas 19 verificações com os três serviços reais em processos separados: 18 apresentaram o comportamento desejado e uma registrou o baseline 500 do LLM, pendente na tarefa 3 do Daniel.

A suíte automatizada também passou: **27 testes**, executados com `python -m unittest discover -s tests -v`. Os testes originais de persistência e similaridade foram mantidos.

## Método

Execução local no Windows com o ambiente virtual do repositório. Os serviços foram iniciados em portas temporárias, com um arquivo de índice separado contendo um documento de teste. Os processos de recuperação e ingestão foram realmente encerrados e reiniciados para simular indisponibilidade.

Redis e LLM foram apontados para portas locais reservadas sem servidor. Na prova de falha do LLM, foi usada uma chave fictícia e endereço em `127.0.0.1`, sem chamar uma API externa. Não foram alterados o índice de uso normal nem os terminais do usuário. Todos os processos temporários foram encerrados ao final.

## Evidências HTTP

| Cenário | HTTP observado | Duração (s) |
|---|---:|---:|
| Fluxo normal, LLM simulado e Redis fora | 200 | 0.225 |
| Saude da ingestao com Redis fora | 200 | 2.076 |
| Indexar com Redis fora | 503 | 2.065 |
| Consultar tarefa com Redis fora | 503 | 2.036 |
| Indice em disco independe do Redis | 200 | 0.030 |
| Recuperacao fora, consulta 1 | 503 | 3.654 |
| Recuperacao fora, consulta 2 | 503 | 3.681 |
| Recuperacao fora, consulta 3 | 503 | 3.651 |
| Recuperacao fora, consulta 4 | 503 | 0.024 |
| Recuperacao religada e circuito recuperado | 200 | 0.115 |
| Ingestao fora, busca 1 | 503 | 3.652 |
| Ingestao fora, busca 2 | 503 | 3.629 |
| Ingestao fora, busca 3 | 503 | 3.630 |
| Ingestao fora, busca 4 | 503 | 0.012 |
| Ingestao fora propaga 503 ate geracao | 503 | 0.695 |
| Ingestao religada e busca recuperada | 200 | 0.104 |
| Fluxo completo recuperado | 200 | 0.036 |
| Baseline da tarefa Daniel: LLM indisponivel | 500 | 0.474 |
| LLM simulado restaurado | 200 | 0.116 |

As consultas 1 a 3 com cada serviço parado esgotaram as tentativas e abriram o circuito. A consulta 4 foi recusada sem novas tentativas, com `falha=CircuitoAberto` nos logs. Após religar o serviço e aguardar 21 segundos reais, a sondagem fechou o circuito e as respostas voltaram a 200.

## Limites e integração pendente

- **LLM indisponível: 500 observado.** A geração ainda chama `gerar()` diretamente. A proteção dessa chamada pertence à tarefa 3 do Daniel; essa falha não foi corrigida pela contribuição de resiliência HTTP interna.
- **Docker/Compose:** não validado nesta etapa. Repetir o roteiro do README com os containers quando a contribuição do Luis Felipe estiver integrada.
- **Redis:** validada a indisponibilidade, com 503 tratado e leitura do índice preservada. Consumo de fila e indexação com Redis ativo não foram exercitados nesta validação.
- O ensaio usa um documento controlado para validar a comunicação. Não substitui a avaliação final de qualidade das respostas do projeto.
