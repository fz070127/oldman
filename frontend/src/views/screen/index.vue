<template>
  <div class="screen-viewport">
    <!-- 固定 1920×1080 设计画布，通过 CSS transform: scale + transform-origin: left top 等比缩放 -->
    <div class="screen-stage" :style="stageStyle">
      <!-- 顶部标题栏 -->
      <header class="screen-header">
        <div class="screen-header__left">
          <span class="ws-pill" :class="`is-${ws.status.value}`">
            <i class="ws-pill__dot" />
            <span>{{ wsStatusText }}</span>
          </span>
          <span class="refresh-text">刷新：{{ lastRefreshText }}</span>
        </div>

        <div class="screen-header__center">
          <h1 class="screen-title">银铃守护 · 社区独居老人智能监测大屏</h1>
          <div class="screen-title-line" />
        </div>

        <div class="screen-header__right">
          <span class="clock-text">{{ nowText }}</span>
          <button
            v-if="isNonProd"
            type="button"
            class="screen-btn is-danger"
            :disabled="mocking"
            @click="triggerMockAlarm"
          >
            {{ mocking ? '注入中...' : '模拟告警' }}
          </button>
          <button type="button" class="screen-btn" @click="toggleFullscreen">
            {{ isFullscreen ? '退出全屏' : '全屏展示' }}
          </button>
          <button type="button" class="screen-btn" @click="goBack">返回管理端</button>
        </div>
      </header>

      <!-- WS 收到 ALARM_NEW 时的中央警示浮层（3 秒自动消失） -->
      <Transition name="alert-pop">
        <div v-if="liveBanner" class="live-alert-toast" role="alert">
          <span class="live-alert-toast__badge">{{ liveBanner.level }}</span>
          <span class="live-alert-toast__text">
            <strong>{{ liveBanner.communityName }}</strong>
            · {{ liveBanner.roomNo }}室 · {{ liveBanner.elderName }}
            {{ liveBanner.eventType === EventType.LONG_LIE ? '检测到久躺异常' : '检测到疑似跌倒' }}
            （置信度 {{ Math.round(liveBanner.confidence * 100) }}%）
          </span>
        </div>
      </Transition>

      <!-- 主体 1920×1080 网格：上 60%（左1/4 + 中1/2 + 右1/4）+ 下 40%（三等分图表） -->
      <main class="screen-body">
        <!-- 上 60% -->
        <section class="screen-row screen-row--top">
          <KpiPanel :overview="overview" />
          <CommunityMap :list="distribution" :active-alert-ids="activeAlertIds" />
          <RealtimeStream :items="realtimeList" :latest-id="latestEventId" />
        </section>

        <!-- 下 40% -->
        <section class="screen-row screen-row--bottom">
          <AlarmTrendChart :list="trendList" />
          <LevelPieChart
            :p0="todayLevelStats.p0"
            :p1="todayLevelStats.p1"
            :p2="todayLevelStats.p2"
            :today-total="todayLevelStats.total"
          />
          <DeviceOnlineChart
            :online="overview?.deviceOnline ?? 0"
            :offline="overview?.deviceOffline ?? 0"
            :total="overview?.deviceTotal ?? 0"
          />
        </section>
      </main>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import dayjs from 'dayjs'
import {
  getDashboardDistribution,
  getDashboardOverview,
  getDashboardRealtime,
  getDashboardTrend,
} from '@/api/dashboard'
import { createMockEvent } from '@/api/event'
import { useWebSocket } from '@/hooks/useWebSocket'
import { useAlarmStore } from '@/stores/alarm'
import type { WsAlarmNewPayload } from '@/types/alarm'
import type {
  DashboardOverview,
  DistributionItem,
  RealtimeItem,
  TrendItem,
} from '@/types/dashboard'
import { EventLevel, EventType } from '@/types/event'
import AlarmTrendChart from './components/AlarmTrendChart.vue'
import CommunityMap from './components/CommunityMap.vue'
import DeviceOnlineChart from './components/DeviceOnlineChart.vue'
import KpiPanel from './components/KpiPanel.vue'
import LevelPieChart from './components/LevelPieChart.vue'
import RealtimeStream from './components/RealtimeStream.vue'

