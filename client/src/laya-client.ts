// Minimal typed HTTP client for a local laya-serve (POST /v1/systemone).
// No dependencies: uses the global fetch available in Node 18+ and browsers.

export type ChoiceQuestion = {
  type: 'choice';
  instructions: string;
  criteria: Record<string, string>;
};
export type ScoreQuestion = { type: 'score'; instructions: string; criteria: string[] };
export type NoulQuestion = {
  type: 'noul';
  instructions: string;
  criteria?: { false: string; true: string };
};
export type Question = ChoiceQuestion | ScoreQuestion | NoulQuestion;
export type Questions = Record<string, Question>;

type AnswerBase = {
  probabilities?: Record<string, number>;
  confidence?: number;
  /** Probability of the reported answer: the calibrated value to gate on. */
  answer_confidence?: number;
  low_confidence?: boolean;
};
export type ChoiceAnswer = AnswerBase & { type: 'choice'; choice: string };
export type ScoreAnswer = AnswerBase & {
  type: 'score';
  score: number;
  legend?: Record<string, string>;
};
export type NoulAnswer = AnswerBase & { type: 'noul'; noul: number };
export type Answer = ChoiceAnswer | ScoreAnswer | NoulAnswer;

export type LayaResponse = {
  answers: Record<string, Answer>;
  routing?: { model?: string; reason?: string };
  usage?: { input_tokens: number; output_tokens: number };
};

export type LayaClientOptions = {
  baseUrl?: string;
  apiKey?: string;
  /** Abort the request after this many ms. Perception must stay inside the 2 s reply budget. */
  timeoutMs?: number;
  /** Checkpoint to force: english | multilingual | typed-decisions. Omit to let the router pick. */
  model?: string;
  fetchImpl?: typeof fetch;
};

export class LayaError extends Error {
  readonly kind: 'timeout' | 'network' | 'http' | 'invalid';
  readonly status?: number;
  constructor(kind: LayaError['kind'], message: string, status?: number) {
    super(message);
    this.name = 'LayaError';
    this.kind = kind;
    this.status = status;
  }
}

export class LayaClient {
  readonly baseUrl: string;
  readonly timeoutMs: number;
  private readonly apiKey?: string;
  private readonly model?: string;
  private readonly fetchImpl: typeof fetch;

  constructor(opts: LayaClientOptions = {}) {
    this.baseUrl = (opts.baseUrl ?? 'http://127.0.0.1:8000').replace(/\/+$/, '');
    this.timeoutMs = opts.timeoutMs ?? 300;
    this.apiKey = opts.apiKey;
    this.model = opts.model;
    this.fetchImpl = opts.fetchImpl ?? fetch;
  }

  async predict(
    state: string | Record<string, unknown>,
    questions: Questions,
    signal?: AbortSignal,
  ): Promise<LayaResponse> {
    const body: Record<string, unknown> = { state, questions };
    if (this.model) body.model = this.model;
    const json = await this.request('/v1/systemone', body, signal);
    if (!json || typeof json !== 'object' || typeof (json as LayaResponse).answers !== 'object') {
      throw new LayaError('invalid', 'response has no answers object');
    }
    return json as LayaResponse;
  }

  async health(): Promise<boolean> {
    try {
      const res = await this.fetchImpl(`${this.baseUrl}/health`, {
        headers: this.headers(),
        signal: AbortSignal.timeout(this.timeoutMs),
      });
      return res.ok;
    } catch {
      return false;
    }
  }

  private headers(): Record<string, string> {
    const h: Record<string, string> = { 'content-type': 'application/json' };
    if (this.apiKey) h.authorization = `Bearer ${this.apiKey}`;
    return h;
  }

  private async request(path: string, body: unknown, signal?: AbortSignal): Promise<unknown> {
    const timeout = AbortSignal.timeout(this.timeoutMs);
    const combined = signal ? AbortSignal.any([signal, timeout]) : timeout;
    let res: Response;
    try {
      res = await this.fetchImpl(`${this.baseUrl}${path}`, {
        method: 'POST',
        headers: this.headers(),
        body: JSON.stringify(body),
        signal: combined,
      });
    } catch (err) {
      if (timeout.aborted) throw new LayaError('timeout', `no answer within ${this.timeoutMs} ms`);
      throw new LayaError('network', err instanceof Error ? err.message : String(err));
    }
    if (!res.ok) {
      const text = await res.text().catch(() => '');
      throw new LayaError('http', `HTTP ${res.status}: ${text.slice(0, 200)}`, res.status);
    }
    try {
      return await res.json();
    } catch {
      throw new LayaError('invalid', 'response is not JSON');
    }
  }
}
