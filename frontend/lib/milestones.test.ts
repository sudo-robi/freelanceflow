import { describe, expect, it } from "vitest";
import { splitMilestoneAmounts } from "./milestones";

describe("splitMilestoneAmounts", () => {
  it("allocates exact shares for a divisible total", () => {
    expect(splitMilestoneAmounts(100, ["a", "b"])).toEqual(["50.0000000", "50.0000000"]);
  });

  it("keeps the sum exact for a non-divisible total", () => {
    const shares = splitMilestoneAmounts(100, ["a", "b", "c"]);
    expect(shares.reduce((sum, value) => sum + Number(value), 0)).toBe(100);
    expect(shares).toEqual(["33.3333334", "33.3333333", "33.3333333"]);
  });

  it("handles fractional budgets and empty input", () => {
    const shares = splitMilestoneAmounts(10.5, ["a", "b", "c"]);
    expect(shares.reduce((sum, value) => sum + Number(value), 0)).toBe(10.5);
    expect(splitMilestoneAmounts(100, [])).toEqual([]);
  });
});
