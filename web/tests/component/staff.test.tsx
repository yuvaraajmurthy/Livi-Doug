import { describe, it, expect, beforeEach } from "vitest";
import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { server } from "../setup";
import { API, fixture, renderAt, setupPersona } from "../helpers";
import { StaffApp } from "../../src/features/staff/StaffApp";

function staffHandlers(over: Record<string, unknown> = {}) {
  const j = (name: string) => () => HttpResponse.json(over[name] ?? fixture("staff", name));
  return [
    http.get(`${API}/staff/funnel`, j("staff_funnel")),
    http.get(`${API}/staff/gaps`, j("staff_gaps")),
    http.get(`${API}/staff/weekly`, j("staff_weekly")),
    http.get(`${API}/staff/dips`, j("staff_dips")),
    http.get(`${API}/staff/retakes`, j("staff_retakes")),
  ];
}

describe("Staff Pulse", () => {
  beforeEach(() => {
    setupPersona("staff");
    server.use(...staffHandlers());
  });

  it("states scope and suppression up front", async () => {
    renderAt(<StaffApp />, "/staff", "/staff/*");
    expect(await screen.findByText(/groups under 10 hidden by the database/i)).toBeInTheDocument();
    expect(screen.getByText(/Synthetic semester/)).toBeInTheDocument();
  });

  it("renders hidden groups as 'Under 10', never as numbers", async () => {
    const f = fixture("staff", "staff_funnel");
    f.suppressed_groups = 3;
    server.use(...staffHandlers({ staff_funnel: f }));
    renderAt(<StaffApp />, "/staff", "/staff/*");
    const hidden = await screen.findAllByText("Under 10");
    expect(hidden).toHaveLength(3);
    for (const h of hidden) expect(h.closest("[data-suppressed]")?.textContent?.replace("Under 10", "")).not.toMatch(/\d/);
    expect(screen.getByText(/3 groups hidden/)).toBeInTheDocument();
  });

  it("calls out the Camden financial gap against Newark", async () => {
    renderAt(<StaffApp />, "/staff/gaps", "/staff/*");
    const callout = await screen.findByTestId("gap-callout");
    expect(callout).toHaveTextContent("Camden");
    expect(callout).toHaveTextContent("20.5");
    expect(callout).toHaveTextContent("Newark");
    expect(callout).toHaveTextContent("14.9");
  });

  it("every chart has a table equivalent", async () => {
    renderAt(<StaffApp />, "/staff/trends", "/staff/*");
    const fig = await screen.findByRole("figure", { name: /Weekly average/i });
    expect(within(fig).getByRole("table")).toBeInTheDocument();
  });

  it("shows the SQL behind an answer", async () => {
    server.use(
      http.post(`${API}/staff/ask`, () =>
        HttpResponse.json({
          synthetic: true,
          now: "2026-10-12T09:00:00-04:00",
          ok: true,
          message: "Camden has the fewest financial resources per student.",
          sql: "SELECT campus, low_students_per_item FROM staff_gaps(NULL,NULL,NULL,NULL,NULL)",
          columns: ["campus", "low_students_per_item"],
          rows: [{ campus: "camden", low_students_per_item: 20.5 }],
        }),
      ),
    );
    renderAt(<StaffApp />, "/staff/ask", "/staff/*");
    await userEvent.type(await screen.findByRole("textbox", { name: /Ask the data/ }), "where is financial supply thinnest?");
    await userEvent.click(screen.getByRole("button", { name: "Ask" }));
    expect(await screen.findByText(/SELECT campus, low_students_per_item/)).toBeInTheDocument();
    expect(screen.getByRole("cell", { name: "20.5" })).toBeInTheDocument();
  });
});