const DESIGN_WIDTH = 1920
const DESIGN_HEIGHT = 1080
const MAX_STREAM_ITEMS = 12
const POLL_INTERVAL_MS = 30_000
const LIVE_ALERT_HIGHLIGHT_MS = 12_000
const LIVE_BANNER_DURATION_MS = 3_000

const router = useRouter()
const alarmStore = useAlarmStore()
const ws = useWebSocket()

const isNonProd = import.meta.env.MODE !== 'production' || import.meta.env.VITE_USE_MOCK === 'true'

// ---------------- 1920×1080 等比缩放（transform: scale + transform-origin: left top） ----------------
const scale = ref(1)
const offsetX = ref(0)
const offsetY = ref(0)

function recalcScale() {
  const vw = window.innerWidth
  const vh = window.innerHeight
  const nextScale = Math.min(vw / DESIGN_WIDTH, vh / DESIGN_HEIGHT)
  scale.value = Number(nextScale.toFixed(6))
  offsetX.value = Math.max(0, Math.floor((vw - DESIGN_WIDTH * nextScale) / 2))
  offsetY.value = Math.max(0, Math.floor((vh - DESIGN_HEIGHT * nextScale) / 2))
}

const stageStyle = computed(() => ({
  left: `${offsetX.value}px`,
  top: `${offsetY.value}px`,
  transform: `scale(${scale.value})`,
}))

// ---------------- 顶部时钟与全屏控制 ----------------
const nowText = ref(dayjs().format('YYYY-MM-DD HH:mm:ss'))
const lastRefreshText = ref('--:--:--')
const isFullscreen = ref(false)
let clockTimer: ReturnType<typeof setInterval> | null = null

const wsStatusText = computed(() => {
  switch (ws.status.value) {
    case 'open':
      return '实时通道在线'
    case 'connecting':
      return '正在连接...'
    case 'reconnecting':
      return '断线重连中'
    default:
      return '通道未连接'
  }
})

function syncFullscreenState() {
  isFullscreen.value = Boolean(document.fullscreenElement)
}

async function toggleFullscreen() {
  try {
    if (!document.fullscreenElement) {
      await document.documentElement.requestFullscreen()
    } else {
      await document.exitFullscreen()
    }
  } catch {
    // 浏览器策略阻止全屏时静默忽略
  }
}

function goBack() {
  if (document.fullscreenElement) {
    document.exitFullscreen().catch(() => undefined)
  }
  router.push('/alarm')
}

// ---------------- 核心看板数据与 30s 轮询 ----------------
const overview = ref<DashboardOverview | null>(null)
const trendList = ref<TrendItem[]>([])
const distribution = ref<DistributionItem[]>([])
const realtimeList = ref<RealtimeItem[]>([])
const latestEventId = ref('')
const activeAlertIds = ref<string[]>([])
const liveBanner = ref<WsAlarmNewPayload | null>(null)

const alertTimers = new Map<string, ReturnType<typeof setTimeout>>()
let bannerTimer: ReturnType<typeof setTimeout> | null = null
let pollTimer: ReturnType<typeof setInterval> | null = null

/** 今日级别占比（优先取 /dashboard/trend 今日项，确保与折线图、overview 口径一致） */
const todayLevelStats = computed(() => {
  const todayStr = dayjs().format('YYYY-MM-DD')
  const todayItem =
    trendList.value.find((item) => item.date === todayStr) ||
    trendList.value[trendList.value.length - 1]
  if (!todayItem) {
    return {
      p0: overview.value?.alarmP0Today ?? 0,
      p1: 0,
      p2: 0,
      total: overview.value?.alarmToday ?? 0,
    }
  }
  const total = Math.max(todayItem.total, overview.value?.alarmToday ?? 0)
  return {
    p0: todayItem.p0,
    p1: todayItem.p1,
    p2: todayItem.p2,
    total,
  }
})

