import { describe, expect, it } from "vitest";
import {
  buildDocumentsQuery,
  buildExploreQuery,
  filterConcepts,
  formatCountStat,
  jobNeedsPolling,
  relationshipTargetPayload,
  relationshipTypesForTarget,
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

  it("encodes date, correspondent, type, tag, and completeness filters", () => {
    expect(
      buildDocumentsQuery({
        page: 1,
        created_gte: "2026-01-01",
        created_lte: "2026-12-31",
        correspondent: "Airbus",
        document_type: "Payslip",
        tag: "hr",
        completeness: "partial",
        sort: "correspondent",
        order: "asc",
      }),
    ).toBe(
      "page=1&sort=correspondent&order=asc&created_gte=2026-01-01&created_lte=2026-12-31&correspondent=Airbus&document_type=Payslip&tag=hr&completeness=partial",
    );
  });

  it("omits completeness=any from the query string", () => {
    expect(buildDocumentsQuery({ page: 1, completeness: "any" })).toBe("page=1");
  });
});

describe("buildExploreQuery", () => {
  it("defaults to documents mode and page 1", () => {
    expect(buildExploreQuery()).toBe("mode=documents&page=1");
  });

  it("encodes explore filters and omits completeness=any", () => {
    expect(
      buildExploreQuery({
        mode: "people",
        page: 2,
        q: " Ali ",
        sort: "title",
        order: "asc",
        completeness: "any",
        relationship_type: "concerns-person",
        person: "Alice",
        country: "Germany",
      }),
    ).toBe(
      "mode=people&page=2&q=Ali&sort=title&order=asc&relationship_type=concerns-person&person=Alice&country=Germany",
    );
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
  it("polls uploading, processing, and resolving", () => {
    expect(jobNeedsPolling({ state: "UPLOADING" })).toBe(true);
    expect(jobNeedsPolling({ state: "PROCESSING" })).toBe(true);
    expect(jobNeedsPolling({ state: "RESOLVING_DOCUMENT" })).toBe(true);
    expect(jobNeedsPolling({ state: "READY" })).toBe(false);
    expect(jobNeedsPolling({ state: "FAILED" })).toBe(false);
    expect(jobNeedsPolling({ state: "RETRYABLE_FAILURE" })).toBe(false);
  });
});

describe("relationshipTypesForTarget", () => {
  const types = [
    {
      code: "source-country",
      name: "Source Country",
      target_ontology: "country",
      directionality: "directed",
      inverse: null,
      target_entity_types: ["country"],
    },
    {
      code: "derived-from",
      name: "Derived From",
      target_ontology: null,
      directionality: "directed",
      inverse: "has-derivative",
      target_entity_types: ["document"],
    },
    {
      code: "document-type",
      name: "Document Type",
      target_ontology: "document-type",
      directionality: "directed",
      inverse: null,
      target_entity_types: ["concept"],
    },
  ];

  it("filters using target_entity_types from the API", () => {
    expect(relationshipTypesForTarget(types, "document").map((t) => t.code)).toEqual([
      "derived-from",
    ]);
    expect(relationshipTypesForTarget(types, "concept").map((t) => t.code)).toEqual([
      "document-type",
    ]);
    expect(relationshipTypesForTarget(types, "country").map((t) => t.code)).toEqual([
      "source-country",
    ]);
  });
});

describe("formatCountStat", () => {
  it("appends + when capped", () => {
    expect(formatCountStat({ count: 25, capped: true })).toBe("25+");
    expect(formatCountStat({ count: 3, capped: false })).toBe("3");
  });

  it("marks unavailable stats", () => {
    expect(formatCountStat({ count: 0, capped: false, unavailable: true })).toBe("unavailable");
  });
});

describe("relationshipTargetPayload", () => {
  it("prefers entity id when present", () => {
    expect(
      relationshipTargetPayload({
        id: "ent-1",
        label: "Germany",
        entity_type: "concept",
        paperless_document_id: null,
        subtitle: null,
        open_url: null,
      }),
    ).toEqual({ target_entity_id: "ent-1" });
  });

  it("falls back to paperless document id", () => {
    expect(
      relationshipTargetPayload({
        id: null,
        label: "Payslip",
        entity_type: "document",
        paperless_document_id: 184,
        subtitle: null,
        open_url: null,
      }),
    ).toEqual({ target_paperless_id: 184 });
  });
});
