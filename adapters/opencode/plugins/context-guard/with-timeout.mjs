const DEFAULT_TIMEOUT_MS = 5000

export class CallTimeoutError extends Error {
  constructor(ms) {
    super(`call timed out after ${ms}ms`)
    this.name = "CallTimeoutError"
  }
}

export const resolveTimeoutMs = (env) => {
  const ms = Number.parseInt(env.SUBAGENT_GUARD_TIMEOUT_MS ?? "", 10)
  return Number.isInteger(ms) && ms > 0 ? ms : DEFAULT_TIMEOUT_MS
}

export const withTimeout = (promise, ms) => {
  let timer
  const timeout = new Promise((_, reject) => {
    timer = setTimeout(() => reject(new CallTimeoutError(ms)), ms)
  })
  return Promise.race([promise, timeout]).finally(() => clearTimeout(timer))
}
