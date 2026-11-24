<template>
  <PageContainer title="视频跌倒检测演示" body-padding="0">
    <template #extra>
      <el-tag type="warning" effect="plain" size="small">前端模拟 · 非真实推理</el-tag>
    </template>

    <div class="demo-detect">
      <el-alert
        class="demo-detect__notice"
        type="warning"
        :closable="false"
        show-icon
        title="演示说明"
        description="本页标注框、置信度与跌倒状态由前端动画模拟，不调用检测模型。导入视频仅用于展示目标框叠加效果；真实检测需接入边缘端模型或后端推理接口。"
      />

      <div class="demo-detect__grid">
        <section class="stage-card">
          <div class="toolbar">
            <input ref="fileRef" type="file" accept="video/*" class="hidden-input" @change="handleFileChange" />
            <el-button type="primary" :icon="VideoCamera" @click="openFilePicker">导入视频</el-button>
            <el-button :icon="isPlaying ? VideoPause : VideoPlay" @click="togglePlay">
              {{ isPlaying ? '暂停' : '播放' }}
            </el-button>
            <el-button :icon="RefreshRight" @click="restart">重新演示</el-button>
            <el-button :icon="MagicStick" @click="startAnimation">动画示例</el-button>
            <span class="toolbar__file" :title="videoName">{{ videoName }}</span>
          </div>

          <div class="stage" :class="{ 'stage--animation': mode === 'animation' }">
            <video
              v-show="mode === 'video'"
              ref="videoRef"
              class="stage__video"
              :src="videoUrl || undefined"
              playsinline
              muted
              @loadedmetadata="handleLoadedMetadata"
              @play="isPlaying = true"
              @pause="isPlaying = false"
              @ended="isPlaying = false"
            />
            <canvas ref="canvasRef" class="stage__canvas" />
            <div class="stage__live">
              <span class="stage__dot" :class="{ 'is-active': isPlaying }" />
              {{ isPlaying ? '演示中' : '已暂停' }}
            </div>
            <div class="stage__corner stage__corner--tl" />
            <div class="stage__corner stage__corner--tr" />
            <div class="stage__corner stage__corner--bl" />
            <div class="stage__corner stage__corner--br" />
          </div>

          <div class="timeline">
            <span class="timeline__time">{{ formatTime(currentTime) }}</span>
            <el-progress :percentage="Math.round(progress * 100)" :show-text="false" :stroke-width="6" />
            <span class="timeline__time">{{ formatTime(duration) }}</span>
          </div>
          <div v-if="error" class="error-text">{{ error }}</div>
        </section>

        <aside class="info-card">
          <div class="info-card__header">
            <span>实时判定</span>
            <el-tag :type="statusTagType" effect="dark" size="small">{{ statusLabel }}</el-tag>
          </div>

          <div class="status-panel" :class="`status-panel--${status}`">
            <div class="status-panel__icon">{{ statusIcon }}</div>
            <div>
              <div class="status-panel__title">{{ statusTitle }}</div>
              <div class="status-panel__desc">{{ statusDesc }}</div>
            </div>
          </div>

          <el-row :gutter="12" class="metrics">
            <el-col :span="12">
              <div class="metric">
                <div class="metric__label">目标数</div>
                <div class="metric__value">{{ targetCount }}</div>
              </div>
            </el-col>
            <el-col :span="12">
              <div class="metric">
                <div class="metric__label">目标置信度</div>
                <div class="metric__value">{{ confidence.toFixed(2) }}</div>
              </div>
            </el-col>
            <el-col :span="12">
              <div class="metric">
                <div class="metric__label">当前时间</div>
                <div class="metric__value metric__value--sm">{{ formatTime(currentTime) }}</div>
              </div>
            </el-col>
            <el-col :span="12">
              <div class="metric">
                <div class="metric__label">演示进度</div>
                <div class="metric__value metric__value--sm">{{ Math.round(progress * 100) }}%</div>
              </div>
            </el-col>
          </el-row>

          <div class="legend">
            <div class="legend__title">标注说明</div>
            <div><i class="legend__color legend__color--normal" />绿色：正常活动</div>
            <div><i class="legend__color legend__color--suspect" />橙色：疑似跌倒 P1</div>
            <div><i class="legend__color legend__color--fall" />红色：跌倒确认 P0</div>
          </div>

          <div class="logs">
            <div class="logs__title">演示事件</div>
            <div v-if="!logs.length" class="logs__empty">暂无事件</div>
            <div v-for="item in logs" :key="item.id" class="log-item" :class="`log-item--${item.type}`">
              <span class="log-item__time">{{ item.time }}</span>
              <span>{{ item.text }}</span>
            </div>
          </div>
        </aside>
      </div>
    </div>
  </PageContainer>
