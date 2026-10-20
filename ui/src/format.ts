// Display formatting for slot values. Display only: the numbers spoken come from the server.

export const inr = (n: number) =>
  n >= 100_000 ? `₹${+(n / 100_000).toFixed(2)} lakh` : `₹${n.toLocaleString("en-IN")}`;

const LABEL: Record<string, string> = {
  budget_min: "Budget from",
  budget_max: "Budget up to",
  budget_target: "Around",
  body_type: "Body",
  fuel: "Fuel",
  city: "City",
  make: "Make",
  model: "Model",
  max_km: "Max km",
  min_payload_kg: "Payload at least",
  min_year: "Year from",
  purpose: "Ranked for",
};

export const slotLabel = (k: string) => LABEL[k] ?? k;

export function slotValue(k: string, v: unknown): string {
  if (v === null || v === undefined) return "–";
  if (typeof v === "number") {
    if (k.startsWith("budget")) return inr(v);
    if (k === "min_payload_kg") return `${v.toLocaleString("en-IN")} kg`;
    if (k === "min_year") return String(v);
    return v.toLocaleString("en-IN");
  }
  const s = String(v).replace(/_/g, " ");
  if (s === "cng") return "CNG";
  return k === "city" || k === "fuel" ? s.replace(/\b\w/g, (c) => c.toUpperCase()) : s;
}

export const FEATURE: Record<string, string> = {
  price: "Price",
  low_km: "Low km",
  newer_year: "Newer",
  papers_verified: "Papers verified",
  purpose_fit: "Fits purpose",
};
