<template>
  <div v-loading="loading" class="event-detail-page">
    <PageContainer :title="detail ? `事件详情 · ${detail.id}` : '事件详情'">
      <template #extra>
        <el-button :icon="ArrowLeft" @click="router.push('/event')">返回列表</el-button>
      </template>

      <EmptyState v-if="!loading && !detail" description="未找到该事件记录" />

      <div v-else-if="detail" class="event-detail__layout">
        <!-- 左侧 60%：关键帧序列 + 脱敏片段播放器 + features 特征表格 -->
        <div class="event-detail__left">
          <!-- 1. 关键帧序列（横向 6 张缩略图，点击弹大图） -->
          <section class="detail-block">
            <div class="detail-block__head">
              <h3 class="detail-block__title">关键帧序列（点击放大预览）</h3>
              <span class="detail-block__sub">共 {{ keyframes.length }} 帧 · 脱敏画面</span>
            </div>
            <div class="keyframe-strip">
              <div
                v-for="(frameUrl, idx) in keyframes"
                :key="idx"
                class="keyframe-card"
                @click="openKeyframePreview(frameUrl, idx)"
              >
                <img :src="frameUrl" :alt="`关键帧 ${idx + 1}`" class="keyframe-card__img" />
                <span class="keyframe-card__badge">#{{ idx + 1 }}</span>
              </div>
            </div>
          </section>

          <!-- 2. 脱敏片段播放器（video 标签，poster 用首帧） -->
          <section class="detail-block">
            <div class="detail-block__head">
              <h3 class="detail-block__title">脱敏片段回放</h3>
              <StatusTag category="eventLevel" :status="detail.level" />
            </div>
            <div class="video-box">
              <video
                class="video-player"
                controls
                preload="metadata"
                :poster="firstKeyframe"
                :src="videoClipUrl"
              >
                您的浏览器不支持 HTML5 视频播放
              </video>
            </div>
          </section>

          <!-- 3. 算法特征 features 表格 -->
          <section class="detail-block">
            <h3 class="detail-block__title">算法特征参数（Features）</h3>
            <el-descriptions :column="2" border label-width="110px">
              <el-descriptions-item label="躯干角">
                {{ detail.features?.torsoAngle ?? '-' }}°
              </el-descriptions-item>
              <el-descriptions-item label="高度降幅">
                {{ detail.features ? `${Math.round(detail.features.heightDrop * 100)}%` : '-' }}
                <span v-if="detail.features" class="feature-raw">
                  （{{ detail.features.heightDrop }}）
                </span>
              </el-descriptions-item>
              <el-descriptions-item label="静止时长">
                {{ detail.features?.stillDurationSec ?? '-' }} 秒
              </el-descriptions-item>
              <el-descriptions-item label="目标 trackId">
                #{{ detail.features?.trackId ?? '-' }}
              </el-descriptions-item>
              <el-descriptions-item label="算法版本">
                <span class="mono-text">{{ detail.algoVersion || '-' }}</span>
              </el-descriptions-item>
              <el-descriptions-item label="置信度">
                <div class="feature-conf">
                  <el-progress
                    :percentage="Math.round(detail.confidence * 100)"
                    :color="getConfidenceColor(detail.confidence)"
                    :stroke-width="8"
                  />
                </div>
              </el-descriptions-item>
              <el-descriptions-item label="人体框宽高比">
                {{ detail.features?.aspectRatio ?? '-' }}
              </el-descriptions-item>
              <el-descriptions-item label="关键点置信度">
                {{ detail.features ? `${Math.round(detail.features.kpConf * 100)}%` : '-' }}
              </el-descriptions-item>
            </el-descriptions>
          </section>
        </div>

        <!-- 右侧 40%：老人信息小结 + 设备信息 + 处置区 -->
        <div class="event-detail__right">
          <!-- 1. 老人信息小结（可点击跳 /elder/detail/:id） -->
          <section class="detail-block">
            <div class="detail-block__head">
              <h3 class="detail-block__title">老人信息小结</h3>
              <el-link
                type="primary"
                :underline="false"
                @click="router.push(`/elder/detail/${detail.elderId}`)"
              >
                查看完整档案 &rarr;
              </el-link>
            </div>
            <el-descriptions :column="1" border label-width="96px">
              <el-descriptions-item label="老人姓名">
                <el-link
                  type="primary"
                  :underline="false"
                  class="elder-link"
                  @click="router.push(`/elder/detail/${detail.elderId}`)"
                >
                  {{ elderInfo?.name || detail.elderName }}
                </el-link>
              </el-descriptions-item>
              <el-descriptions-item label="年龄 / 性别">
                <span v-if="elderInfo">
                  {{ elderInfo.age }} 岁 · {{ elderInfo.gender === Gender.MALE ? '男' : '女' }}
                </span>
                <span v-else>-</span>
              </el-descriptions-item>
              <el-descriptions-item label="房间号">{{ detail.roomNo }}</el-descriptions-item>
              <el-descriptions-item label="所属社区">
                {{ elderInfo?.communityName || '-' }}
              </el-descriptions-item>
              <el-descriptions-item label="责任网格员">
                {{ elderInfo?.guardianName || '-' }}
              </el-descriptions-item>
              <el-descriptions-item label="健康标签">
                <div v-if="elderInfo?.healthTags?.length" class="tag-cell">
                  <el-tag
                    v-for="tag in elderInfo.healthTags"
                    :key="tag"
                    size="small"
                    effect="plain"
                    class="mr-4"
                  >
                    {{ tag }}
                  </el-tag>
                </div>
                <span v-else class="text-disabled">无</span>
              </el-descriptions-item>
            </el-descriptions>
          </section>

          <!-- 2. 设备信息 -->
          <section class="detail-block">
            <div class="detail-block__head">
              <h3 class="detail-block__title">上报设备信息</h3>
              <el-link
                type="primary"
                :underline="false"
                @click="router.push(`/device/detail/${detail.deviceId}`)"
              >
                设备详情 &rarr;
              </el-link>
            </div>
            <el-descriptions :column="1" border label-width="96px">
              <el-descriptions-item label="设备编号">
                <el-link
                  type="primary"
                  :underline="false"
                  class="mono-text"
                  @click="router.push(`/device/detail/${detail.deviceId}`)"
                >
                  {{ detail.deviceNo }}
                </el-link>
              </el-descriptions-item>
              <el-descriptions-item label="设备类型">
                <StatusTag v-if="deviceInfo" category="deviceType" :status="deviceInfo.type" />
                <span v-else>边缘盒子</span>
              </el-descriptions-item>
              <el-descriptions-item label="运行状态">
                <StatusTag v-if="deviceInfo" category="deviceStatus" :status="deviceInfo.status" />
                <span v-else>-</span>
              </el-descriptions-item>
              <el-descriptions-item label="安装位置">
                {{ deviceInfo?.installAddr || `${detail.roomNo} 室` }}
              </el-descriptions-item>
              <el-descriptions-item label="发生时间">
                {{ formatDateTime(detail.occurredAt) }}
              </el-descriptions-item>
            </el-descriptions>
          </section>

          <!-- 3. 处置区 -->
          <section class="detail-block">
            <h3 class="detail-block__title">事件核实与处置</h3>

            <!-- 已处理态：显示结果 + 备注 + 处理时间 + 操作人 -->
            <el-descriptions v-if="detail.handled" :column="1" border label-width="96px">
              <el-descriptions-item label="处理结果">
                <el-tag
                  v-if="detail.handleResult === EventHandleResult.TRUE_FALL"
                  type="danger"
                  size="small"
                >
                  确认属实（真实跌倒/异常）
                </el-tag>
                <el-tag
                  v-else-if="detail.handleResult === EventHandleResult.FALSE_POSITIVE"
                  type="info"
                  size="small"
                >
                  标记误报
                </el-tag>
                <el-tag v-else type="warning" size="small">其他</el-tag>
              </el-descriptions-item>
              <el-descriptions-item label="处置备注">
                {{ detail.handleRemark || '无备注' }}
              </el-descriptions-item>
              <el-descriptions-item label="处理时间">
                {{ formatDateTime(detail.handledAt) }}
              </el-descriptions-item>
              <el-descriptions-item label="操作人">
                {{ detail.handlerName || currentOperatorName }}
              </el-descriptions-item>
            </el-descriptions>

            <!-- 未处理态：两个按钮「确认属实」/「标记误报」+ 备注输入 -->
            <div v-else class="handle-panel">
              <div class="handle-panel__tip">
                该事件尚未人工复核，请结合左侧关键帧与算法特征给出复核结论：
              </div>
              <el-input
                v-model="remarkInput"
                type="textarea"
                :rows="3"
                maxlength="200"
                show-word-limit
                placeholder="请输入复核备注（例如：弯腰拾物误触 / 已电话联系家属确认安全）"
                class="mb-12"
              />
              <div class="handle-panel__actions">
                <el-button
                  type="danger"
                  :loading="submitting"
                  @click="submitHandle(EventHandleResult.TRUE_FALL)"
                >
                  确认属实
                </el-button>
                <el-button
                  type="warning"
                  plain
                  :loading="submitting"
                  @click="submitHandle(EventHandleResult.FALSE_POSITIVE)"
                >
                  标记误报
                </el-button>
              </div>
            </div>
          </section>
        </div>
      </div>
    </PageContainer>

    <!-- 关键帧大图弹窗 -->
    <el-dialog
      v-model="previewVisible"
      :title="`关键帧大图预览 · 第 ${previewIndex + 1} 帧`"
      width="720px"
      destroy-on-close
      align-center
    >
      <div class="preview-dialog-body">
        <img v-if="previewBigUrl" :src="previewBigUrl" alt="关键帧大图" class="preview-full-img" />
      </div>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ArrowLeft } from '@element-plus/icons-vue'
