import { describe, expect, it } from "vitest";
import contractExtraction from "../../../data/sample/fixtures/case-001/contract_extraction.json";
import registryExtraction from "../../../data/sample/fixtures/case-001/registry_extraction.json";
import correctionRequest from "../../../data/sample/fixtures/case-001/correction_request.json";
import inputSnapshot from "../../../data/sample/fixtures/case-001/input_snapshot.json";
import analysisRunResult from "../../../data/sample/fixtures/case-001/analysis_run_result.json";
import generationResult from "../../../data/sample/fixtures/case-001/generation_result.json";
import { case001Fixtures } from "../../src/mocks/handlers";

describe("CASE-001 MSW fixtures", () => {
  it("uses all six repository fixtures without field rewriting", () => {
    expect(case001Fixtures.contract_extraction).toEqual(contractExtraction);
    expect(case001Fixtures.registry_extraction).toEqual(registryExtraction);
    expect(case001Fixtures.correction_request).toEqual(correctionRequest);
    expect(case001Fixtures.input_snapshot).toEqual(inputSnapshot);
    expect(case001Fixtures.analysis_run_result).toEqual(analysisRunResult);
    expect(case001Fixtures.generation_result).toEqual(generationResult);
  });

  it("keeps the complete ordered R01-R10 result", () => {
    expect(case001Fixtures.analysis_run_result.results.map((item) => item.rule_id)).toEqual([
      "R01",
      "R02",
      "R03",
      "R04",
      "R05",
      "R06",
      "R07",
      "R08",
      "R09",
      "R10",
    ]);
  });
});
