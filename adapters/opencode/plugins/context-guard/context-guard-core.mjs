const DEFAULT_THRESHOLD = 100_000

const notice = (size) =>
  `Context size is about ${size}. If the user's prompt starts a topic unrelated ` +
  "to the current request, recommend in one line that the user log open items " +
  "and start a new session before continuing."

const threshold = (env) => Number(env.CONTEXT_GUARD_TOKENS ?? DEFAULT_THRESHOLD)

const isAssistantWithTokens = (message) =>
  message?.type === "assistant" && message.tokens != null

export function lastContextTokens(messages) {
  const last = [...messages].reverse().find(isAssistantWithTokens)
  if (!last) return null
  const { input, cache } = last.tokens
  return (input ?? 0) + (cache?.read ?? 0) + (cache?.write ?? 0)
}

export function contextNotice(messages, env) {
  try {
    if (messages.at(-1)?.type !== "user") return null
    const tokens = lastContextTokens(messages)
    const limit = threshold(env)
    if (tokens === null || Number.isNaN(limit) || tokens < limit) return null
    return notice(`${Math.floor(tokens / 1000)}K`)
  } catch {
    return null
  }
}
