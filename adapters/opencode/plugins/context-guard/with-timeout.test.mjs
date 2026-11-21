import { test } from "node:test"
import assert from "node:assert/strict"
import { withTimeout, resolveTimeoutMs, CallTimeoutError } from "./with-timeout.mjs"

test("resolves with the value when fast", async () => {
  assert.equal(await withTimeout(Promise.resolve(7), 50), 7)
})

test("rejects with CallTimeoutError when it never settles", async () => {
  await assert.rejects(withTimeout(new Promise(() => {}), 10), { name: "CallTimeoutError" })
  assert.ok(new CallTimeoutError(10) instanceof Error)
})

test("propagates the original rejection", async () => {
  await assert.rejects(withTimeout(Promise.reject(new Error("boom")), 50), /boom/)
})

test("timeout comes from SUBAGENT_GUARD_TIMEOUT_MS, default 5000, invalid falls back", () => {
  assert.equal(resolveTimeoutMs({}), 5000)
  assert.equal(resolveTimeoutMs({ SUBAGENT_GUARD_TIMEOUT_MS: "20" }), 20)
  assert.equal(resolveTimeoutMs({ SUBAGENT_GUARD_TIMEOUT_MS: "abc" }), 5000)
  assert.equal(resolveTimeoutMs({ SUBAGENT_GUARD_TIMEOUT_MS: "0" }), 5000)
})
