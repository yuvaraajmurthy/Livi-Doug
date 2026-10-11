// Browser audio for voice mode: mic → 16 kHz PCM16 chunks; 24 kHz PCM16 → speakers, gapless, stoppable on barge-in.

export function b64FromBuffer(buf: ArrayBuffer): string {
  const bytes = new Uint8Array(buf);
  let s = "";
  for (let i = 0; i < bytes.length; i += 0x8000) s += String.fromCharCode(...bytes.subarray(i, i + 0x8000));
  return btoa(s);
}

export function pcm16ToFloat32(b64: string): Float32Array<ArrayBuffer> {
  const bin = atob(b64);
  const n = bin.length >> 1;
  const out = new Float32Array(new ArrayBuffer(n * 4));
  for (let i = 0; i < n; i++) {
    let v = bin.charCodeAt(2 * i) | (bin.charCodeAt(2 * i + 1) << 8);
    if (v >= 0x8000) v -= 0x10000;
    out[i] = v / 0x8000;
  }
  return out;
}

export class MicCapture {
  private ctx: AudioContext | null = null;
  private stream: MediaStream | null = null;
  private node: AudioWorkletNode | null = null;
  muted = false;

  async start(onChunk: (b64: string) => void, onLevel: (rms: number) => void): Promise<void> {
    this.stream = await navigator.mediaDevices.getUserMedia({
      audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true, channelCount: 1 },
    });
    this.ctx = new AudioContext();
    await this.ctx.audioWorklet.addModule("/pcm-worklet.js");
    const src = this.ctx.createMediaStreamSource(this.stream);
    this.node = new AudioWorkletNode(this.ctx, "pcm-capture");
    this.node.port.onmessage = (e: MessageEvent<{ pcm: ArrayBuffer; rms: number }>) => {
      onLevel(this.muted ? 0 : e.data.rms);
      // muted: keep the stream flowing as silence so the model still detects the end of a turn
      onChunk(b64FromBuffer(this.muted ? new ArrayBuffer(e.data.pcm.byteLength) : e.data.pcm));
    };
    src.connect(this.node);
  }

  stop() {
    this.node?.disconnect();
    this.stream?.getTracks().forEach(t => t.stop());
    void this.ctx?.close();
    this.node = null;
    this.stream = null;
    this.ctx = null;
  }
}

export class Player {
  private ctx: AudioContext | null = null;
  private analyser: AnalyserNode | null = null;
  private sources = new Set<AudioBufferSourceNode>();
  private at = 0;
  onIdle: (() => void) | null = null;

  private ensure(): AudioContext {
    if (!this.ctx) {
      this.ctx = new AudioContext();
      this.analyser = this.ctx.createAnalyser();
      this.analyser.fftSize = 512;
      this.analyser.connect(this.ctx.destination);
    }
    return this.ctx;
  }

  /** Resume inside a user gesture (Safari/iOS autoplay rules). */
  async unlock() {
    await this.ensure().resume();
  }

  play(b64: string, sampleRate = 24000) {
    const ctx = this.ensure();
    const data = pcm16ToFloat32(b64);
    if (!data.length) return;
    const buf = ctx.createBuffer(1, data.length, sampleRate);
    buf.copyToChannel(data, 0);
    const src = ctx.createBufferSource();
    src.buffer = buf;
    src.connect(this.analyser!);
    const start = Math.max(this.at, ctx.currentTime + 0.06);
    src.start(start);
    this.at = start + buf.duration;
    this.sources.add(src);
    src.onended = () => {
      this.sources.delete(src);
      if (!this.sources.size) this.onIdle?.();
    };
  }

  get playing() {
    return this.sources.size > 0;
  }

  level(): number {
    if (!this.analyser || !this.playing) return 0;
    const a = new Uint8Array(this.analyser.fftSize);
    this.analyser.getByteTimeDomainData(a);
    let s = 0;
    for (const v of a) s += ((v - 128) / 128) ** 2;
    return Math.sqrt(s / a.length);
  }

  /** Barge-in: silence everything scheduled, immediately. */
  stop() {
    for (const s of this.sources) {
      try {
        s.stop();
      } catch {
        // already stopped
      }
    }
    this.sources.clear();
    this.at = 0;
  }

  close() {
    this.stop();
    void this.ctx?.close();
    this.ctx = null;
  }
}
