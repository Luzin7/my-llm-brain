import { test } from "node:test"
import assert from "node:assert/strict"
import plugin from "./context-guard.js"

const assistant = (input) => ({ type: "assistant", tokens: { input, cache: { read: 0, write: 0 } } })

const setup = async (contextFn) => {
  const hooks = {}
  await plugin.setup({
    session: {
      hook: async (name, fn) => { hooks[name] = fn },
      context: contextFn,
    },
  })
  return hooks
}

test("pushes a system notice above the threshold", async () => {
  const hooks = await setup(async () => [assistant(150000), { type: "user" }])
  const event = { sessionID: "s1", system: [] }
  await hooks.context(event)
  assert.equal(event.system.length, 1)
  assert.equal(event.system[0].type, "text")
  assert.match(event.system[0].text, /150K/)
})

test("stays silent below the threshold", async () => {
  const hooks = await setup(async () => [assistant(100), { type: "user" }])
  const event = { sessionID: "s1", system: [] }
  await hooks.context(event)
  assert.deepEqual(event.system, [])
})

test("context read failure fails open", async () => {
  const hooks = await setup(async () => { throw new Error("boom") })
  const event = { sessionID: "s1", system: [] }
  await hooks.context(event)
  assert.deepEqual(event.system, [])
})

test("hung context read fails open", async () => {
  process.env.SUBAGENT_GUARD_TIMEOUT_MS = "20"
  const hooks = await setup(() => new Promise(() => {}))
  const event = { sessionID: "s1", system: [] }
  await hooks.context(event)
  delete process.env.SUBAGENT_GUARD_TIMEOUT_MS
  assert.deepEqual(event.system, [])
})
