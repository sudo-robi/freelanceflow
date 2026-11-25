const QUANTUM = 10_000_000; // seven decimal places, matching backend Decimal validation

/** Split an amount into exact 7-decimal shares whose sum equals the total. */
export function splitMilestoneAmounts(total: number, titles: string[]): string[] {
  if (titles.length === 0) return [];
  const totalUnits = Math.round(total * QUANTUM);
  const base = Math.floor(totalUnits / titles.length);
  const remainder = totalUnits - base * titles.length;
  return titles.map((_, index) => ((base + (index < remainder ? 1 : 0)) / QUANTUM).toFixed(7));
}
