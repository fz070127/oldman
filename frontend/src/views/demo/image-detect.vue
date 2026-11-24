<template>
  <PageContainer title="图片人体状态检测" body-padding="0">
    <template #extra>
      <el-tag type="success" effect="plain" size="small">真实推理 · 基于 UR Fall Detection</el-tag>
    </template>

    <div class="image-detect">
      <el-alert
        class="image-detect__notice"
        type="info"
        :closable="false"
        show-icon
        title="判定口径"
        description="上传图片后由后端提取人体关键点并判断姿态。判定阈值来自 UR Fall Detection 数据集真实帧标定；单帧没有时间序列，只给出姿态风险，跌倒确认仍需多帧视频共识。"
      />

      <div class="image-detect__grid">
        <section class="stage-card">
          <div class="toolbar">
            <input ref="fileRef" type="file" accept="image/png,image/jpeg,image/webp" class="hidden-input" @change="handleFileChange" />
            <el-button type="primary" :icon="UploadFilled" :loading="loading" @click="openFilePicker">
              导入图片
            </el-button>
            <el-button :icon="Picture" :loading="loading" @click="loadSample('fall-130.png')">示例：跌倒帧</el-button>
            <el-button :icon="Picture" :loading="loading" @click="loadSample('normal-060.png')">示例：正常活动</el-button>
            <el-button :icon="Picture" :loading="loading" @click="loadSample('fall-070.png')">示例：跌倒帧 2</el-button>
            <span class="toolbar__file" :title="fileName">{{ fileName }}</span>
          </div>

          <div class="stage" :class="{ 'stage--empty': !imageUrl }">
            <img v-show="imageUrl && !loading" ref="imageRef" class="stage__image" :src="imageUrl" alt="待检测图片" @load="redraw" />
            <canvas ref="canvasRef" class="stage__canvas" />
            <div v-if="!imageUrl && !loading" class="stage__placeholder">
              <el-icon :size="42"><Picture /></el-icon>
              <div>点击「导入图片」或选择数据集示例</div>
              <div class="stage__hint">支持 PNG / JPEG / WEBP，最大 12 MB</div>
            </div>
            <div v-if="loading" class="stage__loading">模型推理中…</div>
          </div>

          <div v-if="error" class="error-text">{{ error }}</div>
        </section>

        <aside class="result-card">
          <div class="result-card__header">
            <span>判定结果</span>
            <el-tag :type="statusTagType" effect="dark" size="small">{{ result?.label || '等待图片' }}</el-tag>
          </div>

          <div v-if="result" class="result-body">
            <div class="status-panel" :class="`status-panel--${result.status}`">
              <div class="status-panel__icon">{{ statusIcon }}</div>
              <div>
                <div class="status-panel__title">{{ result.status === 'FALL' ? '检测到躺卧姿态' : result.status === 'SUSPECT' ? '姿态异常' : result.status === 'NO_PERSON' ? '未检测到人' : '正常活动姿态' }}</div>
                <div class="status-panel__desc">{{ statusDesc }}</div>
              </div>
            </div>

            <div class="metric">
              <div class="metric__label">风险 / 置信度</div>
              <el-progress :percentage="Math.round(result.score * 100)" :color="scoreColor" />
            </div>

            <el-descriptions :column="1" border size="small" class="details">
              <el-descriptions-item label="模型参考分">
                {{ result.modelScore?.toFixed(4) ?? '—' }}
              </el-descriptions-item>
              <el-descriptions-item label="目标检测分">
                {{ result.detectionScore?.toFixed(4) || '—' }}
              </el-descriptions-item>
              <el-descriptions-item v-if="result.geometry" label="躯干与水平夹角">
                {{ result.geometry.torsoAngle === null ? '关键点置信度不足' : `${result.geometry.torsoAngle}°` }}
              </el-descriptions-item>
              <el-descriptions-item v-if="result.geometry" label="人体框宽高比">
                {{ result.geometry.aspectRatio }}
              </el-descriptions-item>
              <el-descriptions-item v-if="result.geometry" label="归一化身高">
                {{ result.geometry.bodyHeight }}
              </el-descriptions-item>
              <el-descriptions-item label="关键点数量">
                {{ result.keypoints.length }} 个（COCO 17 点）
              </el-descriptions-item>
            </el-descriptions>

            <div class="basis">
              <div class="basis__title">判定依据</div>
              <div class="basis__text">{{ result.basis }}</div>
            </div>
          </div>

          <div v-else class="result-empty">上传图片后展示判定结果、骨架叠加与模型指标。</div>
        </aside>
      </div>
    </div>
  </PageContainer>
