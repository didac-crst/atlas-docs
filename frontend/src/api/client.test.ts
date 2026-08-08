import { describe, expect, it } from "vitest";
import { filterConcepts } from "../api/client";

describe("filterConcepts", () => {
  const concepts = [
    { code: "germany", name: "Germany" },
    { code: "spain", name: "Spain" },
    { code: "alice", name: "Alice" },
  ];

  it("returns all concepts for empty query", () => {
    expect(filterConcepts(concepts, "")).toHaveLength(3);
  });

  it("filters by name and code case-insensitively", () => {
    expect(filterConcepts(concepts, "ger")).toEqual([{ code: "germany", name: "Germany" }]);
    expect(filterConcepts(concepts, "ALI")).toEqual([{ code: "alice", name: "Alice" }]);
  });
});