</template>

<script setup lang="ts">
import { MagicStick, RefreshRight, VideoCamera, VideoPause, VideoPlay } from '@element-plus/icons-vue'

type Phase = 'normal' | 'suspect' | 'fall'
type LogType = 'info' | 'warning' | 'danger'
interface DemoLog {
  id: number
  time: string
  text: string
  type: LogType
}

const ANIMATION_DURATION = 10
const fileRef = ref<HTMLInputElement | null>(null)
const videoRef = ref<HTMLVideoElement | null>(null)
const canvasRef = ref<HTMLCanvasElement | null>(null)

const mode = ref<'animation' | 'video'>('animation')
const videoUrl = ref('')
const videoName = ref('动画示例')
const isPlaying = ref(true)
const currentTime = ref(0)
const duration = ref(ANIMATION_DURATION)
const status = ref<Phase>('normal')
const confidence = ref(0.32)
const targetCount = ref(1)
const logs = ref<DemoLog[]>([])
const error = ref('')

const progress = computed(() => (duration.value > 0 ? Math.min(currentTime.value / duration.value, 1) : 0))
const statusLabel = computed(() => ({ normal: '正常', suspect: 'P1 疑似', fall: 'P0 确认' })[status.value])
const statusTitle = computed(
  () =>
    ({
      normal: '未发现跌倒风险',
      suspect: '检测到疑似失衡',
      fall: '跌倒事件已确认',
    })[status.value],
)
const statusDesc = computed(
  () =>
    ({
      normal: '目标姿态稳定，标注框跟随移动',
      suspect: '框高骤降，进入疑似跌倒观察窗口',
      fall: '持续卧地且形态符合，触发 P0 演示事件',
    })[status.value],
)
const statusIcon = computed(() => ({ normal: '✓', suspect: '!', fall: '!!' })[status.value])
const statusTagType = computed<'success' | 'warning' | 'danger'>(() =>
  status.value === 'fall' ? 'danger' : status.value === 'suspect' ? 'warning' : 'success',
)

let rafId = 0
let animElapsed = 0
let lastFrameTs = 0
let lastUiTs = 0
let lastPhase: Phase | '' = ''
let logSeq = 0

function clamp(value: number, min = 0, max = 1) {
  return Math.min(max, Math.max(min, value))
}

function formatTime(seconds: number) {
  if (!Number.isFinite(seconds)) return '00:00'
  const total = Math.max(0, Math.floor(seconds))
  const mm = String(Math.floor(total / 60)).padStart(2, '0')
  const ss = String(total % 60).padStart(2, '0')
  return `${mm}:${ss}`
}

function phaseAt(ratio: number): Phase {
  if (ratio < 0.42) return 'normal'
  if (ratio < 0.64) return 'suspect'
  if (ratio < 0.94) return 'fall'
  return 'normal'
}

function resetLogs(text?: string) {
  logs.value = []
  lastPhase = ''
  logSeq = 0
  if (text) pushLog(text, 'info')
}

function pushLog(text: string, type: LogType = 'info') {
  logs.value.unshift({ id: ++logSeq, time: formatTime(currentTime.value), text, type })
  logs.value = logs.value.slice(0, 6)
}

function ensureCanvasSize() {
  const canvas = canvasRef.value
  if (!canvas) return
  if (mode.value === 'video' && videoRef.value?.videoWidth) {
    const video = videoRef.value
    if (canvas.width !== video.videoWidth || canvas.height !== video.videoHeight) {
      canvas.width = video.videoWidth
      canvas.height = video.videoHeight
    }
  } else if (canvas.width !== 960 || canvas.height !== 540) {
    canvas.width = 960
    canvas.height = 540
  }
}