</template>

<script setup lang="ts">
import { Picture, UploadFilled } from '@element-plus/icons-vue'
import { detectImage, type DetectionResult } from '@/api/detection'
import PageContainer from '@/components/PageContainer.vue'

const COCO_EDGES: [number, number][] = [
  [0, 1], [0, 2], [1, 3], [2, 4], [0, 5], [0, 6],
  [5, 7], [7, 9], [6, 8], [8, 10], [5, 11], [6, 12],
  [11, 13], [13, 15], [12, 14], [14, 16], [5, 6], [11, 12],
]

const fileRef = ref<HTMLInputElement>()
const imageRef = ref<HTMLImageElement>()
const canvasRef = ref<HTMLCanvasElement>()
const imageUrl = ref('')
const fileName = ref('')
const loading = ref(false)
const error = ref('')
const result = ref<DetectionResult | null>(null)

const statusTagType = computed<'success' | 'warning' | 'danger' | 'info'>(() => {
  if (result.value?.status === 'FALL') return 'danger'
  if (result.value?.status === 'SUSPECT') return 'warning'
  if (result.value?.status === 'NO_PERSON') return 'info'
  return 'success'
})
const statusIcon = computed(() => {
  if (result.value?.status === 'FALL') return '!'
  if (result.value?.status === 'SUSPECT') return '?'
  if (result.value?.status === 'NO_PERSON') return '—'
  return 'OK'
})
const statusDesc = computed(() => {
  if (result.value?.status === 'FALL') return '躺卧姿态明显，建议结合视频序列复核后派单'
  if (result.value?.status === 'SUSPECT') return '姿态偏离常态，建议人工确认'
  if (result.value?.status === 'NO_PERSON') return '请选用人体清晰可见的图片'
  return '当前姿态未触发跌倒风险规则'
})
const scoreColor = computed(() => {
  if (result.value?.status === 'FALL') return '#f56c6c'
  if (result.value?.status === 'SUSPECT') return '#e6a23c'
  return '#67c23a'
})

function openFilePicker() {
  fileRef.value?.click()
}

function handleFileChange(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (file) void runDetect(file)
  input.value = ''
}

async function loadSample(name: string) {
  loading.value = true
  error.value = ''
  try {
    const response = await fetch(`${import.meta.env.BASE_URL}samples/${name}`)
    if (!response.ok) throw new Error('示例图片加载失败')
    const blob = await response.blob()
    await runDetect(new File([blob], name, { type: blob.type || 'image/png' }))
  } catch (e) {
    error.value = e instanceof Error ? e.message : '示例图片加载失败'
  } finally {
    loading.value = false
  }
}

async function runDetect(file: File) {
  if (!file.type.startsWith('image/')) {
    error.value = '请选择图片文件'
    return
  }
  if (file.size > 12 * 1024 * 1024) {
    error.value = '图片不能超过 12 MB'
    return
  }
  loading.value = true
  error.value = ''
  result.value = null
  if (imageUrl.value) URL.revokeObjectURL(imageUrl.value)
  imageUrl.value = URL.createObjectURL(file)
  fileName.value = file.name
  try {
    result.value = await detectImage(file)
    await nextTick()
    redraw()
  } catch (e) {
    error.value = e && typeof e === 'object' && 'message' in e
      ? String(e.message)
      : '检测失败，请重试'
  } finally {
    loading.value = false
  }
}

