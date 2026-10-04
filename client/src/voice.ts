// Prosody features from raw mono PCM, computed in the bridge next to the transcript.
// Schema ultron-v1 does not send these to Laya: they ride on the event and land in the decision
// log, so real recordings pile up for a future ultron-v2 that reads intonation (docs/entonacao.md).
// No dependencies: works on a Float32Array from Web Audio or from a decoded WAV in Node.

export type VoiceFeatures = {
  durationMs: number;
  /** Share of 30 ms frames above the speech threshold. */
  speechRatio: number;
  /** RMS level of the speech frames, dBFS (0 = full scale). */
  rmsDb: number;
  peakDb: number;
  /** Words per second of speech time; needs the transcript's word count. */
  wordsPerSecond?: number;
  /** Median and spread of the fundamental frequency over voiced frames; absent if none found. */
  pitchHz?: number;
  pitchStdHz?: number;
  /** Silences of at least 500 ms between two stretches of speech. */
  longPauses: number;
};

export type VoiceOptions = {
  /** Frames quieter than this (dBFS) count as silence. */
  silenceDb?: number;
  minPitchHz?: number;
  maxPitchHz?: number;
};

const FRAME_MS = 30;
const LONG_PAUSE_MS = 500;

const toDb = (x: number) => (x > 0 ? 20 * Math.log10(x) : -120);
const round = (x: number, digits = 1) => Number(x.toFixed(digits));

/** Pitch of one frame by autocorrelation; undefined when the frame is not clearly periodic. */
function framePitch(frame: Float32Array, sampleRate: number, minHz: number, maxHz: number): number | undefined {
  const minLag = Math.floor(sampleRate / maxHz);
  const maxLag = Math.min(frame.length - 1, Math.ceil(sampleRate / minHz));
  let energy = 0;
  for (let i = 0; i < frame.length; i++) energy += frame[i] * frame[i];
  if (energy === 0) return undefined;
  let bestLag = 0;
  let best = 0;
  for (let lag = minLag; lag <= maxLag; lag++) {
    let sum = 0;
    for (let i = 0; i + lag < frame.length; i++) sum += frame[i] * frame[i + lag];
    const r = sum / energy;
    if (r > best) {
      best = r;
      bestLag = lag;
    }
  }
  return best >= 0.5 && bestLag > 0 ? sampleRate / bestLag : undefined;
}

function median(xs: number[]): number {
  const s = [...xs].sort((a, b) => a - b);
  const m = s.length >> 1;
  return s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2;
}

export function voiceFeatures(
  samples: Float32Array,
  sampleRate: number,
  transcript?: string,
  opts: VoiceOptions = {},
): VoiceFeatures {
  const { silenceDb = -45, minPitchHz = 70, maxPitchHz = 400 } = opts;
  const frameLen = Math.max(1, Math.round((sampleRate * FRAME_MS) / 1000));
  const frames = Math.floor(samples.length / frameLen);

  let peak = 0;
  for (let i = 0; i < samples.length; i++) peak = Math.max(peak, Math.abs(samples[i]));

  let speechFrames = 0;
  let speechSq = 0;
  let longPauses = 0;
  let silentRun = 0;
  let seenSpeech = false;
  const pitches: number[] = [];
  for (let f = 0; f < frames; f++) {
    const frame = samples.subarray(f * frameLen, (f + 1) * frameLen);
    let sq = 0;
    for (let i = 0; i < frame.length; i++) sq += frame[i] * frame[i];
    const speech = toDb(Math.sqrt(sq / frame.length)) > silenceDb;
    if (speech) {
      if (seenSpeech && silentRun * FRAME_MS >= LONG_PAUSE_MS) longPauses++;
      seenSpeech = true;
      silentRun = 0;
      speechFrames++;
      speechSq += sq;
      const p = framePitch(frame, sampleRate, minPitchHz, maxPitchHz);
      if (p !== undefined) pitches.push(p);
    } else {
      silentRun++;
    }
  }

  const speechMs = speechFrames * FRAME_MS;
  const out: VoiceFeatures = {
    durationMs: Math.round((samples.length / sampleRate) * 1000),
    speechRatio: frames ? round(speechFrames / frames, 2) : 0,
    rmsDb: speechFrames ? round(toDb(Math.sqrt(speechSq / (speechFrames * frameLen)))) : -120,
    peakDb: round(toDb(peak)),
    longPauses,
  };
  const words = transcript?.trim() ? transcript.trim().split(/\s+/).length : 0;
  if (words && speechMs) out.wordsPerSecond = round(words / (speechMs / 1000), 2);
  if (pitches.length) {
    const mid = median(pitches);
    const variance = pitches.reduce((a, p) => a + (p - mid) ** 2, 0) / pitches.length;
    out.pitchHz = round(mid);
    out.pitchStdHz = round(Math.sqrt(variance));
  }
  return out;
}
