import { it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { CrisisScreen } from "../../src/features/safety/CrisisScreen";
import { fixture } from "../helpers";

it("renders every line as a real call/text link and marks unverified lines", () => {
  const c = fixture("andre", "win_crisis");
  render(<CrisisScreen crisis={c} onBack={() => {}} />);
  expect(screen.getByRole("heading", { name: c.title })).toBeInTheDocument();
  for (const line of c.lines) {
    const link = screen.getByRole("link", { name: new RegExp(line.name.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")) });
    expect(link).toHaveAttribute("href", line.href);
  }
  expect(screen.getAllByText("Verifying").length).toBe(c.lines.filter((l: { verified: boolean }) => !l.verified).length);
  expect(screen.getByRole("button", { name: "Back to Compass" })).toBeInTheDocument();
});
