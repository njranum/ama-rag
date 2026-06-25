import { expect, it } from "vitest";

import { groupByTitle } from "./sources";
import type { Source } from "./types";

const src = (title: string, text: string, url: string | null = null): Source => ({
  title,
  text,
  url,
  anchor: null,
});

it("collapses multiple chunks of the same page into one card (lead chunk wins)", () => {
  const grouped = groupByTitle([src("A", "first"), src("A", "second"), src("B", "b")]);
  expect(grouped.map((g) => g.title)).toEqual(["A", "B"]);
  expect(grouped[0].text).toBe("first"); // best-match-first chunk represents the group
});

it("preserves best-first order and uniqueness", () => {
  const grouped = groupByTitle([src("B", "b"), src("A", "a"), src("B", "b2")]);
  expect(grouped.map((g) => g.title)).toEqual(["B", "A"]);
});

it("is empty for no sources", () => {
  expect(groupByTitle([])).toEqual([]);
});
