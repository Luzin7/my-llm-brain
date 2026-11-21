import { test } from "node:test"
import assert from "node:assert/strict"
import { readFileSync } from "node:fs"

const copies = ["with-timeout.mjs", "with-timeout.test.mjs"]

for (const name of copies) {
  test(`${name} is identical in both plugin packages`, () => {
    const first = readFileSync(new URL(`./subagent-cap/${name}`, import.meta.url), "utf8")
    const second = readFileSync(new URL(`./context-guard/${name}`, import.meta.url), "utf8")
    assert.equal(first, second)
  })
}
