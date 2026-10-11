import { it, expect } from "vitest";
import { session, sessionFromToken } from "../../src/session/session";

it("parses a sandbox token without a network call", () => {
  const s = sessionFromToken("v1.andre.sbAbc123.sig");
  expect(s).toMatchObject({ persona: "andre", sandbox: true, role: "student" });
});

it("parses a staff token and rejects junk", () => {
  expect(sessionFromToken("v1.staff.xyz.sig")?.role).toBe("staff");
  expect(sessionFromToken("not-a-token")).toBeNull();
});

it("persists to sessionStorage and notifies subscribers", () => {
  let n = 0;
  const off = session.subscribe(() => n++);
  session.set(sessionFromToken("v1.priya.p1.sig"));
  expect(session.token()).toBe("v1.priya.p1.sig");
  expect(JSON.parse(sessionStorage.getItem("compass.session")!).persona).toBe("priya");
  session.clear();
  expect(session.token()).toBeNull();
  expect(n).toBe(2);
  off();
});
