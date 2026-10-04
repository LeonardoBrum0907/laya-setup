// Prosody: cheap numbers about HOW something was said, measured from the raw audio.
// v1 only logs them next to each decision; they are not sent to Laya (the trained schema has no
// voice fields yet). Once enough real utterances are logged, they become the data for a v2 schema.
// No models, no dependencies: RMS loudness, autocorrelation pitch, pauses and speaking rate.

export type Prosody = {
  durationMs: number;
  /** Mean loudness of voiced frames, dBFS (0 = full scale, more negative = quieter). */
  rmsDb: number;
  /** Loudest frame, dBFS. */
  peakDb: number;
  /** Median pitch of voiced frames, Hz; null when nothing voiced was found. */
  pitchHz: number | null;
  /** Pitch spread: interquartile range in semitones. Flat delivery is low, lively is high. */
  pitchRangeSt: number | null;
  /** Fraction of frames with voice. */
  voicedRatio: number;
  longestPauseMs: number;
  /** Words per second of voiced time, when a transcript is given. */
  wordsPerSec: number | null;
};

export type ProsodyLabels = {
  volume: 'baixo' | 'normal' | 'alto';
  ritmo: 'lento' | 'normal' | 'rapido';
  tom: 'plano' | 'normal' | 'variado';
};

/** The speaker's usual values; labels are relative to these, not absolute. */
export type ProsodyBaseline = { rmsDb: number; wordsPerSec: number; pitchRangeSt: number };

export const DEFAULT_BASELINE: ProsodyBaseline = { rmsDb: -26, wordsPerSec: 3, pitchRangeSt: 3 };

const FRAME_MS = 40;
const HOP_MS = 20;
const MIN_HZ = 75;
const MAX_HZ = 400;
const SILENCE_DB = -45;

const toDb = (x: number) => (x > 0 ? 20 * Math.log10(x) : -120);
const round = (x: number, d = 1) => Number(x.toFixed(d));

function quantile(sorted: number[], q: number): number {
  const pos = (sorted.length - 1) * q;
  const lo = Math.floor(pos);
  const hi = Math.ceil(pos);
  return sorted[lo] + (sorted[hi] - sorted[lo]) * (pos - lo);
}

/** Normalized autocorrelation pitch of one frame, or null when it is not clearly periodic. */
function framePitch(frame: Float32Array, sampleRate: number): number | null {
  const minLag = Math.floor(sampleRate / MAX_HZ);
  const maxLag = Math.min(Math.ceil(sampleRate / MIN_HZ), frame.length - 1);
  let best = 0;
  let bestLag = 0;
  for (let lag = minLag; lag <= maxLag; lag++) {
    let num = 0;
    let e1 = 0;
    let e2 = 0;
    for (let i = 0; i + lag < frame.length; i++) {
      num += frame[i] * frame[i + lag];
      e1 += frame[i] * frame[i];
      e2 += frame[i + lag] * frame[i + lag];
    }
    const r = num / (Math.sqrt(e1 * e2) || 1);
    if (r > best) {
      best = r;
      bestLag = lag;
    }
  }
  return best > 0.6 && bestLag > 0 ? sampleRate / bestLag : null;
}

/** Converts 16-bit PCM (what most capture and STT pipelines hand around) to floats in -1..1. */
export function pcm16ToFloat(pcm: Int16Array): Float32Array {
  const out = new Float32Array(pcm.length);
  for (let i = 0; i < pcm.length; i++) out[i] = pcm[i] / 32768;
  return out;
}

/** Measures one utterance: mono samples in -1..1. */
export function measureProsody(samples: Float32Array, sampleRate: number, transcript?: string): Prosody {
  const frameLen = Math.round((sampleRate * FRAME_MS) / 1000);
  const hop = Math.round((sampleRate * HOP_MS) / 1000);
  const rms: number[] = [];
  const pitches: number[] = [];
  let voiced = 0;
  let frames = 0;
  let pause = 0;
  let longestPause = 0;
  for (let start = 0; start + frameLen <= samples.length; start += hop) {
    const frame = samples.subarray(start, start + frameLen);
    let sum = 0;
    for (let i = 0; i < frame.length; i++) sum += frame[i] * frame[i];
    const db = toDb(Math.sqrt(sum / frame.length));
    frames++;
    if (db < SILENCE_DB) {
      pause++;
      longestPause = Math.max(longestPause, pause);
      continue;
    }
    pause = 0;
    voiced++;
    rms.push(db);
    const f0 = framePitch(frame, sampleRate);
    if (f0 !== null) pitches.push(f0);
  }
  const voicedSec = (voiced * HOP_MS) / 1000;
  const words = transcript?.trim() ? transcript.trim().split(/\s+/).length : 0;
  let pitchHz: number | null = null;
  let pitchRangeSt: number | null = null;
  if (pitches.length >= 3) {
    const sorted = [...pitches].sort((a, b) => a - b);
    pitchHz = round(quantile(sorted, 0.5));
    pitchRangeSt = round(12 * Math.log2(quantile(sorted, 0.75) / quantile(sorted, 0.25)), 2);
  }
  return {
    durationMs: Math.round((samples.length / sampleRate) * 1000),
    rmsDb: rms.length ? round(rms.reduce((a, b) => a + b, 0) / rms.length) : -120,
    peakDb: rms.length ? round(Math.max(...rms)) : -120,
    pitchHz,
    pitchRangeSt,
    voicedRatio: frames ? round(voiced / frames, 2) : 0,
    longestPauseMs: longestPause * HOP_MS,
    wordsPerSec: words && voicedSec > 0 ? round(words / voicedSec, 2) : null,
  };
}

/** Coarse labels relative to the speaker's baseline: the shape a v2 Laya state would carry. */
export function describeProsody(p: Prosody, baseline: ProsodyBaseline = DEFAULT_BASELINE): ProsodyLabels {
  const loud = p.rmsDb - baseline.rmsDb;
  const rate = p.wordsPerSec === null ? 1 : p.wordsPerSec / baseline.wordsPerSec;
  const range = p.pitchRangeSt === null ? 1 : p.pitchRangeSt / baseline.pitchRangeSt;
  return {
    volume: loud >= 6 ? 'alto' : loud <= -6 ? 'baixo' : 'normal',
    ritmo: rate >= 1.3 ? 'rapido' : rate <= 0.7 ? 'lento' : 'normal',
    tom: range <= 0.5 ? 'plano' : range >= 1.6 ? 'variado' : 'normal',
  };
}

/** Learns the speaker's baseline from logged utterances (median of each measure). */
export function fitBaseline(samples: Prosody[], fallback: ProsodyBaseline = DEFAULT_BASELINE): ProsodyBaseline {
  const present = (xs: (number | null)[]) => xs.filter((x): x is number => x !== null);
  const median = (xs: number[], d: number) => (xs.length ? quantile([...xs].sort((a, b) => a - b), 0.5) : d);
  return {
    rmsDb: round(median(samples.filter((s) => s.rmsDb > -120).map((s) => s.rmsDb), fallback.rmsDb)),
    wordsPerSec: round(median(present(samples.map((s) => s.wordsPerSec)), fallback.wordsPerSec), 2),
    pitchRangeSt: round(median(present(samples.map((s) => s.pitchRangeSt)), fallback.pitchRangeSt), 2),
  };
}
