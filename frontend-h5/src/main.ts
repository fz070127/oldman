import { createSSRApp } from 'vue'
import App from './App.vue'

/**
 * 兼容简写路由与推送直达动态参数路由：
 * - #/pages/login -> #/pages/login/index
 * - #/pages/home -> #/pages/home/index
 * - #/pages/records -> #/pages/records/index
 * - #/pages/profile -> #/pages/profile/index
 * - #/pages/alarm/:id -> #/pages/alarm/index?id=:id
 */
function normalizeH5Hash() {
  if (typeof window === 'undefined' || !window.location) return
  const hash = window.location.hash || ''
  const shortMap: Record<string, string> = {
    '#/pages/login': '#/pages/login/index',
    '#/pages/home': '#/pages/home/index',
    '#/pages/records': '#/pages/records/index',
    '#/pages/record': '#/pages/records/index',
    '#/pages/profile': '#/pages/profile/index',
    '#/pages/mine': '#/pages/profile/index',
  }
  if (shortMap[hash]) {
    window.location.replace(shortMap[hash])
    return
  }
  const alarmMatch = hash.match(/^#\/pages\/alarm\/([^/?#]+)$/)
  if (alarmMatch && alarmMatch[1] && alarmMatch[1] !== 'index') {
    window.location.replace(`#/pages/alarm/index?id=${encodeURIComponent(alarmMatch[1])}`)
  }
}

if (typeof window !== 'undefined') {
  normalizeH5Hash()
  window.addEventListener('hashchange', normalizeH5Hash)
}

export function createApp() {
  const app = createSSRApp(App)
  return {
    app,
  }
}