function redraw() {
  const canvas = canvasRef.value
  const image = imageRef.value
  if (!canvas || !image || !image.complete || !image.naturalWidth) return
  const width = image.naturalWidth
  const height = image.naturalHeight
  canvas.width = width
  canvas.height = height
  const ctx = canvas.getContext('2d')
  if (!ctx) return
  ctx.clearRect(0, 0, width, height)
  ctx.drawImage(image, 0, 0)

  if (!result.value || !result.value.keypoints.length) return
  const color = result.value.status === 'FALL' ? '#f56c6c'
    : result.value.status === 'SUSPECT' ? '#e6a23c' : '#67c23a'
  const lineWidth = Math.max(2, Math.round(width / 320))

  if (result.value.box.length === 4) {
    const [x1, y1, x2, y2] = result.value.box
    ctx.strokeStyle = color
    ctx.lineWidth = lineWidth
    ctx.strokeRect(x1, y1, x2 - x1, y2 - y1)
    ctx.fillStyle = color
    ctx.font = `${Math.max(14, Math.round(width / 48))}px sans-serif`
    ctx.fillText(result.value.label, x1, Math.max(18, y1 - 6))
  }

  ctx.strokeStyle = '#ffffff'
  ctx.lineWidth = lineWidth
  for (const [a, b] of COCO_EDGES) {
    const pa = result.value.keypoints[a]
    const pb = result.value.keypoints[b]
    if (!pa || !pb || pa[2] < 0.3 || pb[2] < 0.3) continue
    ctx.beginPath()
    ctx.moveTo(pa[0], pa[1])
    ctx.lineTo(pb[0], pb[1])
    ctx.stroke()
  }
  for (const point of result.value.keypoints) {
    if (point[2] < 0.3) continue
    ctx.beginPath()
    ctx.arc(point[0], point[1], lineWidth * 2, 0, Math.PI * 2)
    ctx.fillStyle = color
    ctx.fill()
    ctx.strokeStyle = '#ffffff'
    ctx.lineWidth = 1
    ctx.stroke()
  }
}

onBeforeUnmount(() => {
  if (imageUrl.value) URL.revokeObjectURL(imageUrl.value)
})
</script>

<style scoped lang="scss">
.image-detect {
  padding: 18px;
}

.image-detect__notice {
  margin-bottom: 16px;
}

.image-detect__grid {
  display: grid;
  grid-template-columns: minmax(0, 1.6fr) minmax(320px, 1fr);
  gap: 16px;
  align-items: start;
}

.stage-card,
.result-card {
  background: #fff;
  border: 1px solid #e4e7ed;
  border-radius: 8px;
  padding: 14px;
}

.toolbar {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
  margin-bottom: 12px;
}

.hidden-input {
  display: none;
}

.toolbar__file {
  color: #909399;
  font-size: 12px;
  max-width: 220px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.stage {
  position: relative;
  min-height: 320px;
  background: #f5f7fa;
  border: 1px dashed #c0c4cc;
  border-radius: 6px;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
}

.stage__image,
.stage__canvas {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  object-fit: contain;
}

.stage__placeholder,
.stage__loading {
  position: relative;
  color: #909399;
  text-align: center;
  line-height: 2;
}

.stage__hint {
  font-size: 12px;
  color: #c0c4cc;
}

.error-text {
  margin-top: 10px;
  color: #f56c6c;
  font-size: 13px;
}

.result-card__header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-weight: 600;
  padding-bottom: 12px;
  border-bottom: 1px solid #ebeef5;
}

.result-body {
  padding-top: 12px;
}

.result-empty {
  padding: 32px 8px;
  color: #909399;
  font-size: 13px;
  text-align: center;
}

.status-panel {
  display: flex;
  gap: 12px;
  align-items: center;
  padding: 12px;
  border-radius: 6px;
  margin-bottom: 14px;
  background: #f0f9eb;
}

.status-panel--FALL { background: #fef0f0; }
.status-panel--SUSPECT { background: #fdf6ec; }
.status-panel--NO_PERSON { background: #f4f4f5; }

.status-panel__icon {
  width: 38px;
  height: 38px;
  border-radius: 50%;
  display: grid;
  place-items: center;
  font-weight: 700;
  color: #fff;
  background: #67c23a;
  flex-shrink: 0;
}

.status-panel--FALL .status-panel__icon { background: #f56c6c; }
.status-panel--SUSPECT .status-panel__icon { background: #e6a23c; }
.status-panel--NO_PERSON .status-panel__icon { background: #909399; }

.status-panel__title {
  font-weight: 600;
  margin-bottom: 2px;
}

.status-panel__desc {
  font-size: 12px;
  color: #606266;
}

.metric {
  margin-bottom: 14px;
}

.metric__label {
  font-size: 12px;
  color: #606266;
  margin-bottom: 6px;
}

.details {
  margin-bottom: 14px;
}

.details__note {
  color: #909399;
  font-size: 11px;
}

.basis {
  background: #f5f7fa;
  border-radius: 6px;
  padding: 10px 12px;
}

.basis__title {
  font-weight: 600;
  font-size: 13px;
  margin-bottom: 4px;
}

.basis__text {
  font-size: 12px;
  color: #606266;
  line-height: 1.7;
}

@media (max-width: 1100px) {
  .image-detect__grid { grid-template-columns: 1fr; }
}
</style>
