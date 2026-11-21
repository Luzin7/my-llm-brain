import { test } from "node:test"
import assert from "node:assert/strict"
import { contextNotice, lastContextTokens } from "./context-guard-core.mjs"

const assistant = (input, read = 0, write = 0) => ({
  type: "assistant", tokens: { input, output: 5, reasoning: 0, cache: { read, write } },
})
const user = () => ({ type: "user" })

test("below threshold is silent", () => {
  assert.equal(contextNotice([assistant(10, 50000, 1000), user()], {}), null)
})

test("at threshold injects notice with size", () => {
  assert.match(contextNotice([assistant(1000, 98000, 1000), user()], {}), /100K/)
})

test("sums input and both cache fields", () => {
  assert.equal(lastContextTokens([assistant(50000, 60000, 40000)]), 150000)
})

test("notice recommends a new session for unrelated topics", () => {
  const text = contextNotice([assistant(150000), user()], {})
  assert.match(text, /unrelated/)
  assert.match(text, /new session/)
  assert.doesNotMatch(text, /owner/i)
})

test("uses last assistant message", () => {
  assert.equal(contextNotice([assistant(150000), assistant(20000), user()], {}), null)
})

test("env threshold lowers", () => {
  assert.notEqual(contextNotice([assistant(5000), user()], { CONTEXT_GUARD_TOKENS: "1000" }), null)
})

test("env threshold raises", () => {
  assert.equal(contextNotice([assistant(150000), user()], { CONTEXT_GUARD_TOKENS: "200000" }), null)
})

test("silent when last message is not a new user prompt", () => {
  assert.equal(contextNotice([user(), assistant(150000)], {}), null)
})

test("no assistant messages is silent", () => {
  assert.equal(contextNotice([user()], {}), null)
})

test("garbled input fails open", () => {
  assert.equal(contextNotice(null, {}), null)
  assert.equal(contextNotice([{}, { tokens: null }, 5], {}), null)
})

test("invalid env threshold fails open", () => {
  assert.equal(contextNotice([assistant(150000), user()], { CONTEXT_GUARD_TOKENS: "abc" }), null)
})
