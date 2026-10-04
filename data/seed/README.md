# Semente (escrita à mão)

Esta pasta é para exemplos escritos **por você**, não gerados. O agente só criou o esqueleto.

- Um arquivo `.jsonl` por tema, por exemplo `provocacao.jsonl`, `chamados.jsonl`.
- Formato de cada linha: veja `template.jsonl.example` e o cabeçalho de `scripts/validate_dataset.py`.
- As perguntas e opções vêm de `data/schema/ultron_schema.json`. Aqui vão só os rótulos.
- Rotule seguindo `data/rubric.md`. Em caso de dúvida entre duas classes, anote no `id` (ex.: `seed-0042-ambiguo`) e discuta antes de expandir.
- Nada de dados pessoais reais.
- Depois de escrever: `python scripts/validate_dataset.py`.

Os exemplos em `data/examples/plumbing.jsonl` servem só para testar o encanamento; não são semente.
