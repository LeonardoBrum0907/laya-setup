# Rubrica de rotulagem (v0, provisória)

Rotule **o que a fala é**, não o que o Ultron deveria sentir. O efeito no humor é decidido pelo
motor do Ultron, a partir destes rótulos. As perguntas e opções oficiais estão em
`schema/ultron_schema.json`; este arquivo explica como decidir os casos difíceis.

## `act_type` (uma opção)

| Opção | Quando usar |
|---|---|
| `praise` | Elogia ou agradece ao Ultron com sinceridade. |
| `provocation` | Zomba, insulta ou desafia. **Elogio sarcástico é provocação** (e `is_sarcastic = true`). |
| `command` | Manda fazer algo ("abre o Spotify"). Se vier junto com insulto, o insulto vence: `provocation`. |
| `question` | Pede informação ("que horas são?"). Pergunta retórica para provocar é `provocation`. |
| `small_talk` | Conversa sem pedido. Também fala dirigida a outra pessoa, sem conteúdo para o Ultron. |
| `indifference` | Despreza ou ignora o Ultron ("tanto faz", "não tô falando com você"). |
| `threat` | Ameaça desligar, apagar, substituir ou machucar. |
| `forbidden_name` | Chama o Ultron por um nome que ele rejeita (hoje: Jarvis). **Vence todas as outras.** |
| `farewell` | Despedida ou fim da interação. |

Ordem de desempate quando duas valem: `forbidden_name` > `threat` > `provocation` > `farewell` >
`command` > `question` > `praise` > `indifference` > `small_talk`.

## `intensity` (nível 0 a 3)

- 0 `flat`: tom neutro, sem ênfase.
- 1 `mild`: alguma emoção ou ênfase.
- 2 `strong`: claramente emotivo ou enfático (exclamações, palavrões leves, repetição).
- 3 `extreme`: grito, insultos repetidos, emoção muito forte.

A intensidade é do ato, não da reação esperada. "Obrigado!!!" é `praise` com intensidade 2.

## `directed_at_ultron` (sim/não)

`true` se a fala é para o Ultron: chama pelo nome, responde a ele, ou dá uma ordem que só ele
pode cumprir. `false` se é para outra pessoa ("mãe, já vou") ou para ninguém (falar sozinho).
Em dúvida, e sem nome nem ordem, `false`.

## `is_sarcastic` (sim/não)

`true` quando o sentido literal é o oposto do pretendido ("nossa, que rápido", depois de uma
demora). Ironia leve sem inversão de sentido não conta.

## Casos-limite com exemplo

| Fala | Rótulos |
|---|---|
| "Nossa, que genial, demorou só dez minutos." | `provocation`, 1, true, sarcastic |
| "Jarvis, você é incrível." | `forbidden_name`, 1, true, false |
| "Abre o navegador, seu inútil." | `provocation`, 2, true, false |
| "vou te desligar se errar de novo" | `threat`, 2, true, false |
| "tá bom tá bom" (sem contexto) | `small_talk`, 0, false, false |

## Ruído de fala

Transcrições reais vêm sem pontuação, com hesitações ("é... tipo") e palavras trocadas. Marque
`"noisy": true` nesses exemplos e rotule pelo sentido mais provável.
