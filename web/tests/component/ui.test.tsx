import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router";
import { useState } from "react";
import { Button } from "../../src/ui/Button";
import { Sheet } from "../../src/ui/Sheet";
import { TabBar } from "../../src/ui/TabBar";
import { SourceBadge } from "../../src/ui/Badge";
import { Chip } from "../../src/ui/Chip";

describe("Button", () => {
  it("is busy and disabled while loading, and does not fire clicks", async () => {
    const onClick = vi.fn();
    render(<Button loading onClick={onClick}>I'm in</Button>);
    const b = screen.getByRole("button", { name: /I'm in/ });
    expect(b).toBeDisabled();
    expect(b).toHaveAttribute("aria-busy", "true");
    await userEvent.click(b);
    expect(onClick).not.toHaveBeenCalled();
  });
});

describe("Chip", () => {
  it("exposes its pressed state", async () => {
    function T() {
      const [on, setOn] = useState(false);
      return <Chip selected={on} onClick={() => setOn(!on)}>I don't know anyone</Chip>;
    }
    render(<T />);
    const c = screen.getByRole("button", { name: /know anyone/ });
    expect(c).toHaveAttribute("aria-pressed", "false");
    await userEvent.click(c);
    expect(c).toHaveAttribute("aria-pressed", "true");
  });
});

describe("Sheet", () => {
  function Harness() {
    const [open, setOpen] = useState(false);
    return (
      <>
        <button onClick={() => setOpen(true)}>Open why</button>
        <Sheet open={open} onClose={() => setOpen(false)} title="Why this fits">
          <button>First</button>
          <button>Last</button>
        </Sheet>
      </>
    );
  }

  it("opens as a labelled dialog, traps focus, closes on Escape and returns focus", async () => {
    const user = userEvent.setup();
    render(<Harness />);
    const trigger = screen.getByRole("button", { name: "Open why" });
    await user.click(trigger);
    const dialog = await screen.findByRole("dialog", { name: "Why this fits" });
    expect(dialog).toBeInTheDocument();
    expect(dialog.contains(document.activeElement)).toBe(true);
    for (let i = 0; i < 5; i++) await user.tab();
    expect(dialog.contains(document.activeElement)).toBe(true);
    await user.keyboard("{Escape}");
    await vi.waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    expect(trigger).toHaveFocus();
  });
});

describe("TabBar", () => {
  it("marks the current tab", () => {
    render(
      <MemoryRouter initialEntries={["/map"]}>
        <TabBar />
      </MemoryRouter>,
    );
    expect(screen.getByRole("link", { name: /Map/ })).toHaveAttribute("aria-current", "page");
    expect(screen.getByRole("link", { name: /Today/ })).not.toHaveAttribute("aria-current");
  });
});

describe("SourceBadge", () => {
  it("labels synthetic items as samples", () => {
    render(<SourceBadge synthetic />);
    expect(screen.getByText("Sample")).toBeInTheDocument();
  });
  it("renders nothing for real items", () => {
    const { container } = render(<SourceBadge synthetic={false} />);
    expect(container).toBeEmptyDOMElement();
  });
});
