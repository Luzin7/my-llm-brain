import { test, beforeEach, afterEach } from "node:test"
import assert from "node:assert/strict"
import plugin from "./index.js"

const PARENT = "ses_parent"

const makeCtx = ({ children = [], listError = null } = {}) => {
  const hooks = {}
  return {
    hooks,
    listCalls: [],
    tool: { hook: async (name, fn) => { hooks[name] = fn } },
    session: {
      list: async function (query) {
        ctx.listCalls.push(query)
        if (listError) throw listError
        return { data: children.map((id) => ({ id })) }
      },
    },
  }
}

let ctx
let warnings
const originalWarn = console.warn
const originalCap = process.env.SUBAGENT_CAP

const setup = async (options) => {
  ctx = makeCtx(options)
  await plugin.setup(ctx)
}

const call = (overrides = {}) => ({
  tool: "subagent",
  sessionID: PARENT,
  id: "call_1",
  input: {},
  ...overrides,
})

beforeEach(() => {
  warnings = []
  console.warn = (message) => warnings.push(message)
  delete process.env.SUBAGENT_CAP
})

afterEach(() => {
  console.warn = originalWarn
  if (originalCap === undefined) delete process.env.SUBAGENT_CAP
  else process.env.SUBAGENT_CAP = originalCap
})

test("registers execute.before and execute.after hooks", async () => {
  await setup()
  assert.equal(typeof ctx.hooks["execute.before"], "function")
  assert.equal(typeof ctx.hooks["execute.after"], "function")
})

test("below the default cap of 25 allows", async () => {
  await setup({ children: Array.from({ length: 24 }, (_, i) => `c${i}`) })
  await ctx.hooks["execute.before"](call())
})

test("default cap reached throws FanOutCapReachedError", async () => {
  await setup({ children: Array.from({ length: 25 }, (_, i) => `c${i}`) })
  await assert.rejects(ctx.hooks["execute.before"](call()), { name: "FanOutCapReachedError" })
})

test("cap comes from SUBAGENT_CAP", async () => {
  process.env.SUBAGENT_CAP = "2"
  await setup({ children: ["a", "b"] })
  await assert.rejects(ctx.hooks["execute.before"](call()), { name: "FanOutCapReachedError" })
})

test("invalid SUBAGENT_CAP falls back to 25", async () => {
  process.env.SUBAGENT_CAP = "abc"
  await setup({ children: Array.from({ length: 24 }, (_, i) => `c${i}`) })
  await ctx.hooks["execute.before"](call())
})

test("block message names count and cap and has no owner wording", async () => {
  process.env.SUBAGENT_CAP = "1"
  await setup({ children: ["a"] })
  await assert.rejects(ctx.hooks["execute.before"](call()), (error) => {
    assert.match(error.message, /1 child sessions/)
    assert.match(error.message, /cap is 1/)
    assert.doesNotMatch(error.message, /owner/i)
    return true
  })
})

test("resume of an existing child is allowed at the cap", async () => {
  process.env.SUBAGENT_CAP = "1"
  await setup({ children: ["child_1"] })
  await ctx.hooks["execute.before"](call({ input: { sessionID: "child_1" } }))
})

test("resume of an unknown session counts as new", async () => {
  process.env.SUBAGENT_CAP = "1"
  await setup({ children: ["child_1"] })
  await assert.rejects(
    ctx.hooks["execute.before"](call({ input: { sessionID: "other" } })),
    { name: "FanOutCapReachedError" },
  )
})

test("session.list failure allows with a warning", async () => {
  await setup({ listError: new Error("boom") })
  await ctx.hooks["execute.before"](call())
  assert.equal(warnings.length, 1)
  assert.match(warnings[0], /subagent-cap/)
  assert.match(warnings[0], /boom/)
})

test("hung session.list allows with a warning", async () => {
  process.env.SUBAGENT_GUARD_TIMEOUT_MS = "20"
  await setup()
  ctx.session.list = () => new Promise(() => {})
  await ctx.hooks["execute.before"](call())
  delete process.env.SUBAGENT_GUARD_TIMEOUT_MS
  assert.equal(warnings.length, 1)
  assert.match(warnings[0], /timed out/)
})

test("missing session id allows with a warning", async () => {
  await setup()
  await ctx.hooks["execute.before"](call({ sessionID: undefined }))
  assert.equal(warnings.length, 1)
})

test("other tools are ignored", async () => {
  process.env.SUBAGENT_CAP = "0"
  await setup()
  await ctx.hooks["execute.before"](call({ tool: "bash" }))
  assert.equal(ctx.listCalls.length, 0)
})

test("pending parallel dispatches count toward the cap", async () => {
  process.env.SUBAGENT_CAP = "2"
  await setup({ children: ["a"] })
  await ctx.hooks["execute.before"](call({ id: "call_1" }))
  await assert.rejects(
    ctx.hooks["execute.before"](call({ id: "call_2" })),
    { name: "FanOutCapReachedError" },
  )
})

test("execute.after releases the pending reservation", async () => {
  process.env.SUBAGENT_CAP = "2"
  await setup({ children: ["a"] })
  await ctx.hooks["execute.before"](call({ id: "call_1" }))
  await ctx.hooks["execute.after"]({ tool: "subagent", id: "call_1" })
  await ctx.hooks["execute.before"](call({ id: "call_2" }))
})

test("sessions are counted independently", async () => {
  process.env.SUBAGENT_CAP = "1"
  await setup({ children: [] })
  await ctx.hooks["execute.before"](call({ sessionID: "s1", id: "c1" }))
  await ctx.hooks["execute.before"](call({ sessionID: "s2", id: "c2" }))
})
