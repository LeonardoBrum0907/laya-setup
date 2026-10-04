# Entonação: plano para o schema v2

Decisão de 04/10/2026: o fine-tuning da v1 usa **só texto**. Em paralelo, o projeto já começa a
juntar dados de entonação para decidir, com números, se uma v2 que lê a voz vale a pena.

## Por que não agora

O Laya lê só o `state`. Se a v2 mandar campos de voz, a semente e o teste congelado também
precisam ter esses campos, medidos de **gravações reais**. Treinar com texto e depois mandar voz
não funciona bem. Sem gravações rotuladas, não há como treinar nem medir a v2.

## O que já existe (cliente)

`client/src/voice.ts` calcula, a partir do áudio PCM mono (Float32Array do Web Audio, ou WAV
decodificado no Node), sem dependências:

| Campo | O que é |
|---|---|
| `durationMs` | Duração do trecho |
| `speechRatio` | Fração de quadros de 30 ms com fala |
| `rmsDb`, `peakDb` | Volume da fala e pico, em dBFS |
| `wordsPerSecond` | Ritmo, usando o número de palavras da transcrição |
| `pitchHz`, `pitchStdHz` | Altura mediana da voz e quanto ela varia (autocorrelação) |
| `longPauses` | Pausas de 500 ms ou mais entre trechos de fala |

O bridge passa isso em `perceive({ transcript, voice })`. Na v1 o campo **vai só para o log**
(`logs/decisions.jsonl`); o `state` enviado ao Laya continua `{ transcript, device, channel }`
(há teste garantindo isso).

## Próximos passos

1. **Bridge:** chamar `voiceFeatures()` com o áudio de cada fala, junto com a transcrição.
2. **Sua linha de base:** volume e altura só significam algo comparados ao seu normal. Depois de
   umas 50 falas, calcular média e desvio por pessoa e guardar valores relativos
   (ex.: volume +8 dB acima do normal).
3. **Guardar o áudio (opcional, local):** `data/private/audio/<id>.wav` (pasta fora do git),
   para regravar ou recalcular campos depois.
4. **Rotular falas reais** do log com a mesma rubrica. Elas viram candidatas a teste congelado
   da v2.
5. **Medir se ajuda:** nos erros da v1 no teste congelado, ver se a voz separaria os casos
   (sarcasmo só no tom, grito sem "!"). Se separar, criar `ultron-v2` com um campo descritivo no
   `state`, por exemplo `"voz": {"volume": "alto", "ritmo": "rápido", "altura": "variada"}`
   (palavras, não números crus, porque o Laya lê texto).
6. **Alternativa mais cara:** um modelo de emoção na voz (ex.: wav2vec2 de emoção) cuja saída
   vira um campo do `state`. Só se as medidas simples não bastarem; testar em português e na
   CPU antes.

Risada e grito por regras podem ir direto para o motor de humor do Ultron sem esperar a v2.