import { getDeviceDetail } from '@/api/device'
import { getElderDetail } from '@/api/elder'
import { getEventDetail, getEventMedia, handleEvent } from '@/api/event'
import EmptyState from '@/components/EmptyState.vue'
import PageContainer from '@/components/PageContainer.vue'
import StatusTag from '@/components/StatusTag.vue'
import { useUserStore } from '@/stores/user'
import type { Device } from '@/types/device'
import { Gender, type ElderDetail } from '@/types/elder'
import {
  EventHandleResult,
  type EventDetail,
  type EventMedia,
} from '@/types/event'
import { formatDateTime } from '@/utils/time'

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()

const eventId = computed(() => String(route.params.id || ''))
const loading = ref(false)
const detail = ref<EventDetail | null>(null)
const media = ref<EventMedia | null>(null)
const elderInfo = ref<ElderDetail | null>(null)
const deviceInfo = ref<Device | null>(null)

const currentOperatorName = computed(() => userStore.userInfo?.nickname || '系统管理员')

/** 6 张关键帧缩略图列表 */
const keyframes = computed<string[]>(() => {
  if (media.value?.keyframes?.length) return media.value.keyframes
  if (detail.value?.media?.keyframes?.length) return detail.value.media.keyframes
  if (!detail.value) return []
  return Array.from(
    { length: 6 },
    (_, idx) => `https://picsum.photos/seed/${detail.value!.id}-kf-${idx + 1}/320/240`,
  )
})

