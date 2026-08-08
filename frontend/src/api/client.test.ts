import { describe, expect, it } from "vitest";
import {
  buildDocumentsQuery,
  filterConcepts,
  jobNeedsPolling,
  summarizeBulkResults,
} from "../api/client";

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

describe("buildDocumentsQuery", () => {
  it("keeps legacy unclassified=true when classification is omitted", () => {
    expect(buildDocumentsQuery({ page: 2, unclassified: true })).toBe(
      "page=2&unclassified=true",
    );
  });

  it("encodes classification, search, sort, and order", () => {
    expect(
      buildDocumentsQuery({
        page: 1,
        q: " payslip ",
        classification: "unclassified",
        sort: "title",
        order: "asc",
      }),
    ).toBe("page=1&q=payslip&classification=unclassified&sort=title&order=asc");
  });
});

describe("summarizeBulkResults", () => {
  it("aggregates statuses for operator feedback", () => {
    expect(
      summarizeBulkResults([
        { paperless_document_id: 1, status: "created" },
        { paperless_document_id: 2, status: "skipped_duplicate" },
        { paperless_document_id: 3, status: "forbidden_or_missing" },
      ]),
    ).toBe("1 created · 1 skipped · 1 forbidden/missing");
  });
});

describe("jobNeedsPolling", () => {
  it("polls uploading and processing only", () => {
    expect(jobNeedsPolling({ state: "UPLOADING" })).toBe(true);
    expect(jobNeedsPolling({ state: "PROCESSING" })).toBe(true);
    expect(jobNeedsPolling({ state: "READY" })).toBe(false);
    expect(jobNeedsPolling({ state: "FAILED" })).toBe(false);
  });
});
