import { withTimeout, resolveTimeoutMs } from "./with-timeout.mjs"

const DEFAULT_CAP = 25
const PENDING_DISPATCH_TTL_MS = 300000
const SUBAGENT_TOOL = "subagent"

const resolveCap = (env) => {
  const cap = Number.parseInt(env.SUBAGENT_CAP ?? "", 10)
  return Number.isInteger(cap) && cap >= 0 ? cap : DEFAULT_CAP
}

class FanOutCapReachedError extends Error {
  constructor(count, cap) {
    super(
      `Subagent fan-out cap reached: this session already has ${count} child sessions ` +
        `and the cap is ${cap}. Do not split the work further. ` +
        "Stop and ask the user how to proceed.",
    )
    this.name = "FanOutCapReachedError"
  }
}

const createPendingDispatches = () => {
  const reservations = new Map()
  return {
    add: (callID, parentID) => reservations.set(callID, { parentID, at: Date.now() }),
    release: (callID) => reservations.delete(callID),
    sweep(now) {
      for (const [callID, reservation] of reservations) {
        if (now - reservation.at >= PENDING_DISPATCH_TTL_MS) reservations.delete(callID)
      }
    },
    countFor(parentID) {
      let count = 0
      for (const reservation of reservations.values()) {
        if (reservation.parentID === parentID) count += 1
      }
      return count
    },
  }
}

const childIDsOf = async (ctx, parentID, cap) => {
  try {
    const page = await withTimeout(
      ctx.session.list({ parentID, limit: cap + 1 }),
      resolveTimeoutMs(process.env),
    )
    return new Set(page.data.map((session) => session.id))
  } catch (error) {
    console.warn(`[subagent-cap] session list failed for ${parentID}, allowing: ${error?.message}`)
    return null
  }
}

const resolveSessionID = (event) => {
  if (event.sessionID) return event.sessionID
  console.warn("[subagent-cap] subagent call without session id, allowing")
  return null
}

const isResume = (childID, childIDs) => Boolean(childID) && childIDs.has(childID)

const createGuard = (ctx, pending) => async (event) => {
  if (event.tool !== SUBAGENT_TOOL) return
  const parentID = resolveSessionID(event)
  if (!parentID) return
  const cap = resolveCap(process.env)
  pending.sweep(Date.now())
  const childIDs = await childIDsOf(ctx, parentID, cap)
  if (childIDs === null) return
  if (isResume(event.input?.sessionID, childIDs)) return
  const count = childIDs.size + pending.countFor(parentID)
  if (count >= cap) throw new FanOutCapReachedError(count, cap)
  pending.add(event.id, parentID)
}

export default {
  id: "subagent-cap",
  async setup(ctx) {
    const pending = createPendingDispatches()
    await ctx.tool.hook("execute.before", createGuard(ctx, pending))
    await ctx.tool.hook("execute.after", (event) => {
      if (event.tool === SUBAGENT_TOOL) pending.release(event.id)
    })
  },
}
