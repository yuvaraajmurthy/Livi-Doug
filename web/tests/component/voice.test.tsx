import { describe, it, expect, beforeEach, vi } from "vitest";
import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClientProvider } from "@tanstack/react-query";
import { queryClient } from "../../src/app/providers";
import { fixture, setupPersona } from "../helpers";

const audio = vi.hoisted(() => ({ fail: null as null | string, sent: [] as string[] }));

vi.mock("../../src/features/voice/audio", async orig => {
  const real = await orig<typeof import("../../src/features/voice/audio")>();
  class MicCapture {
    muted = false;
    async start(onChunk: (b64: string) => void) {
      if (audio.fail) throw Object.assign(new Error("no"), { name: audio.fail });
      onChunk("AAAA");
    }
    stop() {}
  }
  class Player {
    onIdle: (() => void) | null = null;
    async unlock() {}
    play() {}
    level() {
      return 0;
    }
    stop() {}
    close() {}
  }
  return { ...real, MicCapture, Player };
});

class FakeWS {
  static OPEN = 1;
  static last: FakeWS | null = null;
  readyState = 0;
  sent: unknown[] = [];
  onopen: (() => void) | null = null;
  onmessage: ((e: { data: string }) => void) | null = null;
  onerror: (() => void) | null = null;
  onclose: (() => void) | null = null;
  constructor(public url: string) {
    FakeWS.last = this;
    queueMicrotask(() => {
      this.readyState = 1;
      this.onopen?.();
    });
  }
  send(d: string) {
    this.sent.push(JSON.parse(d));
  }
  close() {
    this.readyState = 3;
  }
  frame(f: unknown) {
    act(() => this.onmessage?.({ data: JSON.stringify(f) }));
  }
}

const { VoiceOverlay } = await import("../../src/features/voice/VoiceOverlay");

const mount = (onClose = vi.fn()) => {
  render(
    <QueryClientProvider client={queryClient}>
      <VoiceOverlay onClose={onClose} conversationId="c-1" />
    </QueryClientProvider>,
  );
  return onClose;
};

describe("VoiceOverlay", () => {
  beforeEach(() => {
    setupPersona("andre");
    audio.fail = null;
    FakeWS.last = null;
    vi.stubGlobal("WebSocket", FakeWS);
  });

  it("starts with the token and conversation, then shows captions and event chips", async () => {
    mount();
    await waitFor(() => expect(FakeWS.last?.sent[0]).toMatchObject({ type: "start", conversation_id: "c-1" }));
    const ws = FakeWS.last!;
    expect(ws.url).toBe("wss://api.test/voice/ws");
    expect((ws.sent[0] as { token: string }).token).toBeTruthy();

    ws.frame({ type: "ready" });
    expect(screen.getByRole("status")).toHaveTextContent("Listening");
    ws.frame({ type: "transcript", role: "user", text: "anything free this week?", final: true });
    expect(screen.getByRole("status")).toHaveTextContent("Thinking");
    ws.frame({
      type: "ui",
      event: {
        type: "events",
        items: [{ id: "e1", title: "Interfaith lunch", when_label: "Fri Oct 16", venue: "Robeson", cost_label: "Free", synthetic: true, kind: "event" }],
      },
    });
    ws.frame({ type: "transcript", role: "assistant", text: "There's a free lunch Friday.", final: true });
    expect(screen.getByRole("status")).toHaveTextContent("Speaking");
    expect(screen.getByText("anything free this week?")).toBeInTheDocument();
    expect(screen.getByText("There's a free lunch Friday.")).toBeInTheDocument();
    expect(document.querySelector('[data-tour="voice-event-0"]')).toHaveTextContent("Interfaith lunch");
  });

  it("explains a blocked microphone and never opens a socket", async () => {
    audio.fail = "NotAllowedError";
    mount();
    expect(await screen.findByText(/Microphone access is off/)).toBeInTheDocument();
    expect(FakeWS.last).toBeNull();
  });

  it("shows the crisis screen when the server flags a turn", async () => {
    mount();
    await waitFor(() => expect(FakeWS.last?.sent.length).toBeGreaterThan(0));
    const c = fixture("andre", "win_crisis");
    FakeWS.last!.frame({ ...c, type: "crisis" });
    expect(await screen.findByRole("heading", { name: c.title })).toBeInTheDocument();
  });

  it("ends and offers typing instead", async () => {
    const onClose = mount();
    await userEvent.click(screen.getByRole("button", { name: "Type instead" }));
    expect(onClose).toHaveBeenCalledWith(true);
    await userEvent.click(screen.getByRole("button", { name: "End voice" }));
    expect(onClose).toHaveBeenCalledTimes(2);
  });
});
