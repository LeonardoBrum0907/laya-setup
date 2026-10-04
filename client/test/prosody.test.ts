import assert from 'node:assert/strict';
import { describe, it } from 'node:test';
import { describeProsody, fitBaseline, measureProsody, pcm16ToFloat } from '../src/index.ts';

const RATE = 16000;

/** Tone segments [hz, seconds, amplitude]; hz 0 means silence. Optional vibrato in semitones. */
function synth(parts: [number, number, number][], vibratoSt = 0): Float32Array {
  const out: number[] = [];
  let phase = 0;
  for (const [hz, sec, amp] of parts) {
    for (let i = 0; i < Math.round(sec * RATE); i++) {
      const f = hz * 2 ** ((vibratoSt / 2) * Math.sin((2 * Math.PI * 2 * out.length) / RATE) / 12);
      phase += (2 * Math.PI * f) / RATE;
      out.push(hz ? amp * Math.sin(phase) : 0);
    }
  }
  return Float32Array.from(out);
}

describe('measureProsody', () => {
  it('finds pitch, loudness, pauses and speaking rate', () => {
    const p = measureProsody(synth([[150, 1, 0.1], [0, 0.6, 0], [150, 1, 0.1]]), RATE, 'abre o spotify aí agora mano');
    assert.ok(Math.abs((p.pitchHz ?? 0) - 150) < 3, `pitch ${p.pitchHz}`);
    assert.ok(Math.abs(p.rmsDb - -23) < 1, `rms ${p.rmsDb}`);
    assert.ok(p.longestPauseMs >= 500 && p.longestPauseMs <= 620, `pause ${p.longestPauseMs}`);
    assert.ok(p.pitchRangeSt !== null && p.pitchRangeSt < 0.5, 'a steady tone is flat');
    assert.ok(Math.abs((p.wordsPerSec ?? 0) - 3) < 0.3, `rate ${p.wordsPerSec}`);
  });

  it('sees a lively voice as a wider pitch range', () => {
    const flat = measureProsody(synth([[180, 2, 0.1]]), RATE);
    const lively = measureProsody(synth([[180, 2, 0.1]], 8), RATE);
    assert.ok((lively.pitchRangeSt ?? 0) > (flat.pitchRangeSt ?? 0) + 3);
  });

  it('handles silence without inventing numbers', () => {
    const p = measureProsody(new Float32Array(RATE), RATE, 'oi');
    assert.equal(p.pitchHz, null);
    assert.equal(p.wordsPerSec, null);
    assert.equal(p.voicedRatio, 0);
  });

  it('converts 16-bit PCM', () => {
    assert.deepEqual([...pcm16ToFloat(Int16Array.from([0, 16384, -32768]))], [0, 0.5, -1]);
  });
});

describe('describeProsody', () => {
  it('labels relative to the speaker baseline', () => {
    const base = measureProsody(synth([[150, 2, 0.05]]), RATE, 'um dois três quatro cinco seis');
    const shout = measureProsody(synth([[150, 1, 0.5]]), RATE, 'um dois três quatro cinco seis');
    const baseline = fitBaseline([base, base, { ...base, pitchRangeSt: null, wordsPerSec: null }]);
    assert.deepEqual(describeProsody(base, { ...baseline, pitchRangeSt: 3 }).volume, 'normal');
    const labels = describeProsody(shout, { ...baseline, pitchRangeSt: 3 });
    assert.equal(labels.volume, 'alto');
    assert.equal(labels.ritmo, 'rapido');
    assert.equal(labels.tom, 'plano');
  });
});
