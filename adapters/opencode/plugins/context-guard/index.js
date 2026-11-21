import { withTimeout, resolveTimeoutMs } from "./with-timeout.mjs"
import { contextNotice } from "./context-guard-core.mjs"

export default {
  id: "context-guard",
  async setup(ctx) {
    await ctx.session.hook("context", async (event) => {
      try {
        const messages = await withTimeout(
          ctx.session.context({ sessionID: event.sessionID }),
          resolveTimeoutMs(process.env),
        )
        const text = contextNotice(messages, process.env)
        if (text) event.system.push({ type: "text", text })
      } catch {}
    })
  },
}
