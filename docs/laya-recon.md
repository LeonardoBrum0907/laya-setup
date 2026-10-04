# Reconhecimento do Laya (Fase 0)

Feito em 04/10/2026, lendo o README do `main` de `github.com/NandhaKishorM/laya`, os metadados do
PyPI e o código do pacote `laya==0.3.26` (wheel baixada e inspecionada). O Hugging Face estava
bloqueado na máquina onde isto foi escrito, então **nenhum checkpoint foi baixado nem executado
ainda**: latência e memória ficam para o primeiro `smoke_test.py` na sua máquina.

## Versões

| Item | Valor |
|---|---|
| `laya` no PyPI | 0.3.26 (a mais recente em 03/10/2026) |
| Python | `>=3.10` (confirmado no PyPI; o README explica que torch 2.14, transformers 5 e huggingface_hub 1.x exigem 3.10) |
| Dependências | `torch>=2.0`, `transformers>=4.48`, `safetensors`, `huggingface_hub`, `numpy`; extra `serve` = fastapi + uvicorn + python-multipart |
| Comandos instalados | `laya`, `laya-serve`, `laya-evals`, `laya-mcp-server` |

## Confirmado

- **Checkpoints.** Ficam todos no repositório `convaiinnovations/laya` no Hugging Face: o inglês
  na raiz, e `multilingual` e `typed-decisions` como **subpastas**
  (`laya.load("convaiinnovations/laya", subfolder="multilingual")`). No `Router` e no servidor,
  basta o nome: `english`, `multilingual`, `typed-decisions`.
- **Router.** `Router().predict(state, questions, model=...)` escolhe o checkpoint pela língua
  e devolve `routing.model`. Português vai para `multilingual`. `Router(max_loaded=1)` reduz
  memória.
- **`state`** pode ser texto ou objeto; um objeto é serializado como JSON antes de entrar no modelo.
  Usamos `{transcript, device, channel}`, sem humor.
- **`score`** recebe `criteria` como **lista** de descrições de nível (cada nível precisa de
  descrição). A resposta traz `score` (nível esperado, 0..n-1), `probabilities` por índice e
  `legend`.
- **`choice`** recebe `criteria` como mapa `opção: descrição`. Resposta: `choice`,
  `probabilities`, `confidence`, `answer_confidence`.
- **`noul`** aceita `criteria` com as chaves `false` e `true`. Resposta: `noul` = P(true).
- **Confiança.** `confidence` em `choice`/`score` é 1 − entropia normalizada; o valor calibrado
  para usar como limiar é **`answer_confidence`** (probabilidade da resposta dada). Existe
  `min_confidence`, que marca `low_confidence` e `abstention`. O README avisa que os checkpoints
  vêm **excessivamente confiantes** e que o `multilingual` não tem temperaturas ajustadas: o
  limiar do fallback precisa ser medido no nosso teste congelado.
- **Servidor.** `laya-serve` escuta em `0.0.0.0:8000` por padrão e não pede autenticação sem
  `LAYA_API_KEY` (confirmado no código de `laya/serve.py`). Existe `LAYA_HOST`, que usamos com
  `127.0.0.1`. Rotas: `GET /health`, `POST /v1/systemone`, `POST /v1/systemone/batch`.
  `LAYA_PRELOAD` vale 1 por padrão; `LAYA_MODELS` limita o que é pré-carregado.
- **Orçamento de tokens.** O multilíngue aceita até 8.192 tokens com `max_len=8192` (vem com
  1.024). Isso resolve o ponto [?] do briefing. Para falas curtas, não importa.
- **Cliente oficial em TypeScript.** Existem `laya-client` (HTTP para `laya-serve`) e `laya-ts`
  (inferência ONNX direto em JS). Escrevemos um cliente próprio mínimo em `client/` porque ele
  precisa do contrato de percepção e do fallback; dá para trocar pelo `laya-client` depois.

## Formato do dataset (resolve a seção 6 do briefing)

Vale a **descrição A**. O script oficial
`notebooks/laya_finetune_typed_decisions_mps.py` carrega `LocalLLaMA/typed-decisions` e, para
cada linha, faz `json.loads` em `state`, `questions` e `gold`. O `gold` é
`{id_da_pergunta: {"probabilities": {...}}}`, com rótulos suaves:

- `choice`: chaves = nomes das opções;
- `noul`: chaves `"false"` e `"true"`;
- `score`: chaves `"0"`, `"1"`, ... até n−1.

Nós escrevemos os exemplos num formato mais simples (rótulo direto por pergunta, perguntas vindas
do schema) e convertemos com `scripts/export_dataset.py`.

## O que muda em relação ao briefing

| Briefing | Realidade |
|---|---|
| `convaiinnovations/laya-multilingual` e `-typed-decisions` como repositórios separados | Subpastas de `convaiinnovations/laya` |
| `laya.train` / `laya-train` talvez existam | **Não existem** na 0.3.26 (não há módulo `train` nem comando). Fine-tuning é pelo notebook ou pelo script MPS |
| 8.192 tokens no multilíngue: a confirmar | Confirmado, com `max_len=8192` |
| Python 3.9+ ou 3.10+ | 3.10+ |
| `laya-serve` sem auth e em 0.0.0.0 [T] | Confirmado no código |
| Fine-tuning: tempo desconhecido | README: cerca de 4 a 5 h em 2×T4 para 4 épocas sobre ~30 mil perguntas |

## Ainda falta medir (na sua máquina)

- Tamanho do download e memória residente do `multilingual` na CPU.
- Latência fria e quente (`scripts/smoke_test.py`).
- Se a latência na CPU cabe no orçamento do Ultron (resposta em até 2 s; o "ouvi" de 0,2 s
  continua sendo reflexo por regras e não deve esperar o Laya).

## Perguntas em aberto (seção 9 do briefing)

Já sabemos pelo contexto do projeto: Windows 11, Node 24, Ultron no navegador com um bridge Node.
Por isso o Laya fica como serviço local separado, chamado pelo bridge. Faltam:

1. RAM da máquina. GPU: **AMD RX 570** (resposta de 04/10/2026). Sem CUDA, e o ROCm no Windows
   não suporta Polaris, então `LAYA_DEVICE=cpu`. Fine-tuning local fica inviável: usar o notebook
   Kaggle 2×T4. Se a CPU for lenta, avaliar exportação ONNX com DirectML (não testado).
2. Idiomas de entrada no começo: só português, ou português e inglês?
3. Quais atos de fala importam mais para a personalidade (refina `act_type`)?
4. Orçamento de latência da percepção.
