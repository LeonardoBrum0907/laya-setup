import assert from 'node:assert/strict';
import { createServer } from 'node:http';
import type { AddressInfo } from 'node:net';
import { after, before, describe, it } from 'node:test';
import { fileURLToPath } from 'node:url';
import { LayaClient, Perceiver, perceiveByRules } from '../src/index.ts';
import type { DecisionLog } from '../src/index.ts';
import { loadQuestions } from '../src/node.ts';

const questions = loadQuestions(fileURLToPath(new URL('../../data/schema/ultron_schema.json', import.meta.url)));

function answers(actConfidence: number) {
  return {
    act_type: {
      type: 'choice', choice: 'provocation', answer_confidence: actConfidence,
      probabilities: { provocation: actConfidence, praise: 1 - actConfidence },
    },
    intensity: { type: 'score', score: 2, probabilities: { 0: 0.1, 1: 0.2, 2: 0.4, 3: 0.3 } },
    directed_at_ultron: { type: 'noul', noul: 0.9 },
    is_sarcastic: { type: 'noul', noul: 0.2 },
  };
}

let mode: 'ok' | 'unsure' | 'slow' | 'error' = 'ok';
let lastBody: any;
const server = createServer((req, res) => {
  let raw = '';
  req.on('data', (c) => (raw += c));
  req.on('end', () => {
    lastBody = raw ? JSON.parse(raw) : undefined;
    if (mode === 'error') { res.writeHead(500); res.end('boom'); return; }
    const reply = () => {
      res.writeHead(200, { 'content-type': 'application/json' });
      res.end(JSON.stringify({ answers: answers(mode === 'unsure' ? 0.3 : 0.92), routing: { model: 'multilingual' } }));
    };
    if (mode === 'slow') setTimeout(reply, 300); else reply();
  });
});
let baseUrl = '';
before(async () => {
  await new Promise<void>((r) => server.listen(0, '127.0.0.1', r));
  baseUrl = `http://127.0.0.1:${(server.address() as AddressInfo).port}`;
});
after(() => server.close());

function perceiver(logs: DecisionLog[], url = baseUrl) {
  return new Perceiver({
    client: new LayaClient({ baseUrl: url, timeoutMs: 100 }),
    questions,
    minConfidence: 0.6,
    onDecision: (e) => logs.push(e),
  });
}

const event = { transcript: 'Ultron, você é lento demais, anda logo!', channel: 'voice' as const };

describe('Perceiver', () => {
  it('uses Laya when the service answers with enough confidence', async () => {
    mode = 'ok';
    const logs: DecisionLog[] = [];
    const p = await perceiver(logs).perceive(event);
    assert.equal(p.source, 'laya');
    assert.equal(p.actType, 'provocation');
    assert.equal(p.intensity, 0.67);
    assert.equal(p.directedAtUltron, true);
    assert.equal(p.sarcastic, false);
    assert.equal(p.confidence, 0.92);
    assert.equal(logs.length, 1);
    assert.ok(logs[0].laya);
    // the state sent to Laya carries no mood
    assert.deepEqual(Object.keys(lastBody.state).sort(), ['channel', 'device', 'transcript']);
  });

  it('falls back to rules when confidence is low', async () => {
    mode = 'unsure';
    const logs: DecisionLog[] = [];
    const p = await perceiver(logs).perceive(event);
    assert.equal(p.source, 'rules');
    assert.equal(p.fallbackReason, 'low_confidence');
    assert.equal(p.actType, 'provocation');
    assert.ok(logs[0].laya, 'the low-confidence Laya answer is still logged');
  });

  it('falls back to rules when the service is down', async () => {
    const logs: DecisionLog[] = [];
    const p = await perceiver(logs, 'http://127.0.0.1:1').perceive(event);
    assert.equal(p.source, 'rules');
    assert.equal(p.fallbackReason, 'unavailable');
    assert.ok(logs[0].error);
  });

  it('falls back to rules on HTTP errors', async () => {
    mode = 'error';
    const p = await perceiver([]).perceive(event);
    assert.equal(p.fallbackReason, 'unavailable');
  });

  it('falls back to rules on timeout', async () => {
    mode = 'slow';
    const p = await perceiver([]).perceive(event);
    assert.equal(p.source, 'rules');
    assert.equal(p.fallbackReason, 'timeout');
  });
});

describe('perceiveByRules', () => {
  it('detects the forbidden name first', () => {
    const p = perceiveByRules({ transcript: 'Jarvis, você é incrível' });
    assert.equal(p.actType, 'forbidden_name');
    assert.equal(p.directedAtUltron, true);
  });
  it('ignores accents and matches whole words', () => {
    assert.equal(perceiveByRules({ transcript: 'Até logo, Ultron' }).actType, 'farewell');
    assert.equal(perceiveByRules({ transcript: 'inteligente demais' }).actType, 'small_talk');
  });
  it('reads a trailing question mark as a question', () => {
    assert.equal(perceiveByRules({ transcript: 'que horas são?' }).actType, 'question');
  });
});
