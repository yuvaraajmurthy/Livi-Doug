import { describe, it, expect, beforeEach } from "vitest";
import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { server } from "../setup";
import { API, fixture, renderAt, setupPersona } from "../helpers";
import { FocusFlow } from "../../src/features/focus/FocusFlow";

describe("Focus flow", () => {
  beforeEach(() => setupPersona("andre"));

  it("starts with strengths, then lets the student pick one area and barriers", async () => {
    const user = userEvent.setup();
    renderAt(<FocusFlow />, "/focus");
    expect(await screen.findByText("Here's what's going well.")).toBeInTheDocument();
    expect(screen.getByText("Spiritual")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Choose one area to work on" }));

    const social = await screen.findByRole("button", { name: /Social/ });
    expect(social).toHaveAttribute("aria-pressed", "false"); // suggested, not pre-selected
    const cont = screen.getByRole("button", { name: "Continue" });
    expect(cont).toBeDisabled();
    await user.click(social);
    expect(social).toHaveAttribute("aria-pressed", "true");
    await user.click(cont);

    const a = await screen.findByRole("button", { name: /No time between class and work/ });
    const b = screen.getByRole("button", { name: /I don't know anyone/ });
    await user.click(a);
    await user.click(b);
    expect(a).toHaveAttribute("aria-pressed", "true");
    expect(b).toHaveAttribute("aria-pressed", "true");
  });

  it("shows the crisis screen and never echoes what was typed", async () => {
    const user = userEvent.setup();
    server.use(http.post(`${API}/me/focus`, () => HttpResponse.json(fixture("andre", "me_focus_crisis"))));
    renderAt(<FocusFlow />, "/focus");
    await user.click(await screen.findByRole("button", { name: "Choose one area to work on" }));
    await user.click(await screen.findByRole("button", { name: /Emotional/ }));
    await user.click(screen.getByRole("button", { name: "Continue" }));
    const words = "everything feels pointless lately";
    await user.type(await screen.findByLabelText(/In your own words/), words);
    await user.click(screen.getByRole("button", { name: "Find my step" }));
    expect(await screen.findByRole("heading", { name: "You don't have to handle this alone" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /988/ })).toHaveAttribute("href", "tel:988");
    expect(screen.getByRole("link", { name: /741741/ })).toHaveAttribute("href", "sms:741741?&body=HOME");
    expect(document.body.textContent).not.toContain(words);
  });
});
