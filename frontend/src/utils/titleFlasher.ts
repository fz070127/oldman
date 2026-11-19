/**
 * 浏览器标签标题闪烁（新告警提醒）
 *
 * - 页面在后台：一直闪，直到用户切回来
 * - 页面在前台：闪 10 秒自动停止；用户任意点击 / 按键也会停止
 */
const FLASH_INTERVAL_MS = 900
const FOREGROUND_FLASH_MS = 10_000

let timer: ReturnType<typeof setInterval> | null = null
let stopTimer: ReturnType<typeof setTimeout> | null = null
let originalTitle = ''
let flashText = ''
let toggled = false

function onVisible() {
  if (document.visibilityState === 'visible') scheduleForegroundStop()
}

function scheduleForegroundStop() {
  if (stopTimer) clearTimeout(stopTimer)
  stopTimer = setTimeout(stopTitleFlash, FOREGROUND_FLASH_MS)
}

export function startTitleFlash(text: string): void {
  flashText = text
  if (!timer) {
    originalTitle = document.title
    toggled = false
    timer = setInterval(() => {
      toggled = !toggled
      document.title = toggled ? `【🔴 ${flashText}】` : `【告警提醒】${originalTitle}`
    }, FLASH_INTERVAL_MS)
    document.addEventListener('visibilitychange', onVisible)
    window.addEventListener('pointerdown', stopTitleFlash, true)
    window.addEventListener('keydown', stopTitleFlash, true)
  }
  if (document.visibilityState === 'visible') scheduleForegroundStop()
}

export function stopTitleFlash(): void {
  if (!timer) return
  clearInterval(timer)
  timer = null
  if (stopTimer) clearTimeout(stopTimer)
  stopTimer = null
  document.removeEventListener('visibilitychange', onVisible)
  window.removeEventListener('pointerdown', stopTitleFlash, true)
  window.removeEventListener('keydown', stopTitleFlash, true)
  document.title = originalTitle
}
