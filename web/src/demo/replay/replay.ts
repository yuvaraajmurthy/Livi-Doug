// Offline replay (filled in by Task 13). Until then, replay mode fails clearly.
import type { CallLog } from "../../api/inspector";

export async function replayRequest<T>(method: string, path: string, _body?: unknown): Promise<{ data: T; call: CallLog }> {
  throw new Error(`Replay not loaded (${method} ${path})`);
}
