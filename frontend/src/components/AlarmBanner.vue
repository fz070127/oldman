<template>
  <transition name="alarm-banner" mode="out-in">
    <div
      v-if="current"
      :key="current.alarmId"
      class="alarm-banner"
      :class="`is-${current.level.toLowerCase()}`"
      @mouseenter="pauseTimer"
      @mouseleave="resumeTimer"
    >
      <div class="alarm-banner__card">
        <!-- 顶部 8 秒进度条（悬停时暂停） -->
        <div
          class="alarm-banner__progress"
          :class="{ 'is-paused': paused }"
          :style="{ animationDuration: `${AUTO_HIDE_MS}ms` }"
        />

        <!-- 左侧警示图标 + 级别 -->
        <div class="alarm-banner__badge">
          <span class="alarm-banner__siren">
            <el-icon :size="18"><BellFilled /></el-icon>
          </span>
          <StatusTag category="eventLevel" :status="current.level" effect="dark" />
        </div>

        <!-- 主体信息：老人姓名 + 房号 + 检测到跌倒 + 置信度 -->
        <div class="alarm-banner__body">
          <div class="alarm-banner__title">
            <span class="alarm-banner__elder">{{ current.elderName }}</span>
            <span class="alarm-banner__room">{{ current.communityName }} · {{ current.roomNo }} 室</span>
            <span class="alarm-banner__event-tag">
              {{ current.eventType === EventType.LONG_LIE ? '检测到久躺' : '检测到跌倒' }}
            </span>
            <span class="alarm-banner__conf">
              置信度 <strong>{{ Math.round(current.confidence * 100) }}%</strong>
            </span>
          </div>
          <div class="alarm-banner__meta">
            <span>告警编号：{{ current.alarmId }}</span>
            <span>发生时间：{{ formatTime(current.occurredAt) }}</span>
            <span v-if="paused" class="alarm-banner__paused-tip">已暂停收起计时</span>
          </div>
        </div>

        <!-- 现场截图缩略图 -->
        <div v-if="current.snapshotUrl" class="alarm-banner__thumb-wrap" @click="handleInspect(current.alarmId)">
          <img
            :src="toThumb(current.snapshotUrl)"
            :alt="current.elderName"
            class="alarm-banner__thumb"
          />
          <span class="alarm-banner__thumb-tag">现场截图</span>
        </div>

        <!-- 排队计数（大于 1 条时展示） -->
        <div v-if="queueLength > 1" class="alarm-banner__queue" title="后续排队待展示告警">
          +{{ queueLength - 1 }} 条排队中
        </div>

        <!-- 操作按钮：去看看 + 关闭 -->
        <div class="alarm-banner__actions">
          <el-button type="danger" size="small" class="alarm-banner__btn-view" @click="handleInspect(current.alarmId)">
            去看看
          </el-button>
          <el-button
            text
            size="small"
            class="alarm-banner__btn-close"
            title="关闭横幅"
            @click="handleClose(current.alarmId)"
          >
            <el-icon :size="16"><Close /></el-icon>
            <span>关闭</span>
          </el-button>
        </div>
      </div>
    </div>
  </transition>
</template>

<script setup lang="ts">
/**
 * 顶部实时告警横幅 —— 阶段 F6
 * - 固定在 Navbar 下方，从上方滑入，带轻微抖动
 * - 红色左边框 + 老人姓名 + 房号 + "检测到跌倒" + 置信度 + 缩略图 + "去看看" + 关闭
 * - 8 秒后自动收起（鼠标悬停时暂停计时，移出后按剩余毫秒继续计时）
 * - 多个告警排队，一次只显示一条（queue[0]）
 */
import dayjs from 'dayjs'
import { BellFilled, Close } from '@element-plus/icons-vue'
import StatusTag from '@/components/StatusTag.vue'
import { useAlarmStore } from '@/stores/alarm'
import { EventType } from '@/types/event'

const AUTO_HIDE_MS = 8000

const router = useRouter()
const alarmStore = useAlarmStore()

const current = computed(() => alarmStore.currentBanner)
const queueLength = computed(() => alarmStore.bannerQueue.length)

const paused = ref(false)
let hideTimer: ReturnType<typeof setTimeout> | null = null
let remainingMs = AUTO_HIDE_MS
let startedAt = 0

function clearHideTimer() {
  if (hideTimer) {
    clearTimeout(hideTimer)
    hideTimer = null
  }
}

function startTimer(durationMs = AUTO_HIDE_MS) {
  clearHideTimer()
  const activeId = current.value?.alarmId
  if (!activeId) return
  remainingMs = durationMs
  startedAt = Date.now()
  paused.value = false
  hideTimer = setTimeout(() => {
    hideTimer = null
    alarmStore.dismissBanner(activeId)
  }, durationMs)
}

function pauseTimer() {
  if (!current.value || paused.value) return
  paused.value = true
  const elapsed = Date.now() - startedAt
  remainingMs = Math.max(600, remainingMs - elapsed)
  clearHideTimer()
}

function resumeTimer() {
  if (!current.value || !paused.value) return
  startTimer(remainingMs)
}

function handleClose(alarmId: string) {
  clearHideTimer()
  alarmStore.dismissBanner(alarmId)
}

function handleInspect(alarmId: string) {
  clearHideTimer()
  alarmStore.dismissBanner(alarmId)
  router.push({ path: '/alarm/list', query: { inspect: alarmId } })
}

