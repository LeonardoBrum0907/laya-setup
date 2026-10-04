// Usage: node examples/perceive.ts "Ultron, você é lento demais"   (with scripts/serve.py running)

import { fileURLToPath } from 'node:url';
import { LayaClient, Perceiver } from '../src/index.ts';
import { jsonlLogger, loadQuestions } from '../src/node.ts';

const root = fileURLToPath(new URL('../../', import.meta.url));
const perceiver = new Perceiver({
  client: new LayaClient({ timeoutMs: 4000, apiKey: process.env.LAYA_API_KEY || undefined }),
  questions: loadQuestions(`${root}data/schema/ultron_schema.json`),
  onDecision: jsonlLogger(`${root}logs/decisions.jsonl`),
});

const text = process.argv[2] ?? 'Ultron, você é lento demais, anda logo com isso.';
console.log(await perceiver.perceive({ transcript: text, channel: 'voice' }));
