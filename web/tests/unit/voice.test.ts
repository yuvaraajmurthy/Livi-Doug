import { describe, it, expect } from "vitest";
import { b64FromBuffer, pcm16ToFloat32 } from "../../src/features/voice/audio";
import { nextState, wsUrl } from "../../src/features/voice/VoiceSession";
import { mergeCaption } from "../../src/features/voice/VoiceOverlay";

describe("voice audio helpers", () => {
  it("round-trips PCM16 little-endian through base64", () => {
    const pcm = new Int16Array([0, 16384, -32768, 32767]);
    const f = pcm16ToFloat32(b64FromBuffer(pcm.buffer));
    expect(Array.from(f)).toEqual([0, 0.5, -1, 32767 / 32768]);
  });
});

describe("voice state", () => {
  it("builds the ws url from the api base", () => {
    expect(wsUrl("https://api.example.com/")).toBe("wss://api.example.com/voice/ws");
    expect(wsUrl("http://localhost:8000")).toBe("ws://localhost:8000/voice/ws");
  });

  it("follows the conversation turn by turn", () => {
    let s = nextState("connecting", { type: "ready" });
    expect(s).toBe("listening");
    s = nextState(s, { type: "transcript", role: "user", text: "hi", final: true });
    expect(s).toBe("thinking");
    s = nextState(s, { type: "audio", data: "" });
    expect(s).toBe("speaking");
    s = nextState(s, { type: "barge_in" });
    expect(s).toBe("listening");
    expect(nextState("error", { type: "end" })).toBe("error");
    expect(nextState("speaking", { type: "end" })).toBe("ended");
    expect(nextState("listening", { type: "ping" })).toBe("listening");
  });
});

describe("captions", () => {
  it("extends an open line, closes it on final, keeps two lines", () => {
    let cs = mergeCaption([], "user", "any", false);
    cs = mergeCaption(cs, "user", "thing", false);
    expect(cs).toEqual([{ role: "user", text: "anything", done: false }]);
    cs = mergeCaption(cs, "user", "anything free?", true);
    cs = mergeCaption(cs, "assistant", "Yes.", true);
    cs = mergeCaption(cs, "user", "where?", true);
    expect(cs.map(c => c.text)).toEqual(["Yes.", "where?"]);
  });
});
