import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const fixturesRoot = join(dirname(fileURLToPath(import.meta.url)), "fixtures");

export function fixturePath(relativePath: string): string {
  return join(fixturesRoot, relativePath);
}

export function loadFixture<T>(relativePath: string): T {
  return JSON.parse(readFileSync(join(fixturesRoot, relativePath), "utf8")) as T;
}

export function loadFixtureText(relativePath: string): string {
  return readFileSync(join(fixturesRoot, relativePath), "utf8");
}
