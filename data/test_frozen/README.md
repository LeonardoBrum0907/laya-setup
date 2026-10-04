# Teste congelado

Conjunto de teste escrito e revisado **por você**. Regras:

- **Nunca** entra em treino, nem serve de base para variações geradas por LLM.
- `scripts/export_dataset.py` se recusa a exportar esta pasta, e `scripts/validate_dataset.py` acusa qualquer fala daqui que também apareça no treino (`LEAK`).
- Mesmo formato da semente. Só português (schema `ultron-v1`). Inclua falas com ruído de transcrição (`"noisy": true`) e casos ambíguos.
- Mudou o teste? Registre a data e o motivo no fim deste arquivo, para que relatórios antigos continuem comparáveis.

## Histórico

- 2026-10-04: pasta criada, vazia.