function roundRect(ctx: CanvasRenderingContext2D, x: number, y: number, w: number, h: number, r: number) {
  ctx.beginPath()
  ctx.moveTo(x + r, y)
  ctx.lineTo(x + w - r, y)
  ctx.quadraticCurveTo(x + w, y, x + w, y + r)
  ctx.lineTo(x + w, y + h - r)
  ctx.quadraticCurveTo(x + w, y + h, x + w - r, y + h)
  ctx.lineTo(x + r, y + h)
  ctx.quadraticCurveTo(x, y + h, x, y + h - r)
  ctx.lineTo(x, y + r)
  ctx.quadraticCurveTo(x, y, x + r, y)
  ctx.closePath()
}

function drawDemoScene(ctx: CanvasRenderingContext2D, w: number, h: number, ratio: number) {
  const wall = ctx.createLinearGradient(0, 0, 0, h)
  wall.addColorStop(0, '#dce8f5')
  wall.addColorStop(0.65, '#eef3f8')
  wall.addColorStop(1, '#cfd8e3')
  ctx.fillStyle = wall
  ctx.fillRect(0, 0, w, h)

  ctx.fillStyle = 'rgba(255,255,255,0.65)'
  ctx.fillRect(w * 0.08, h * 0.12, w * 0.18, h * 0.28)
  ctx.strokeStyle = 'rgba(80,110,140,0.35)'
  ctx.lineWidth = 2
  ctx.strokeRect(w * 0.08, h * 0.12, w * 0.18, h * 0.28)
  ctx.beginPath()
  ctx.moveTo(w * 0.17, h * 0.12)
  ctx.lineTo(w * 0.17, h * 0.4)
  ctx.moveTo(w * 0.08, h * 0.26)
  ctx.lineTo(w * 0.26, h * 0.26)
  ctx.stroke()

  ctx.fillStyle = '#9aa8b8'
  ctx.fillRect(0, h * 0.66, w, h * 0.34)
  ctx.fillStyle = '#7f8fa2'
  ctx.fillRect(w * 0.66, h * 0.46, w * 0.24, h * 0.08)

  ctx.fillStyle = '#f5c86a'
  ctx.globalAlpha = 0.35 + Math.sin(ratio * Math.PI * 4) * 0.05
  ctx.beginPath()
  ctx.ellipse(w * 0.5, h * 0.86, w * 0.28, h * 0.035, 0, 0, Math.PI * 2)
  ctx.fill()
  ctx.globalAlpha = 1
}

function drawPerson(ctx: CanvasRenderingContext2D, w: number, h: number, fallProgress: number) {
  const t = clamp(fallProgress)
  const standing = {
    head: [0.52, 0.26],
    neck: [0.52, 0.34],
    lShoulder: [0.49, 0.35],
    rShoulder: [0.55, 0.35],
    lHip: [0.5, 0.53],
    rHip: [0.54, 0.53],
    lKnee: [0.49, 0.63],
    rKnee: [0.55, 0.63],
    lFoot: [0.48, 0.73],
    rFoot: [0.56, 0.73],
  }
  const lying = {
    head: [0.34, 0.78],
    neck: [0.4, 0.77],
    lShoulder: [0.42, 0.74],
    rShoulder: [0.42, 0.8],
    lHip: [0.57, 0.77],
    rHip: [0.57, 0.81],
    lKnee: [0.66, 0.74],
    rKnee: [0.67, 0.83],
    lFoot: [0.74, 0.74],
    rFoot: [0.75, 0.85],
  }
  const points: Record<string, [number, number]> = {}
  for (const key of Object.keys(standing)) {
    const s = standing[key as keyof typeof standing]
    const l = lying[key as keyof typeof lying]
    points[key] = [s[0] + (l[0] - s[0]) * t, s[1] + (l[1] - s[1]) * t]
  }

  const edges: [string, string][] = [
    ['head', 'neck'],
    ['lShoulder', 'rShoulder'],
    ['lShoulder', 'lHip'],
    ['rShoulder', 'rHip'],
    ['lHip', 'rHip'],
    ['lHip', 'lKnee'],
    ['rHip', 'rKnee'],
    ['lKnee', 'lFoot'],
    ['rKnee', 'rFoot'],
  ]

  ctx.strokeStyle = 'rgba(30, 81, 148, 0.9)'
  ctx.lineWidth = Math.max(2, w * 0.005)
  ctx.lineCap = 'round'
  for (const [a, b] of edges) {
    ctx.beginPath()
    ctx.moveTo(points[a][0] * w, points[a][1] * h)
    ctx.lineTo(points[b][0] * w, points[b][1] * h)
    ctx.stroke()
  }
  for (const key of Object.keys(points)) {
    ctx.beginPath()
    ctx.fillStyle = '#ffffff'
    ctx.strokeStyle = '#1e5194'
    ctx.lineWidth = 2
    ctx.arc(points[key][0] * w, points[key][1] * h, Math.max(3, w * 0.007), 0, Math.PI * 2)
    ctx.fill()
    ctx.stroke()
  }
  return points
}

