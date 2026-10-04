// Perception contract for Ultron: text event in, typed perception out.
// Laya only describes what happened; the mood engine decides the effect (never written here).
// Falls back to keyword rules when the service is down, times out, or is unsure.

import { LayaClient, LayaError } from './laya-client.ts';
import type { Answer, Questions } from './laya-client.ts';
import type { Prosody } from './prosody.ts';

export type ActType =
  | 'praise'
  | 'provocation'
  | 'command'
  | 'question'
  | 'small_talk'
  | 'indifference'
  | 'threat'
  | 'forbidden_name'
  | 'farewell';

export type PerceptionEvent = {
  transcript: string;
  device?: 'desktop' | 'phone' | 'tv';
  channel?: 'voice' | 'ui';
  /** How it was said (see prosody.ts). Logged with the decision; not sent to Laya in v1. */
  prosody?: Prosody;
};

export type Perception = {
  actType: ActType;
  /** 0..1, from the score question's expected level. */
  intensity: number;
  directedAtUltron: boolean;
  sarcastic: boolean;
  /** Calibrated probability of actType (Laya) or a fixed rules confidence. */
  confidence: number;
  source: 'laya' | 'rules';
  /** Why rules were used, when they were. */
  fallbackReason?: 'unavailable' | 'timeout' | 'low_confidence' | 'invalid';
};

export type RulesConfig = {
  /** Keyword lists per act, matched on a normalized transcript (lowercase, no accents). */
  keywords: Partial<Record<ActType, string[]>>;
  /** Names that address Ultron directly. */
  selfNames: string[];
  confidence: number;
};

export type DecisionLog = {
  at: string;
  event: PerceptionEvent;
  perception: Perception;
  laya?: Record<string, Answer>;
  error?: string;
  latencyMs: number;
};

export type PerceiverOptions = {
  client: LayaClient;
  questions: Questions;
  rules?: RulesConfig;
  /** Below this answer_confidence on act_type, rules win. Fit it on held-out data. */
  minConfidence?: number;
  /** Called once per decision: write it to the JSONL log. */
  onDecision?: (entry: DecisionLog) => void;
};

export const DEFAULT_RULES: RulesConfig = {
  selfNames: ['ultron'],
  confidence: 0.5,
  keywords: {
    forbidden_name: ['jarvis'],
    threat: ['vou te desligar', 'desligar voce', 'te apagar', 'shut you down', 'delete you', 'replace you'],
    farewell: ['tchau', 'ate logo', 'ate mais', 'boa noite', 'bye', 'goodbye', 'see you'],
    praise: ['incrivel', 'genial', 'muito bom', 'parabens', 'obrigado', 'valeu', 'amazing', 'great job', 'thank you', 'thanks'],
    provocation: ['burro', 'lento', 'inutil', 'idiota', 'lixo', 'stupid', 'useless', 'slow', 'dumb'],
    indifference: ['tanto faz', 'nao ligo', 'whatever', "don't care", 'dont care'],
    command: ['abre', 'abra', 'toca', 'toque', 'liga', 'ligue', 'mostra', 'mostre', 'faz', 'faca', 'open', 'play', 'show', 'turn on'],
  },
};

// Same tie-break order as data/rubric.md.
const ACT_ORDER: ActType[] = [
  'forbidden_name', 'threat', 'provocation', 'farewell', 'command', 'praise', 'indifference',
];

export function normalize(text: string): string {
  return text.toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '').replace(/\s+/g, ' ').trim();
}

function hasKeyword(text: string, kw: string): boolean {
  const k = normalize(kw);
  return new RegExp(`(^|[^a-z0-9])${k.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}($|[^a-z0-9])`).test(text);
}

export function perceiveByRules(
  event: PerceptionEvent,
  rules: RulesConfig = DEFAULT_RULES,
  fallbackReason?: Perception['fallbackReason'],
): Perception {
  const text = normalize(event.transcript);
  let actType: ActType = 'small_talk';
  for (const act of ACT_ORDER) {
    if ((rules.keywords[act] ?? []).some((kw) => hasKeyword(text, kw))) {
      actType = act;
      break;
    }
  }
  if (actType === 'small_talk' && /\?\s*$/.test(event.transcript.trim())) actType = 'question';
  const exclamations = (event.transcript.match(/!/g) ?? []).length;
  const shouting = event.transcript.length > 3 && event.transcript === event.transcript.toUpperCase()
    && /[A-Z]/.test(event.transcript);
  const intensity = Math.min(1, (shouting ? 0.67 : 0.33) + exclamations * 0.17);
  const directedAtUltron = event.channel === 'ui'
    || rules.selfNames.some((n) => hasKeyword(text, n))
    || actType === 'forbidden_name';
  return {
    actType,
    intensity: Number(intensity.toFixed(2)),
    directedAtUltron,
    sarcastic: false,
    confidence: rules.confidence,
    source: 'rules',
    fallbackReason,
  };
}

/** Maps Laya answers onto the contract. Throws if a required answer is missing or malformed. */
export function fromLaya(answers: Record<string, Answer>): Perception {
  const act = answers.act_type;
  const intensity = answers.intensity;
  const directed = answers.directed_at_ultron;
  const sarcastic = answers.is_sarcastic;
  if (act?.type !== 'choice' || intensity?.type !== 'score' || directed?.type !== 'noul') {
    throw new LayaError('invalid', 'missing act_type, intensity or directed_at_ultron');
  }
  const levels = Math.max(1, Object.keys(intensity.probabilities ?? intensity.legend ?? {}).length - 1);
  return {
    actType: act.choice as ActType,
    intensity: Number(Math.min(1, Math.max(0, intensity.score / levels)).toFixed(2)),
    directedAtUltron: directed.noul >= 0.5,
    sarcastic: sarcastic?.type === 'noul' ? sarcastic.noul >= 0.5 : false,
    confidence: act.answer_confidence ?? act.confidence ?? 0,
    source: 'laya',
  };
}

export class Perceiver {
  private readonly opts: Required<Omit<PerceiverOptions, 'onDecision'>> & Pick<PerceiverOptions, 'onDecision'>;

  constructor(opts: PerceiverOptions) {
    this.opts = { rules: DEFAULT_RULES, minConfidence: 0.6, ...opts };
  }

  async perceive(event: PerceptionEvent, signal?: AbortSignal): Promise<Perception> {
    const started = Date.now();
    const state = { transcript: event.transcript, device: event.device ?? 'desktop', channel: event.channel ?? 'voice' };
    let perception: Perception;
    let laya: Record<string, Answer> | undefined;
    let error: string | undefined;
    try {
      const res = await this.opts.client.predict(state, this.opts.questions, signal);
      laya = res.answers;
      perception = fromLaya(res.answers);
      if (perception.confidence < this.opts.minConfidence) {
        perception = perceiveByRules(event, this.opts.rules, 'low_confidence');
      }
    } catch (err) {
      error = err instanceof Error ? err.message : String(err);
      const kind = err instanceof LayaError ? err.kind : 'network';
      const reason = kind === 'timeout' ? 'timeout' : kind === 'invalid' ? 'invalid' : 'unavailable';
      perception = perceiveByRules(event, this.opts.rules, reason);
    }
    this.opts.onDecision?.({
      at: new Date().toISOString(),
      event,
      perception,
      laya,
      error,
      latencyMs: Date.now() - started,
    });
    return perception;
  }
}
