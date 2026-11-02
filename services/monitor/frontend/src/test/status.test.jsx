import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { Status } from "../components/Status";
import { STATUSES } from "../types/monitoring";

// Plain-Thai words for a non-technical reader (project owner 2026-10-05); the raw code stays internal.
const LABEL = { PASS: "ผ่าน", FAIL: "ไม่ผ่าน", REVIEW: "รอตรวจทาน", "N/A": "ไม่เกี่ยวข้อง" };

describe("Status", () => {
  it.each(STATUSES)("%s has a Thai text label, the raw code as data-status, and an icon", (s) => {
    render(<Status status={s} />);
    const el = screen.getByTestId("status");
    expect(el).toHaveTextContent(LABEL[s]);
    expect(el).toHaveAttribute("data-status", s);
    expect(el.querySelector("svg")).not.toBeNull();
  });

  it("each status uses a distinct icon shape (not colour alone)", () => {
    const shapes = STATUSES.map((s) => {
      const { container, unmount } = render(<Status status={s} />);
      const html = container.querySelector("svg").innerHTML;
      unmount();
      return html;
    });
    expect(new Set(shapes).size).toBe(STATUSES.length);
  });
});
