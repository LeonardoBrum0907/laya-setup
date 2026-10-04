// Reads one state JSON per line on stdin, prints the rules fallback as Laya-shaped answers.
// Used by scripts/eval.py to compare rules against Laya on the same questions.

import { perceiveByRules } from '../src/perception.ts';

let input = '';
process.stdin.setEncoding('utf8');
for await (const chunk of process.stdin) input += chunk;

for (const line of input.split('\n')) {
  if (!line.trim()) continue;
  const state = JSON.parse(line);
  const p = perceiveByRules({ transcript: state.transcript, device: state.device, channel: state.channel });
  const level = Math.round(p.intensity * 3);
  console.log(JSON.stringify({
    act_type: { type: 'choice', choice: p.actType, answer_confidence: p.confidence },
    intensity: { type: 'score', score: level, probabilities: { [level]: 1 } },
    directed_at_ultron: { type: 'noul', noul: p.directedAtUltron ? 1 : 0 },
    is_sarcastic: { type: 'noul', noul: p.sarcastic ? 1 : 0 },
  }));
}
