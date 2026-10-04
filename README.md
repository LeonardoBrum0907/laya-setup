# laya-local

Laya rodando localmente como **camada de percepção** do Ultron. O Laya só descreve o que
aconteceu (tipo de ato, intensidade, se é dirigido ao Ultron); quem decide o efeito no humor é o
motor do Ultron. Se o Laya estiver fora, lento ou inseguro, entram regras por palavras-chave.

```
fala/evento → texto → laya-serve (127.0.0.1) → percepção tipada → motor do Ultron
                                  ↘ fallback por regras (fora / timeout / baixa confiança)
```

Base: `laya==0.3.26` (Apache 2.0). O que foi confirmado no repositório oficial e o que mudou em
relação ao briefing está em [docs/laya-recon.md](docs/laya-recon.md).

## Começar (Windows)

Pré-requisitos: Python 3.10+ (`py -0` lista as versões) e Node 22.18+.

```powershell
powershell -ExecutionPolicy Bypass -File scripts\setup.ps1      # CPU; use -Cuda se tiver GPU NVIDIA
.\.venv\Scripts\python.exe scripts\smoke_test.py                # baixa o checkpoint multilíngue na 1ª vez
.\.venv\Scripts\python.exe scripts\smoke_test.py --offline      # mesmo teste sem rede
.\.venv\Scripts\python.exe scripts\serve.py                     # serviço em http://127.0.0.1:8000
```

macOS / Linux: `bash scripts/setup.sh` e depois `.venv/bin/python scripts/...`.

### Windows com Smart App Control: use Docker

Se `import torch` falhar com `WinError 4551` ("Uma política de Controle de Aplicativo bloqueou
este arquivo"), o Smart App Control está bloqueando as DLLs do PyTorch, que não são assinadas.
Rode o servidor em Docker (o cliente Node continua no Windows):

```powershell
docker compose up -d --build        # serviço em http://127.0.0.1:8000, checkpoints em .\hf-cache
docker compose logs -f laya         # espere "Application startup complete"
docker compose run --rm laya python scripts/smoke_test.py --offline
docker compose down
```

A porta só é publicada em 127.0.0.1. Dentro do contêiner o servidor escuta em 0.0.0.0, e
`LAYA_IN_CONTAINER=1` libera isso sem exigir `LAYA_API_KEY`.

Com o serviço no ar:

```powershell
curl.exe -s http://127.0.0.1:8000/health
cd client; npm install; npm test; node examples/perceive.ts "Ultron, você é lento demais"
```

O exemplo grava cada decisão em `logs/decisions.jsonl`.

## Estrutura

| Caminho | O que é | Fase do briefing |
|---|---|---|
| `docs/laya-recon.md` | Reconhecimento: versões, formato do dataset, divergências | 0 |
| `scripts/setup.ps1`, `setup.sh`, `requirements.txt` | Ambiente isolado com versões fixadas | 1 |
| `scripts/smoke_test.py` | Uma pergunta `choice`, uma `score`, uma `noul`; latência fria e quente | 1 |
| `scripts/serve.py`, `.env.example` | `laya-serve` preso em 127.0.0.1; recusa bind público sem `LAYA_API_KEY` | 2 |
| `client/` | Cliente TypeScript, contrato de percepção, fallback, log JSONL e testes | 3 |
| `data/schema/ultron_schema.json` | Perguntas do Ultron v1 (só português): fonte única de verdade | 4 |
| `data/rubric.md`, `data/seed/`, `data/test_frozen/` | Rubrica, semente (escrita por você) e teste congelado | 5 |
| `scripts/validate_dataset.py` | Valida rótulos, duplicatas e vazamento entre treino e teste | 5 |
| `scripts/export_dataset.py` | Converte para o formato oficial de treino (`state`/`questions`/`gold`) | 5, 7 |
| `scripts/eval.py` | Acurácia, matriz de confusão e ECE por idioma e ruído; Laya vs regras; fila de revisão | 6 |

## Contrato de percepção

```ts
type Perception = {
  actType: 'praise' | 'provocation' | 'command' | 'question' | 'small_talk'
         | 'indifference' | 'threat' | 'forbidden_name' | 'farewell';
  intensity: number;          // 0..1
  directedAtUltron: boolean;
  sarcastic: boolean;
  confidence: number;         // answer_confidence do act_type, ou fixo nas regras
  source: 'laya' | 'rules';
  fallbackReason?: 'unavailable' | 'timeout' | 'low_confidence' | 'invalid';
};
```

O estado enviado ao Laya é só `{ transcript, device, channel }`, **sem humor**. O evento pode
trazer `voice` (volume, ritmo, altura, de `client/src/voice.ts`), mas na v1 isso só vai para o
log; veja `docs/entonacao.md`. Mouse errático,
inatividade e contagem de chamados continuam nas regras do motor e não passam por aqui.

### Ligando ao Ultron

1. O bridge Node do Ultron cria um `Perceiver` (veja `client/examples/perceive.ts`) e chama
   `perceive()` para cada fala transcrita.
2. O mapeamento de percepção para deltas de humor fica como **dados** em
   `mind/personalities/ultron.ts`, por exemplo:
   ```ts
   perception: {
     provocation:    { irritation: +0.15, vanity: -0.05 },
     praise:         { vanity: +0.10 },
     forbidden_name: { irritation: +0.25, vanity: -0.10 },
     // multiplicado por intensity; ignorado se directedAtUltron = false
   }
   ```
   O `mind/core` continua sem saber de Ultron ou de Laya.
3. O sinal de "ouvi" em até 0,2 s continua sendo reflexo por regras; ele não espera a percepção.

## Limites que importam

- Os checkpoints base ficam **perto do acaso** em decisões tipadas zero-shot (0,36 contra 0,32 do
  acaso). O schema `ultron-v1` (só português, nove atos de fala) está fechado; ele define o que rotular, não garante qualidade. A qualidade vem do
  fine-tuning com dados do domínio.
- O limiar de confiança do fallback (`minConfidence`, 0,6 por padrão) é um chute até ser medido
  com `scripts/eval.py` no teste congelado.
- Fine-tuning (Fase 7) não está automatizado aqui: o caminho oficial é o notebook Kaggle 2×T4 ou
  o script para Apple Silicon do repositório do Laya, alimentado por `scripts/export_dataset.py`.
  Não existe `laya.train` na 0.3.26.

## Próximos passos

1. Rodar o setup e o smoke test na sua máquina e anotar latência e memória em `docs/laya-recon.md`.
2. Responder as perguntas em aberto no fim de `docs/laya-recon.md`. Idioma e atos de fala já
   fechados em `ultron-v1` (04/10/2026); faltam RAM e orçamento de latência.
3. Escrever a semente e o teste congelado seguindo `data/rubric.md`.
4. Expansão do dataset por LLM (`scripts/expand_dataset.py`) e preparação do fine-tuning.
5. Entonação: medir a voz no bridge e juntar gravações para decidir uma v2 (`docs/entonacao.md`).
6. Pesquisa de portabilidade (ONNX/`laya-ts`, `laya-mlx`, `decision_ai`).