async function fetchAllDashboardData() {
  const [ovRes, trendRes, distRes, rtRes] = await Promise.allSettled([
    getDashboardOverview(),
    getDashboardTrend(7),
    getDashboardDistribution(),
    getDashboardRealtime(),
  ])

  if (ovRes.status === 'fulfilled') {
    overview.value = ovRes.value
  }
  if (trendRes.status === 'fulfilled') {
    trendList.value = trendRes.value.list || []
  }
  if (distRes.status === 'fulfilled') {
    distribution.value = distRes.value.list || []
  }
  if (rtRes.status === 'fulfilled') {
    const incoming = (rtRes.value.list || []).slice(0, MAX_STREAM_ITEMS)
    realtimeList.value = incoming
  }
  lastRefreshText.value = dayjs().format('HH:mm:ss')
}

// ---------------- WS ALARM_NEW 实时联动：事件流插入 + 地图社区变红放大 ----------------
function highlightCommunity(communityName: string) {
  const matched =
    distribution.value.find((c) => c.communityName === communityName) || distribution.value[0]
  if (!matched) return

  matched.alarmToday += 1
  const cid = matched.communityId
  if (!activeAlertIds.value.includes(cid)) {
    activeAlertIds.value = [...activeAlertIds.value, cid]
  }

  const prev = alertTimers.get(cid)
  if (prev) clearTimeout(prev)
  alertTimers.set(
    cid,
    setTimeout(() => {
      activeAlertIds.value = activeAlertIds.value.filter((id) => id !== cid)
      alertTimers.delete(cid)
    }, LIVE_ALERT_HIGHLIGHT_MS),
  )
}

function handleWsAlarmNew(payload: WsAlarmNewPayload, ts: string) {
  const newId = payload.alarmId || `ws-${Date.now()}`
  const matchedComm = distribution.value.find((c) => c.communityName === payload.communityName)

  const streamItem: RealtimeItem = {
    id: newId,
    elderId: payload.elderId,
    elderName: payload.elderName,
    communityId: matchedComm?.communityId || 'C01',
    communityName: payload.communityName,
    roomNo: payload.roomNo,
    type: payload.eventType,
    level: payload.level,
    confidence: payload.confidence,
    occurredAt: payload.occurredAt || ts || dayjs().toISOString(),
    snapshotUrl: payload.snapshotUrl,
  }

  // 1. 实时事件流顶部插入，严格限制 12 条，超出移除最后一条
  const deduped = realtimeList.value.filter((item) => item.id !== streamItem.id)
  realtimeList.value = [streamItem, ...deduped].slice(0, MAX_STREAM_ITEMS)
  latestEventId.value = streamItem.id

  // 2. 地图对应社区点变红放大
  highlightCommunity(payload.communityName)

  // 3. 本地即时递增 KPI 与今日趋势计数，触发 useCountUp 滚动动画
  if (overview.value) {
    overview.value = {
      ...overview.value,
      alarmToday: overview.value.alarmToday + 1,
      alarmPending: overview.value.alarmPending + 1,
      alarmP0Today:
        payload.level === EventLevel.P0
          ? overview.value.alarmP0Today + 1
          : overview.value.alarmP0Today,
    }
  }

  const todayStr = dayjs().format('YYYY-MM-DD')
  const todayBucket =
    trendList.value.find((d) => d.date === todayStr) ||
    trendList.value[trendList.value.length - 1]
  if (todayBucket) {
    if (payload.level === EventLevel.P0) todayBucket.p0 += 1
    else if (payload.level === EventLevel.P1) todayBucket.p1 += 1
    else todayBucket.p2 += 1
    todayBucket.total += 1
  }

  // 4. 中央警示提示条（3 秒自动消失）
  liveBanner.value = payload
  if (bannerTimer) clearTimeout(bannerTimer)
  bannerTimer = setTimeout(() => {
    liveBanner.value = null
    bannerTimer = null
  }, LIVE_BANNER_DURATION_MS)
}