function drawOverlay(ctx: CanvasRenderingContext2D, w: number, h: number, ratio: number, phase: Phase) {
  const fallT = clamp((ratio - 0.36) / 0.3)
  const smooth = fallT * fallT * (3 - 2 * fallT)
  const stand = { x: 0.41, y: 0.16, w: 0.22, h: 0.63 }
  const lying = { x: 0.27, y: 0.58, w: 0.53, h: 0.31 }
  const box = {
    x: (stand.x + (lying.x - stand.x) * smooth) * w,
    y: (stand.y + (lying.y - stand.y) * smooth) * h,
    w: (stand.w + (lying.w - stand.w) * smooth) * w,
    h: (stand.h + (lying.h - stand.h) * smooth) * h,
  }

  drawPerson(ctx, w, h, smooth)

  const color = phase === 'fall' ? '#ff4d4f' : phase === 'suspect' ? '#faad14' : '#52c41a'
  const label = phase === 'fall' ? 'FALL P0' : phase === 'suspect' ? 'FALL P1' : 'PERSON'
  const score = phase === 'fall' ? 0.91 : phase === 'suspect' ? 0.72 : 0.32 + smooth * 0.35

  ctx.save()
  ctx.strokeStyle = color
  ctx.lineWidth = Math.max(2, w * 0.004)
  roundRect(ctx, box.x, box.y, box.w, box.h, 6)
  ctx.stroke()

  const corner = Math.min(22, box.w * 0.18)
  ctx.lineWidth = Math.max(4, w * 0.007)
  ctx.beginPath()
  ctx.moveTo(box.x, box.y + corner)
  ctx.lineTo(box.x, box.y)
  ctx.lineTo(box.x + corner, box.y)
  ctx.moveTo(box.x + box.w - corner, box.y)
  ctx.lineTo(box.x + box.w, box.y)
  ctx.lineTo(box.x + box.w, box.y + corner)
  ctx.moveTo(box.x + box.w, box.y + box.h - corner)
  ctx.lineTo(box.x + box.w, box.y + box.h)
  ctx.lineTo(box.x + box.w - corner, box.y + box.h)
  ctx.moveTo(box.x + corner, box.y + box.h)
  ctx.lineTo(box.x, box.y + box.h)
  ctx.lineTo(box.x, box.y + box.h - corner)
  ctx.stroke()

  const font = Math.max(12, Math.round(w * 0.022))
  ctx.font = `600 ${font}px sans-serif`
  const text = `${label} ${score.toFixed(2)}`
  const textW = ctx.measureText(text).width
  const labelW = textW + font * 1.2
  const labelH = font * 1.8
  const labelY = box.y - labelH - 4 < 0 ? box.y + 4 : box.y - labelH - 4
  ctx.fillStyle = color
  roundRect(ctx, box.x, labelY, labelW, labelH, 4)
  ctx.fill()
  ctx.fillStyle = '#ffffff'
  ctx.textBaseline = 'middle'
  ctx.fillText(text, box.x + font * 0.6, labelY + labelH / 2)
  ctx.restore()

  return score
}