/** 视频 poster 用首帧 */
const firstKeyframe = computed<string>(() => keyframes.value[0] || detail.value?.snapshotUrl || '')

/** 脱敏片段地址 */
const videoClipUrl = computed<string>(() => {
  return (
    media.value?.clipUrl ||
    detail.value?.media?.clipUrl ||
    detail.value?.clipUrl ||
    'https://interactive-examples.mdn.mozilla.net/media/cc0-videos/flower.mp4'
  )
})

function getConfidenceColor(conf: number): string {
  if (conf > 0.9) return '#52c41a'
  if (conf >= 0.7) return '#faad14'
  return '#909399'
}

// ---------------- 关键帧点击弹大图（先展示 320×240 缩略图，点开后再加载 960×720 大图） ----------------
const previewVisible = ref(false)
const previewIndex = ref(0)
const previewBigUrl = ref('')

function openKeyframePreview(thumbUrl: string, idx: number) {
  previewIndex.value = idx
  previewBigUrl.value = thumbUrl.replace(/\/320\/240(\?.*)?$/, '/960/720$1')
  previewVisible.value = true
}

// ---------------- 加载详情、媒体、关联老人与设备 ----------------
async function loadAll() {
  if (!eventId.value) return
  loading.value = true
  try {
    const [ev, med] = await Promise.all([
      getEventDetail(eventId.value),
      getEventMedia(eventId.value).catch(() => null),
    ])
    detail.value = ev
    media.value = med

    const [elder, dev] = await Promise.all([
      ev.elderId ? getElderDetail(ev.elderId).catch(() => null) : Promise.resolve(null),
      ev.deviceId ? getDeviceDetail(ev.deviceId).catch(() => null) : Promise.resolve(null),
    ])
    elderInfo.value = elder
    deviceInfo.value = dev
  } finally {
    loading.value = false
  }
}

