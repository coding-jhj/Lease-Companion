import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

const fixtureUrl = new URL("./synthetic-non-identifying-lease.pdf", import.meta.url);

export const syntheticLeasePdfFixture = {
  name: "synthetic-non-identifying-lease.pdf",
  mimeType: "application/pdf",
  buffer: readFileSync(fileURLToPath(fixtureUrl)),
} as const;
