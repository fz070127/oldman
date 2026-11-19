/**
 * 告警提示音 —— Web Audio 合成，无需音频资源文件
 *
 * 浏览器自动播放策略：AudioContext 必须在用户手势（点击 / 按键）之后才能 resume。
 * 所以这里在第一次用户交互时才创建并解锁 AudioContext；解锁之前来的告警**不响**，
 * 也就不会出现“每次刷新页面都响”的问题。
 */

let ctx: AudioContext | null = null
let unlocked = false
let installed = false

type AudioContextCtor = typeof AudioContext

function getCtor(): AudioContextCtor | null {
  const w = window as unknown as { AudioContext?: AudioContextCtor; webkitAudioContext?: AudioContextCtor }
  return w.AudioContext || w.webkitAudioContext || null
}

function unlock() {
  const Ctor = getCtor()
  if (!Ctor) return
  if (!ctx) ctx = new Ctor()
  ctx
    .resume()
    .then(() => {
      unlocked = ctx?.state === 'running'
      if (unlocked) removeUnlockListeners()
    })
    .catch(() => undefined)
}

const UNLOCK_EVENTS = ['pointerdown', 'keydown', 'touchstart'] as const

function removeUnlockListeners() {
  for (const evt of UNLOCK_EVENTS) window.removeEventListener(evt, unlock, true)
}

/** 应用启动时调用一次：挂载“首次交互解锁”监听 */
export function installAlarmSoundUnlock(): void {
  if (installed) return
  installed = true
  for (const evt of UNLOCK_EVENTS) window.addEventListener(evt, unlock, true)
}

export function isAlarmSoundUnlocked(): boolean {
  return unlocked
}

/** 播放一段“嘀-嘟-嘀-嘟”的告警音（约 1.3s）。未解锁时静默返回 false */
export function playAlarmSound(): boolean {
  if (!ctx || !unlocked || ctx.state !== 'running') return false
  const start = ctx.currentTime + 0.02
  const tones = [988, 740, 988, 740]
  tones.forEach((freq, i) => {
    const t0 = start + i * 0.32
    const osc = ctx!.createOscillator()
    const gain = ctx!.createGain()
    osc.type = 'square'
    osc.frequency.setValueAtTime(freq, t0)
    gain.gain.setValueAtTime(0.0001, t0)
    gain.gain.exponentialRampToValueAtTime(0.12, t0 + 0.02)
    gain.gain.exponentialRampToValueAtTime(0.0001, t0 + 0.26)
    osc.connect(gain).connect(ctx!.destination)
    osc.start(t0)
    osc.stop(t0 + 0.28)
  })
  return true
}