// ---------------- 处置提交 ----------------
const remarkInput = ref('')
const submitting = ref(false)

async function submitHandle(result: EventHandleResult) {
  if (!detail.value) return
  const isFalse = result === EventHandleResult.FALSE_POSITIVE
  const remark =
    remarkInput.value.trim() || (isFalse ? '人工复核标记为误报' : '人工复核确认事件属实')

  submitting.value = true
  try {
    const updated = await handleEvent(detail.value.id, { result, remark })
    detail.value = {
      ...detail.value,
      handled: updated.handled,
      handleResult: updated.handleResult,
      handleRemark: updated.handleRemark,
      handledAt: updated.handledAt,
      handlerName: updated.handlerName || currentOperatorName.value,
    }
    ElMessage.success(isFalse ? '已标记为误报' : '已确认事件属实')
  } finally {
    submitting.value = false
  }
}

watch(eventId, () => loadAll(), { immediate: true })
</script>

<style scoped lang="scss">
.event-detail__layout {
  display: flex;
  gap: 24px;
  align-items: flex-start;

  @media (max-width: 1100px) {
    flex-direction: column;
  }
}

.event-detail__left {
  flex: 0 0 calc(60% - 12px);
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 20px;

  @media (max-width: 1100px) {
    flex: 1 1 100%;
    width: 100%;
  }
}

.event-detail__right {
  flex: 0 0 calc(40% - 12px);
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 20px;

  @media (max-width: 1100px) {
    flex: 1 1 100%;
    width: 100%;
  }
}

.detail-block {
  padding: 16px 18px;
  background: #fafbfc;
  border: 1px solid $border-color-light;
  border-radius: $radius-large;

  &__head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 12px;
  }

  &__title {
    margin-bottom: 12px;
    font-size: 15px;
    font-weight: 600;
    color: $text-primary;
    border-left: 3px solid $color-primary;
    padding-left: 10px;
  }

  &__head &__title {
    margin-bottom: 0;
  }

  &__sub {
    font-size: 12px;
    color: $text-regular;
  }
}

/* 横向 6 张关键帧缩略图 */
.keyframe-strip {
  display: grid;
  grid-template-columns: repeat(6, 1fr);
  gap: 10px;

  @media (max-width: 768px) {
    grid-template-columns: repeat(3, 1fr);
  }
}

.keyframe-card {
  position: relative;
  aspect-ratio: 4 / 3;
  overflow: hidden;
  cursor: pointer;
  background: #e6ebf2;
  border: 1px solid $border-color;
  border-radius: 6px;
  transition: transform 0.15s ease, box-shadow 0.15s ease;

  &:hover {
    transform: translateY(-2px);
    box-shadow: 0 4px 12px rgba(22, 119, 255, 0.18);
  }

  &__img {
    width: 100%;
    height: 100%;
    object-fit: cover;
  }

  &__badge {
    position: absolute;
    right: 6px;
    bottom: 6px;
    padding: 1px 6px;
    font-size: 11px;
    color: #fff;
    background: rgba(0, 0, 0, 0.55);
    border-radius: 4px;
  }
}

/* 脱敏片段播放器 */
.video-box {
  width: 100%;
  overflow: hidden;
  background: #0f131a;
  border-radius: $radius-base;
}

.video-player {
  display: block;
  width: 100%;
  max-height: 360px;
  object-fit: contain;
}

.feature-raw {
  font-size: 12px;
  color: $text-regular;
}

.feature-conf {
  width: 140px;
}

.mono-text {
  font-family: monospace;
  font-weight: 600;
}

.elder-link {
  font-weight: 600;
}

.tag-cell {
  display: flex;
  flex-wrap: nowrap;
  align-items: center;
  overflow: hidden;

  :deep(.el-tag) {
    flex-shrink: 0;
    white-space: nowrap;
  }
}

.handle-panel {
  &__tip {
    margin-bottom: 10px;
    font-size: 13px;
    color: $text-regular;
  }

  &__actions {
    display: flex;
    gap: 12px;
  }
}

.preview-dialog-body {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 380px;
  background: #0f131a;
  border-radius: $radius-base;
  overflow: hidden;
}

.preview-full-img {
  max-width: 100%;
  max-height: 540px;
  object-fit: contain;
}
</style>