function formatTime(ts?: string): string {
  if (!ts) return '-'
  const d = dayjs(ts)
  return d.isValid() ? d.format('HH:mm:ss') : '-'
}

function toThumb(url: string): string {
  return url.replace(/\/640\/480(\?.*)?$/, '/160/120$1')
}

watch(
  () => current.value?.alarmId,
  (id) => {
    if (id) {
      startTimer(AUTO_HIDE_MS)
    } else {
      clearHideTimer()
    }
  },
  { immediate: true },
)

onBeforeUnmount(() => {
  clearHideTimer()
})
</script>

<style scoped lang="scss">
.alarm-banner {
  position: fixed;
  top: $navbar-height + 8px;
  left: 50%;
  z-index: 2100;
  width: min(920px, calc(100vw - 48px));
  transform: translateX(-50%);
  pointer-events: auto;

  &__card {
    position: relative;
    display: flex;
    align-items: center;
    gap: 14px;
    padding: 12px 18px;
    overflow: hidden;
    background: linear-gradient(90deg, #fff2f0 0%, #ffffff 38%, #ffffff 100%);
    border: 1px solid #ffa39e;
    border-left: 6px solid #cf1322;
    border-radius: 10px;
    box-shadow:
      0 10px 28px rgba(207, 19, 34, 0.22),
      0 2px 8px rgba(0, 0, 0, 0.08);
    animation: banner-shake 0.48s cubic-bezier(0.36, 0.07, 0.19, 0.97) 0.18s both;
  }

  &__progress {
    position: absolute;
    top: 0;
    left: 0;
    height: 3px;
    width: 100%;
    background: linear-gradient(90deg, #cf1322, #ff7875);
    transform-origin: left center;
    animation-name: banner-countdown;
    animation-timing-function: linear;
    animation-fill-mode: forwards;

    &.is-paused {
      animation-play-state: paused;
    }
  }

  &__badge {
    display: flex;
    flex-shrink: 0;
    align-items: center;
    gap: 8px;
  }

  &__siren {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 34px;
    height: 34px;
    color: #fff;
    background: #cf1322;
    border-radius: 50%;
    box-shadow: 0 0 0 4px rgba(207, 19, 34, 0.16);
    animation: siren-pulse 1.2s ease-in-out infinite;
  }

  &__body {
    flex: 1;
    min-width: 0;
  }

  &__title {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 10px;
    font-size: 15px;
    line-height: 1.4;
  }

  &__elder {
    font-size: 16px;
    font-weight: 700;
    color: #1f2329;
  }

  &__room {
    padding: 1px 8px;
    font-size: 13px;
    font-weight: 600;
    color: #cf1322;
    background: #ffccc7;
    border-radius: 4px;
  }

  &__event-tag {
    font-weight: 700;
    color: #cf1322;
  }

  &__conf {
    font-size: 13px;
    color: #4e5969;

    strong {
      color: #cf1322;
      font-weight: 700;
    }
  }

  &__meta {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 14px;
    margin-top: 3px;
    font-size: 12px;
    color: #646a73;
  }

  &__paused-tip {
    color: #d46b08;
    font-weight: 500;
  }

  &__thumb-wrap {
    position: relative;
    flex-shrink: 0;
    width: 76px;
    height: 52px;
    overflow: hidden;
    cursor: pointer;
    border: 1px solid #ffa39e;
    border-radius: 6px;
    background: #1f2329;
  }

  &__thumb {
    width: 100%;
    height: 100%;
    object-fit: cover;
    display: block;
  }

  &__thumb-tag {
    position: absolute;
    right: 0;
    bottom: 0;
    left: 0;
    font-size: 10px;
    line-height: 15px;
    color: #fff;
    text-align: center;
    background: rgba(0, 0, 0, 0.55);
  }

  &__queue {
    flex-shrink: 0;
    padding: 3px 9px;
    font-size: 12px;
    font-weight: 600;
    color: #d46b08;
    background: #fff7e6;
    border: 1px solid #ffd591;
    border-radius: 12px;
  }

  &__actions {
    display: flex;
    flex-shrink: 0;
    align-items: center;
    gap: 6px;
  }

  &__btn-view {
    font-weight: 600;
  }

  &__btn-close {
    color: #646a73;
  }
}

/* 顶部滑入 / 滑出过渡 */
.alarm-banner-enter-active {
  transition:
    opacity 0.24s ease-out,
    transform 0.24s cubic-bezier(0.22, 1, 0.36, 1);
}

.alarm-banner-leave-active {
  transition:
    opacity 0.2s ease-in,
    transform 0.2s ease-in;
}

.alarm-banner-enter-from,
.alarm-banner-leave-to {
  opacity: 0;
  transform: translate(-50%, -26px);
}

@keyframes banner-shake {
  0%,
  100% {
    transform: translateX(0);
  }
  20% {
    transform: translateX(-5px);
  }
  40% {
    transform: translateX(5px);
  }
  60% {
    transform: translateX(-3px);
  }
  80% {
    transform: translateX(2px);
  }
}

@keyframes siren-pulse {
  0%,
  100% {
    box-shadow: 0 0 0 3px rgba(207, 19, 34, 0.18);
  }
  50% {
    box-shadow: 0 0 0 7px rgba(207, 19, 34, 0.06);
  }
}

@keyframes banner-countdown {
  from {
    transform: scaleX(1);
  }
  to {
    transform: scaleX(0);
  }
}
</style>
