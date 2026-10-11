// Mic capture worklet: downsample from the context rate to 16 kHz, Float32 -> Int16 LE, post ~40 ms chunks + RMS level.
class PcmCapture extends AudioWorkletProcessor {
  constructor() {
    super();
    this.ratio = sampleRate / 16000;
    this.pos = 0;
    this.chunk = new Int16Array(640);
    this.n = 0;
    this.sq = 0;
  }

  process(inputs) {
    const ch = inputs[0] && inputs[0][0];
    if (!ch) return true;
    // linear-interpolation resampler, stateful across render quanta
    while (this.pos < ch.length) {
      const i = Math.floor(this.pos);
      const f = this.pos - i;
      const a = ch[i];
      const b = i + 1 < ch.length ? ch[i + 1] : a;
      const s = Math.max(-1, Math.min(1, a + (b - a) * f));
      this.chunk[this.n++] = s < 0 ? s * 0x8000 : s * 0x7fff;
      this.sq += s * s;
      if (this.n === this.chunk.length) {
        this.port.postMessage({ pcm: this.chunk.buffer.slice(0), rms: Math.sqrt(this.sq / this.n) });
        this.n = 0;
        this.sq = 0;
      }
      this.pos += this.ratio;
    }
    this.pos -= ch.length;
    return true;
  }
}

registerProcessor("pcm-capture", PcmCapture);
