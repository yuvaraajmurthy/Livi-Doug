import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useCallback, useEffect, useRef, useState } from "react";
import { api, type CommitResponse, type CrisisResponse, type SupportCard } from "../../api/client";
import { signal } from "../../api/inspector";
import { plans } from "../plan/plans";
import { streamChat } from "./sse";
import type { ChatMessage, EventChip, UIEvent } from "./types";

let seq = 0;
const nextId = (p: string) => `${p}-${Date.now()}-${++seq}`;

function toBlock(ev: { event: string; data: unknown }): UIEvent | null {
  switch (ev.event) {
    case "events":
      return { type: "events", items: (ev.data as { items: EventChip[] }).items };
    case "plan":
      return { type: "plan", plan: ev.data as CommitResponse };
    case "memory":
      return { type: "memory", ...(ev.data as { id: string; statement: string; kind: string }) };
    case "memory_removed":
      return { type: "memory_removed", id: (ev.data as { id: string }).id };
    case "support":
      return { type: "support", card: ev.data as SupportCard };
    default:
      return null;
  }
}

export function useChat() {
  const qc = useQueryClient();
  const history = useQuery({ queryKey: ["chat-history"], queryFn: api.chatHistory, staleTime: Infinity });
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [busy, setBusy] = useState(false);
  const [crisis, setCrisis] = useState<CrisisResponse | null>(null);
  const conv = useRef<string | null>(null);
  const loaded = useRef(false);
  const abort = useRef<AbortController | null>(null);

  useEffect(() => {
    if (!history.data || loaded.current) return;
    loaded.current = true;
    conv.current = history.data.conversation_id;
    setMessages(
      history.data.messages.map(m => ({ id: `h-${m.id}`, role: m.role, text: m.text, blocks: m.blocks ?? [], at: m.at })),
    );
  }, [history.data]);

  useEffect(() => () => abort.current?.abort(), []);

  const patch = (id: string, f: (m: ChatMessage) => ChatMessage) =>
    setMessages(ms => ms.map(m => (m.id === id ? f(m) : m)));

  const send = useCallback(
    async (raw: string) => {
      const text = raw.trim();
      if (!text || busy) return;
      setBusy(true);
      const uid = nextId("u");
      const aid = nextId("a");
      setMessages(ms => [
        ...ms,
        { id: uid, role: "user", text, blocks: [] },
        { id: aid, role: "assistant", text: "", blocks: [], pending: true, status: null },
      ]);
      abort.current = new AbortController();
      try {
        await streamChat(
          { message: text, conversation_id: conv.current },
          ev => {
            if (ev.event === "meta") conv.current = ev.data.conversation_id;
            else if (ev.event === "status") patch(aid, m => ({ ...m, status: ev.data.text }));
            else if (ev.event === "delta") patch(aid, m => ({ ...m, text: m.text + ev.data.text, status: null }));
            else if (ev.event === "crisis") {
              // never echo what was typed: drop both turns and show the fixed card
              setMessages(ms => ms.filter(m => m.id !== uid && m.id !== aid));
              setCrisis(ev.data);
            } else if (ev.event === "done") {
              patch(aid, m => ({ ...m, pending: false, status: null, source: ev.data.source === "rule" ? undefined : ev.data.source }));
              signal("chat:answered");
            } else if (ev.event === "error") {
              patch(aid, m => ({ ...m, pending: false, status: null, text: m.text || ev.data.message }));
            } else {
              const block = toBlock(ev);
              if (!block) return;
              if (block.type === "plan") {
                plans.add(block.plan);
                signal("commitment:created", block.plan);
                signal("reminder:set");
              }
              if (block.type === "events") signal("chat:events", block.items);
              if (block.type === "memory" || block.type === "memory_removed") void qc.invalidateQueries({ queryKey: ["memory"] });
              patch(aid, m => ({ ...m, blocks: [...m.blocks, block], status: null }));
            }
          },
          abort.current.signal,
        );
      } catch (e) {
        patch(aid, m => ({ ...m, pending: false, status: null, text: m.text || (e as Error).message }));
      } finally {
        setMessages(ms => ms.map(m => (m.id === aid && m.pending ? { ...m, pending: false, status: null } : m)));
        setBusy(false);
      }
    },
    [busy, qc],
  );

  const newChat = useCallback(async () => {
    if (busy) return;
    const r = await api.chatNew();
    conv.current = r.conversation_id;
    setMessages([]);
  }, [busy]);

  return { messages, busy, send, newChat, crisis, clearCrisis: () => setCrisis(null), loading: history.isPending };
}