function renderFrame(now: number) {
  rafId = requestAnimationFrame(renderFrame)
  const canvas = canvasRef.value
  const ctx = canvas?.getContext('2d')
  if (!canvas || !ctx) return
  ensureCanvasSize()

  if (!lastFrameTs) lastFrameTs = now
  const delta = (now - lastFrameTs) / 1000
  lastFrameTs = now

  let ratio = 0
  if (mode.value === 'video') {
    const video = videoRef.value
    if (!video) return
    currentTime.value = video.currentTime || 0
    duration.value = Number.isFinite(video.duration) ? video.duration : ANIMATION_DURATION
    ratio = duration.value > 0 ? clamp(currentTime.value / duration.value) : 0
    if (video.readyState >= 2) {
      ctx.drawImage(video, 0, 0, canvas.width, canvas.height)
    } else {
      drawDemoScene(ctx, canvas.width, canvas.height, ratio)
    }
  } else {
    if (isPlaying.value) animElapsed += delta
    if (animElapsed > ANIMATION_DURATION) animElapsed = 0
    currentTime.value = animElapsed
    duration.value = ANIMATION_DURATION
    ratio = clamp(animElapsed / ANIMATION_DURATION)
    drawDemoScene(ctx, canvas.width, canvas.height, ratio)
  }

  const phase = phaseAt(ratio)
  const score = drawOverlay(ctx, canvas.width, canvas.height, ratio, phase)

  if (phase !== lastPhase) {
    lastPhase = phase
    status.value = phase
    if (phase === 'suspect') pushLog('进入疑似跌倒观察窗口（P1）', 'warning')
    if (phase === 'fall') pushLog('模拟跌倒确认事件（P0）', 'danger')
    if (phase === 'normal' && currentTime.value > 1) pushLog('状态恢复：未发现跌倒风险', 'info')
  } else if (now - lastUiTs > 100) {
    status.value = phase
  }

  if (now - lastUiTs > 100) {
    confidence.value = score
    targetCount.value = 1
    lastUiTs = now
  }
}

function openFilePicker() {
  fileRef.value?.click()
}

function handleFileChange(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return
  error.value = ''
  if (!file.type.startsWith('video/')) {
    error.value = '请选择视频文件'
    return
  }
  if (videoUrl.value) URL.revokeObjectURL(videoUrl.value)
  videoUrl.value = URL.createObjectURL(file)
  videoName.value = file.name
  mode.value = 'video'
  animElapsed = 0
  lastFrameTs = 0
  resetLogs('视频已载入，等待播放')
  nextTick(() => {
    ensureCanvasSize()
    videoRef.value?.load()
  })
}

function handleLoadedMetadata() {
  const video = videoRef.value
  if (!video) return
  duration.value = Number.isFinite(video.duration) ? video.duration : ANIMATION_DURATION
  currentTime.value = 0
  ensureCanvasSize()
  resetLogs('视频已载入，开始模拟标注')
  video.play().catch(() => {
    isPlaying.value = false
  })
}

function togglePlay() {
  if (mode.value === 'animation') {
    isPlaying.value = !isPlaying.value
    lastFrameTs = 0
    return
  }
  const video = videoRef.value
  if (!video) return
  if (video.paused) {
    video.play().catch(() => {
      error.value = '浏览器阻止自动播放，请再次点击播放'
    })
  } else {
    video.pause()
  }
}

function restart() {
  if (mode.value === 'animation') {
    animElapsed = 0
    isPlaying.value = true
    lastFrameTs = 0
    resetLogs('动画演示已重新开始')
    return
  }
  const video = videoRef.value
  if (!video) return
  video.currentTime = 0
  resetLogs('视频演示已重新开始')
  video.play().catch(() => {
    isPlaying.value = false
  })
}

function startAnimation() {
  videoRef.value?.pause()
  mode.value = 'animation'
  videoName.value = '动画示例'
  animElapsed = 0
  isPlaying.value = true
  lastFrameTs = 0
  resetLogs('动画演示已启动')
}

onMounted(() => {
  resetLogs('动画演示已启动')
  rafId = requestAnimationFrame(renderFrame)
})

onBeforeUnmount(() => {
  cancelAnimationFrame(rafId)
  if (videoUrl.value) URL.revokeObjectURL(videoUrl.value)
})
</script>

<style scoped lang="scss">
.demo-detect {
  padding: 16px 20px 20px;

  &__notice {
    margin-bottom: 16px;
  }

  &__grid {
    display: grid;
    grid-template-columns: minmax(0, 1fr) 300px;
    gap: 16px;

    @media (max-width: 1100px) {
      grid-template-columns: 1fr;
    }
  }
}

.stage-card,
.info-card {
  background: $bg-white;
  border: 1px solid $border-color-light;
  border-radius: $radius-large;
  box-shadow: $shadow-card;
}