// ---------------- 非生产环境快捷注入模拟告警 ----------------
const mocking = ref(false)
async function triggerMockAlarm() {
  if (mocking.value) return
  mocking.value = true
  try {
    await createMockEvent({
      elderId: '',
      type: EventType.FALL,
      level: EventLevel.P0,
      confidence: 0.95,
    })
  } finally {
    mocking.value = false
  }
}

let offBus: (() => void) | null = null

onMounted(() => {
  recalcScale()
  window.addEventListener('resize', recalcScale)
  document.addEventListener('fullscreenchange', syncFullscreenState)

  clockTimer = setInterval(() => {
    nowText.value = dayjs().format('YYYY-MM-DD HH:mm:ss')
  }, 1000)

  fetchAllDashboardData()
  pollTimer = setInterval(fetchAllDashboardData, POLL_INTERVAL_MS)

  offBus = alarmStore.onAlarmEvent((evt) => {
    if (evt.type === 'new') {
      handleWsAlarmNew(evt.payload, evt.ts)
    } else if (evt.type === 'update') {
      getDashboardOverview()
        .then((ov) => {
          overview.value = ov
        })
        .catch(() => undefined)
    }
  })
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', recalcScale)
  document.removeEventListener('fullscreenchange', syncFullscreenState)
  if (clockTimer) clearInterval(clockTimer)
  if (pollTimer) clearInterval(pollTimer)
  if (bannerTimer) clearTimeout(bannerTimer)
  for (const timer of alertTimers.values()) {
    clearTimeout(timer)
  }
  alertTimers.clear()
  offBus?.()
})
</script>

<style scoped lang="scss">
/* 外层视口：填满窗口，空白区域填充深蓝背景，绝不溢出 */
.screen-viewport {
  position: relative;
  width: 100vw;
  height: 100vh;
  overflow: hidden;
  background-color: #0a1128;
  user-select: none;
}

/* 1920×1080 固定设计稿画布 + 深蓝背景 + 淡淡网格线（CSS repeating-linear-gradient） */
.screen-stage {
  position: absolute;
  display: flex;
  flex-direction: column;
  width: 1920px;
  height: 1080px;
  padding: 12px 18px 16px;
  color: #eaf6ff;
  font-family:
    -apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC', 'Hiragino Sans GB',
    'Microsoft YaHei', sans-serif;
  transform-origin: left top;
  background-color: #0a1128;
  background-image:
    radial-gradient(circle at 50% 18%, rgba(33, 150, 243, 0.16) 0%, rgba(10, 17, 40, 0) 58%),
    repeating-linear-gradient(
      0deg,
      rgba(0, 229, 255, 0.045) 0,
      rgba(0, 229, 255, 0.045) 1px,
      transparent 1px,
      transparent 40px
    ),
    repeating-linear-gradient(
      90deg,
      rgba(0, 229, 255, 0.045) 0,
      rgba(0, 229, 255, 0.045) 1px,
      transparent 1px,
      transparent 40px
    );
}

/* 顶部标题栏 */
.screen-header {
  display: grid;
  grid-template-columns: 420px 1fr 480px;
  align-items: center;
  flex-shrink: 0;
  height: 64px;
  margin-bottom: 12px;
  padding: 0 8px;
  background: linear-gradient(
    90deg,
    rgba(0, 229, 255, 0.04) 0%,
    rgba(0, 229, 255, 0.14) 50%,
    rgba(0, 229, 255, 0.04) 100%
  );
  border-bottom: 1px solid rgba(0, 229, 255, 0.32);

  &__left {
    display: flex;
    align-items: center;
    gap: 14px;
  }

  &__center {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
  }

  &__right {
    display: flex;
    align-items: center;
    justify-content: flex-end;
    gap: 10px;
  }
}

.screen-title {
  margin: 0;
  font-size: 28px;
  font-weight: 700;
  letter-spacing: 4px;
  color: #ffffff;
  text-shadow:
    0 0 16px rgba(0, 229, 255, 0.65),
    0 2px 4px rgba(0, 0, 0, 0.5);
}

