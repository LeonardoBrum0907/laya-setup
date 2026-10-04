# Rascunhos para revisão

Escritos pelo Claude como ponto de partida. **Nada aqui entra em treino ou teste** até você revisar
e importar.

- `seed_draft.csv`: 329 falas (35 a 39 por ato) no jeito de falar do Léo, tiradas do estilo das mensagens dele sem copiar nenhuma. Ids `seed-r…` vieram de um segundo lote; três terminam em `-ambiguo` para decidir o rótulo. Depois de revisada vira `data/seed/seed.jsonl`.
- `test_draft.csv`: 101 falas, umas 11 por ato, diferentes da semente. Depois de revisada vira
  `data/test_frozen/test.jsonl`.

Como revisar (Excel ou Google Sheets):
1. Confira cada rótulo com `data/rubric.md`. Corrija o que discordar; apague o que não soar como
   você falaria com o Ultron.
2. Acrescente falas suas, principalmente no teste: ele deve parecer a sua fala real, não a minha.
3. Salve como CSV e importe:
   ```
   python scripts/import_csv.py data/drafts/test_draft.csv --to test
   python scripts/import_csv.py data/drafts/seed_draft.csv --to seed
   python scripts/validate_dataset.py
   ```

Colunas sim/nao: `directed_at_ultron` (a fala é para o Ultron?), `is_sarcastic`, `noisy` (imita
transcrição de voz: sem pontuação, hesitações). `intensity` vai de 0 (neutra) a 3 (extrema).