.toolbar {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
  padding: 12px 14px;
  border-bottom: 1px solid $border-color-light;

  &__file {
    max-width: 240px;
    margin-left: auto;
    overflow: hidden;
    color: $text-regular;
    font-size: 12px;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
}

.hidden-input {
  display: none;
}

.stage {
  position: relative;
  overflow: hidden;
  margin: 14px;
  background: #0b1626;
  border-radius: $radius-base;
  aspect-ratio: 16 / 9;

  &__video,
  &__canvas {
    position: absolute;
    inset: 0;
    width: 100%;
    height: 100%;
  }

  &__video {
    object-fit: contain;
  }

  &__canvas {
    background: transparent;
  }

  &__live {
    position: absolute;
    top: 12px;
    left: 12px;
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 5px 9px;
    color: #fff;
    font-size: 12px;
    background: rgba(0, 0, 0, 0.45);
    border-radius: 12px;
  }

  &__dot {
    width: 7px;
    height: 7px;
    background: $text-disabled;
    border-radius: 50%;

    &.is-active {
      background: #52c41a;
      box-shadow: 0 0 8px #52c41a;
    }
  }

  &__corner {
    position: absolute;
    width: 18px;
    height: 18px;
    border-color: rgba(255, 255, 255, 0.65);
    border-style: solid;

    &--tl {
      top: 10px;
      left: 10px;
      border-width: 2px 0 0 2px;
    }
    &--tr {
      top: 10px;
      right: 10px;
      border-width: 2px 2px 0 0;
    }
    &--bl {
      bottom: 10px;
      left: 10px;
      border-width: 0 0 2px 2px;
    }
    &--br {
      right: 10px;
      bottom: 10px;
      border-width: 0 2px 2px 0;
    }
  }
}

.timeline {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 0 14px 14px;

  &__time {
    min-width: 42px;
    color: $text-regular;
    font-size: 12px;
    font-variant-numeric: tabular-nums;
  }

  :deep(.el-progress) {
    flex: 1;
  }
}

.error-text {
  padding: 0 14px 12px;
  color: $color-danger;
  font-size: 12px;
}

.info-card {
  padding: 14px;

  &__header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    font-size: 14px;
    font-weight: 600;
    color: $text-primary;
  }
}

.status-panel {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-top: 14px;
  padding: 12px;
  background: #f7f9fc;
  border: 1px solid $border-color-light;
  border-radius: $radius-base;

  &__icon {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 38px;
    height: 38px;
    color: #fff;
    font-size: 18px;
    font-weight: 700;
    background: $color-success;
    border-radius: 50%;
  }

  &__title {
    font-size: 14px;
    font-weight: 600;
    color: $text-primary;
  }

  &__desc {
    margin-top: 4px;
    color: $text-regular;
    font-size: 12px;
    line-height: 1.5;
  }

  &--suspect &__icon {
    background: $color-warning;
  }
  &--fall &__icon {
    background: $color-danger;
  }
}

.metrics {
  margin-top: 14px;
}

.metric {
  padding: 10px;
  background: #fafbfc;
  border-radius: $radius-base;

  &__label {
    color: $text-regular;
    font-size: 12px;
  }

  &__value {
    margin-top: 4px;
    color: $text-primary;
    font-size: 18px;
    font-weight: 600;
    font-variant-numeric: tabular-nums;

    &--sm {
      font-size: 15px;
    }
  }
}

.legend {
  margin-top: 16px;
  color: $text-regular;
  font-size: 12px;
  line-height: 1.9;

  &__title,
  .logs__title {
    margin-bottom: 4px;
    color: $text-primary;
    font-size: 13px;
    font-weight: 600;
  }

  &__color {
    display: inline-block;
    width: 10px;
    height: 10px;
    margin-right: 6px;
    border-radius: 2px;

    &--normal {
      background: $color-success;
    }
    &--suspect {
      background: $color-warning;
    }
    &--fall {
      background: $color-danger;
    }
  }
}

.logs {
  margin-top: 14px;
  padding-top: 12px;
  border-top: 1px solid $border-color-light;

  &__empty {
    padding: 10px 0;
    color: $text-disabled;
    font-size: 12px;
  }
}

.log-item {
  display: flex;
  gap: 8px;
  padding: 6px 0;
  color: $text-regular;
  font-size: 12px;
  border-bottom: 1px dashed $border-color-light;

  &__time {
    color: $text-disabled;
    font-variant-numeric: tabular-nums;
  }

  &--warning {
    color: #b87500;
  }
  &--danger {
    color: $color-danger;
  }
}
</style>