.screen-title-line {
  width: 320px;
  height: 2px;
  margin-top: 4px;
  background: linear-gradient(90deg, transparent, #00e5ff, transparent);
}

.ws-pill {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 10px;
  font-size: 12px;
  color: #cfe6ff;
  background: rgba(16, 32, 72, 0.72);
  border: 1px solid rgba(0, 229, 255, 0.28);

  &__dot {
    width: 7px;
    height: 7px;
    border-radius: 50%;
    background: #ffb300;
  }

  &.is-open {
    border-color: rgba(0, 230, 118, 0.45);

    .ws-pill__dot {
      background: #00e676;
      box-shadow: 0 0 8px #00e676;
    }
  }

  &.is-closed {
    border-color: rgba(255, 59, 92, 0.45);

    .ws-pill__dot {
      background: #ff3b5c;
    }
  }
}

.refresh-text {
  font-family: 'DIN Alternate', 'Consolas', monospace;
  font-size: 13px;
  color: rgba(185, 215, 255, 0.72);
}

.clock-text {
  margin-right: 6px;
  font-family: 'DIN Alternate', 'Consolas', monospace;
  font-size: 17px;
  font-weight: 600;
  letter-spacing: 1px;
  color: #00e5ff;
  font-variant-numeric: tabular-nums;
}

.screen-btn {
  height: 30px;
  padding: 0 12px;
  font-size: 12px;
  color: #00e5ff;
  cursor: pointer;
  background: rgba(16, 32, 72, 0.8);
  border: 1px solid rgba(0, 229, 255, 0.45);
  transition: all 0.2s ease;

  &:hover:not(:disabled) {
    color: #0a1128;
    background: #00e5ff;
    box-shadow: 0 0 12px rgba(0, 229, 255, 0.6);
  }

  &:disabled {
    opacity: 0.55;
    cursor: not-allowed;
  }

  &.is-danger {
    color: #ff8fa3;
    border-color: rgba(255, 59, 92, 0.65);

    &:hover:not(:disabled) {
      color: #fff;
      background: #ff3b5c;
      box-shadow: 0 0 12px rgba(255, 59, 92, 0.65);
    }
  }
}

/* WS 实时告警中央警示浮层 */
.live-alert-toast {
  position: absolute;
  top: 84px;
  left: 50%;
  z-index: 40;
  display: inline-flex;
  align-items: center;
  gap: 12px;
  padding: 10px 22px;
  transform: translateX(-50%);
  background: rgba(54, 10, 24, 0.94);
  border: 1px solid #ff3b5c;
  box-shadow:
    0 0 24px rgba(255, 59, 92, 0.55),
    inset 0 0 16px rgba(255, 59, 92, 0.28);

  &__badge {
    padding: 2px 8px;
    font-family: 'DIN Alternate', 'Consolas', monospace;
    font-size: 14px;
    font-weight: 700;
    color: #fff;
    background: #ff3b5c;
  }

  &__text {
    font-size: 15px;
    color: #ffe8ec;

    strong {
      color: #ffffff;
    }
  }
}

.alert-pop-enter-active,
.alert-pop-leave-active {
  transition: all 0.3s ease;
}

.alert-pop-enter-from,
.alert-pop-leave-to {
  opacity: 0;
  transform: translate(-50%, -14px);
}

/* 主体布局：上 60% + 下 40% */
.screen-body {
  display: grid;
  grid-template-rows: 60fr 40fr;
  gap: 14px;
  flex: 1;
  min-height: 0;
}

.screen-row {
  display: grid;
  gap: 14px;
  min-height: 0;

  /* 左 1/4 + 中 1/2 + 右 1/4 */
  &--top {
    grid-template-columns: 1fr 2fr 1fr;
  }

  /* 下排三个图表均分 */
  &--bottom {
    grid-template-columns: 1fr 1fr 1fr;
  }
}
</style>
