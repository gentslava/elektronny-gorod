import { describe, expect, it } from "vitest";

describe("frontend bundle build options", () => {
  it("uses the fixed esbuild release with full Lit-safe minification", async () => {
    const fsModule = "node:fs/promises";
    const { readFile } = await import(fsModule);
    const buildScript = await readFile(new URL("../build.mjs", import.meta.url), "utf8");
    const packageJson = JSON.parse(
      await readFile(new URL("../package.json", import.meta.url), "utf8"),
    ) as { devDependencies?: Record<string, string> };

    expect(packageJson.devDependencies?.["esbuild"]).toBe("^0.28.1");
    expect(buildScript).toMatch(/\bminify\s*:\s*true/);
    expect(buildScript).not.toMatch(/\bminifySyntax\s*:/);
    expect(buildScript).not.toContain("trimGeneratedLineEnds");
    expect(buildScript).not.toMatch(/bundle\.replace\(/);
  });
});
