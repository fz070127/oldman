<template>
  <el-drawer
    :model-value="modelValue"
    size="720px"
    :with-header="false"
    destroy-on-close
    class="alarm-detail-drawer"
    @update:model-value="emit('update:modelValue', $event)"
  >
    <div v-loading="loading" class="drawer-shell">
      <!-- 1. 顶部：级别徽标 + 状态 + 倒计时（PENDING 时）+ 关闭按钮 -->
      <header class="drawer-header">
        <div class="drawer-header__left">
          <span class="drawer-header__title">告警处置详情</span>
          <span v-if="detail" class="drawer-header__id">#{{ detail.id }}</span>
          <template v-if="detail">
            <StatusTag category="eventLevel" :status="detail.level" size="default" />
            <StatusTag category="alarmStatus" :status="detail.status" size="default" />
          </template>
        </div>

        <div class="drawer-header__right">
          <div
            v-if="detail && detail.status === AlarmStatus.PENDING && displayCountdownSec !== null"
            class="drawer-countdown"
            :class="{ 'is-urgent': displayCountdownSec <= 15 }"
          >
            <el-icon><Timer /></el-icon>
            <span>升级倒计时</span>
            <strong>{{ formatMMSS(displayCountdownSec) }}</strong>
          </div>
          <el-button text circle :icon="Close" @click="emit('update:modelValue', false)" />
        </div>
      </header>

      <!-- 2. 主体双栏区 -->
      <div v-if="detail" class="drawer-body">
        <!-- 主栏（左）：老人信息卡 + 竖向5阶段时间轴 + 现场截图/播放器 + 事件要素表 -->
        <div class="drawer-main">
          <!-- 老人信息卡 -->
          <section class="panel-card elder-card">
            <div class="panel-card__head">
              <span class="panel-card__title">老人信息卡</span>
              <el-link
                type="primary"
                :underline="false"
                @click="goElderDetail(detail.elder.id)"
              >
                老人档案 &rarr;
              </el-link>
            </div>
            <div class="elder-card__grid">
              <div class="elder-card__main">
                <div class="elder-card__name-row">
                  <span class="elder-card__name">{{ detail.elder.name }}</span>
                  <span class="elder-card__age">{{ detail.elder.age }} 岁</span>
                  <span class="elder-card__room">{{ detail.elder.roomNo }} 室</span>
                </div>
                <div class="elder-card__addr">{{ detail.elder.address }}</div>
                <div class="elder-card__tags">
                  <el-tag
                    v-for="tag in detail.elder.healthTags"
                    :key="tag"
                    size="small"
                    effect="plain"
                  >
                    {{ tag }}
                  </el-tag>
                  <span v-if="!detail.elder.healthTags?.length" class="text-muted">无健康标签</span>
                </div>
              </div>
              <div class="elder-card__contact">
                <div class="elder-card__contact-label">主联系人（点击直拨）</div>
                <template v-if="detail.elder.primaryContact">
                  <div class="elder-card__contact-person">
                    {{ detail.elder.primaryContact.name }}
                    <span class="elder-card__contact-rel">（{{ detail.elder.primaryContact.relation }}）</span>
                  </div>
                  <a
                    :href="`tel:${detail.elder.primaryContact.phone}`"
                    class="elder-card__tel"
                  >
                    <el-icon><PhoneFilled /></el-icon>
                    <span>{{ detail.elder.primaryContact.phone }}</span>
                  </a>
                </template>
                <span v-else class="text-muted">未配置主联系人</span>
              </div>
            </div>
          </section>

          <!-- 竖向 5 节点状态时间轴：发生 → 通知家属 → 升级网格员 → 确认 → 完结（当前节点高亮） -->
          <section class="panel-card">
            <div class="panel-card__head">
              <span class="panel-card__title">告警闭环进度</span>
              <span v-if="detail.responseSec !== null" class="panel-card__extra">
                响应耗时 <strong>{{ detail.responseSec }}s</strong>
              </span>
            </div>
            <div class="stage-timeline">
              <div
                v-for="(node, idx) in stageNodes"
                :key="node.key"
                class="stage-node"
                :class="[`is-${node.state}`]"
              >
                <div class="stage-node__rail">
                  <span class="stage-node__dot">
                    <span v-if="node.state === 'current'" class="stage-node__pulse" />
                  </span>
                  <span v-if="idx < stageNodes.length - 1" class="stage-node__line" />
                </div>
                <div class="stage-node__content">
                  <div class="stage-node__top">
                    <span class="stage-node__label">{{ node.label }}</span>
                    <el-tag
                      v-if="node.state === 'current'"
                      size="small"
                      type="danger"
                      effect="dark"
                      class="stage-node__badge"
                    >
                      当前节点
                    </el-tag>
                    <span v-if="node.ts" class="stage-node__time">{{ formatTime(node.ts) }}</span>
                  </div>
                  <div class="stage-node__desc">{{ node.desc }}</div>
                </div>
              </div>
            </div>
          </section>

          <!-- 现场截图大图（点击放大）+ clipUrl 播放器 -->
          <section class="panel-card">
            <div class="panel-card__head">
              <span class="panel-card__title">现场脱敏画面</span>
              <el-link type="primary" :underline="false" @click="previewVisible = true">
                点击放大原图
              </el-link>
            </div>
            <div class="media-grid">
              <div class="snapshot-box" @click="previewVisible = true">
                <img
                  :src="detail.event.snapshotUrl"
                  :alt="detail.id"
                  class="snapshot-box__img"
                />
                <span class="snapshot-box__badge">
                  {{ detail.event.type === EventType.LONG_LIE ? '久躺告警截图' : '跌倒告警截图' }} · 点击放大
                </span>
              </div>
              <div v-if="detail.event.clipUrl" class="clip-box">
                <video
                  :src="detail.event.clipUrl"
                  :poster="detail.event.snapshotUrl"
                  controls
                  preload="metadata"
                  class="clip-box__video"
                />
              </div>
            </div>
          </section>

          <!-- 事件要素表 -->
          <section class="panel-card">
            <div class="panel-card__head">
              <span class="panel-card__title">事件要素表</span>
              <span class="mono-tag">{{ detail.event.algoVersion }}</span>
            </div>
            <el-descriptions :column="2" border size="small" label-width="98px">
              <el-descriptions-item label="事件类型">
                <el-tag
                  size="small"
                  :type="detail.event.type === EventType.FALL ? 'danger' : 'warning'"
                >
                  {{ detail.event.type === EventType.FALL ? '跌倒 (FALL)' : '久躺 (LONG_LIE)' }}
                </el-tag>
              </el-descriptions-item>
              <el-descriptions-item label="算法置信度">
                <strong>{{ Math.round(detail.event.confidence * 100) }}%</strong>
              </el-descriptions-item>
              <el-descriptions-item label="躯干夹角">
                {{ detail.event.features?.torsoAngle ?? '-' }}°
              </el-descriptions-item>
              <el-descriptions-item label="高度降幅">
                {{
                  detail.event.features
                    ? `${Math.round(detail.event.features.heightDrop * 100)}%`
                    : '-'
                }}
              </el-descriptions-item>
              <el-descriptions-item label="静止时长">
                {{ detail.event.features?.stillDurationSec ?? '-' }} 秒
              </el-descriptions-item>
              <el-descriptions-item label="人体宽高比">
                {{ detail.event.features?.aspectRatio ?? '-' }}
              </el-descriptions-item>
              <el-descriptions-item label="关键点置信度">
                {{
                  detail.event.features
                    ? `${Math.round(detail.event.features.kpConf * 100)}%`
                    : '-'
                }}
              </el-descriptions-item>
              <el-descriptions-item label="跟踪目标 ID">
                #{{ detail.event.features?.trackId ?? '-' }}
              </el-descriptions-item>
            </el-descriptions>
          </section>
        </div>

        <!-- 右侧小栏：处置流水（谁、什么时间、什么动作、渠道、送达结果） -->
        <aside class="drawer-side">
          <div class="side-head">
            <span class="side-head__title">处置流水</span>
            <span class="side-head__count">共 {{ detail.actions.length }} 条</span>
          </div>

          <div class="action-stream">
            <div v-for="act in detail.actions" :key="act.id" class="action-item">
              <div class="action-item__top">
                <span class="action-item__badge" :class="`is-${act.action.toLowerCase()}`">
                  {{ formatActionLabel(act.action) }}
                </span>
                <span class="action-item__time">{{ formatTime(act.createdAt) }}</span>
              </div>

              <div class="action-item__actor">
                操作人：<strong>{{ act.actorName }}</strong>
                <span class="action-item__actor-id">({{ act.actor }})</span>
              </div>

              <div v-if="act.channel || act.result" class="action-item__channel-row">
                <el-tag v-if="act.channel" size="small" effect="plain">
                  渠道：{{ formatChannelLabel(act.channel) }}
                </el-tag>
                <el-tag
                  v-if="act.result"
                  size="small"
                  :type="act.result === 'FAILED' ? 'danger' : 'success'"
                  effect="light"
                >
                  {{ formatResultLabel(act.result) }}
                </el-tag>
              </div>

              <div v-if="formatActionDetail(act)" class="action-item__detail">
                {{ formatActionDetail(act) }}
              </div>
            </div>
          </div>
        </aside>
      </div>

      <!-- 3. 底部操作区（严格按当前状态显示合法操作） -->
      <footer v-if="detail" class="drawer-footer">
        <div class="drawer-footer__handler">
          当前责任人：<strong>{{ detail.currentHandler || '-' }}</strong>
          <span v-if="detail.escalateStep > 0" class="drawer-footer__step">
            （已升级 {{ detail.escalateStep }} 次）
          </span>
        </div>

        <div class="drawer-footer__btns">
          <!-- PENDING：[确认我已处理] [派单给网格员] -->
          <template v-if="detail.status === AlarmStatus.PENDING">
            <el-button type="primary" @click="emit('request-ack', detail)">
              确认我已处理
            </el-button>
            <el-button type="warning" plain @click="emit('request-dispatch', detail)">
              派单给网格员
            </el-button>
          </template>

          <!-- ESCALATED：[确认我已处理] [派单] -->
          <template v-else-if="detail.status === AlarmStatus.ESCALATED">
            <el-button type="primary" @click="emit('request-ack', detail)">
              确认我已处理
            </el-button>
            <el-button type="warning" plain @click="emit('request-dispatch', detail)">
              派单
            </el-button>
          </template>

          <!-- ACKNOWLEDGED / COMMUNITY_DISPATCHED：[完结] [标记误报] -->
          <template
            v-else-if="
              detail.status === AlarmStatus.ACKNOWLEDGED ||
              detail.status === AlarmStatus.COMMUNITY_DISPATCHED
            "
          >
            <el-button
              type="success"
              @click="emit('request-resolve', detail, EventHandleResult.TRUE_FALL)"
            >
              完结
            </el-button>
            <el-button
              type="info"
              plain
              @click="emit('request-resolve', detail, EventHandleResult.FALSE_POSITIVE)"
            >
              标记误报
            </el-button>
          </template>

          <!-- 已完成（RESOLVED / FALSE_POSITIVE）：只显示信息 -->
          <template v-else>
            <span class="drawer-footer__done">
              该告警已于 {{ formatTime(detail.resolvedAt) }} 归档完结（{{
                detail.status === AlarmStatus.FALSE_POSITIVE ? '误报关闭' : '真实处置完结'
              }}）
            </span>
          </template>
        </div>
      </footer>
    </div>

    <!-- 截图放大预览 -->
    <el-dialog
      v-model="previewVisible"
      :title="detail ? `现场截图 · ${detail.elder.name}（#${detail.id}）` : '现场截图'"
      width="760px"
      destroy-on-close
      align-center
    >
      <div class="preview-body">
        <img
          v-if="detail?.event.snapshotUrl"
          :src="detail.event.snapshotUrl"
          alt="现场截图大图"
          class="preview-img"
        />
      </div>
    </el-dialog>
  </el-drawer>
</template>

<script setup lang="ts">
/**
 * 告警详情抽屉（el-drawer，宽度 720px）—— 阶段 F6
 * - 顶部：级别徽标 + 状态 + 倒计时（PENDING 时）
 * - 竖向时间轴：发生 → 通知家属 → 升级网格员 → 确认 → 完结，当前节点高亮
 * - 老人信息卡：姓名、年龄、房号、健康标签、主联系人电话（tel: 可拨）
 * - 现场截图大图（点击放大），有 clipUrl 时放播放器
 * - 事件要素表
 * - 底部操作区（按当前状态显示合法操作）
 * - 右侧小栏：处置流水（谁、什么时间、什么动作、渠道、送达结果）
 */
import dayjs from 'dayjs'
import { Close, PhoneFilled, Timer } from '@element-plus/icons-vue'
import StatusTag from '@/components/StatusTag.vue'
import {
  AlarmActionType,
  AlarmStatus,
  type AlarmAction,
  type AlarmDetail,
} from '@/types/alarm'
import { EventHandleResult, EventType } from '@/types/event'

const props = defineProps<{
  modelValue: boolean
  loading: boolean
  detail: AlarmDetail | null
  /** 列表页同步维护的该告警实时剩余秒数（PENDING 时每秒递减） */
  countdownSec?: number | null
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', val: boolean): void
  (e: 'request-ack', detail: AlarmDetail): void
  (e: 'request-dispatch', detail: AlarmDetail): void
  (e: 'request-resolve', detail: AlarmDetail, defaultResult: EventHandleResult): void
}>()

const router = useRouter()
const previewVisible = ref(false)

/** 优先使用父组件每秒递减的 countdownSec，回退到 detail.remainingSec */
const displayCountdownSec = computed<number | null>(() => {
  if (!props.detail || props.detail.status !== AlarmStatus.PENDING) return null
  if (typeof props.countdownSec === 'number') return props.countdownSec
  if (typeof props.detail.remainingSec === 'number') return props.detail.remainingSec
  return null
})

function formatMMSS(sec: number): string {
  const safe = Math.max(0, Math.floor(sec))
  const mm = String(Math.floor(safe / 60)).padStart(2, '0')
  const ss = String(safe % 60).padStart(2, '0')
  return `${mm}:${ss}`
}

function formatTime(ts?: string | null): string {
  if (!ts) return '-'
  const d = dayjs(ts)
  return d.isValid() ? d.format('MM-DD HH:mm:ss') : '-'
}

function goElderDetail(elderId: string) {
  emit('update:modelValue', false)
  router.push(`/elder/detail/${elderId}`)
}

// ---------------- 竖向 5 阶段时间轴：发生 → 通知家属 → 升级网格员 → 确认 → 完结 ----------------
interface StageNode {
  key: string
  label: string
  state: 'done' | 'current' | 'todo' | 'skipped'
  ts: string | null
  desc: string
}

const stageNodes = computed<StageNode[]>(() => {
  const d = props.detail
  if (!d) return []

  const notifyAct = d.actions.find((a) => a.action === AlarmActionType.NOTIFY)
  const escalateAct = d.actions.find(
    (a) => a.action === AlarmActionType.ESCALATE || a.action === AlarmActionType.DISPATCH,
  )
  const ackAct = d.actions.find((a) => a.action === AlarmActionType.ACK)
  const resolveAct = d.actions.find(
    (a) => a.action === AlarmActionType.RESOLVE || a.action === AlarmActionType.MARK_FALSE,
  )

  const st = d.status
  const isFinished = st === AlarmStatus.RESOLVED || st === AlarmStatus.FALSE_POSITIVE
  const isAcked = st === AlarmStatus.ACKNOWLEDGED
  const isEscalatedOrDispatched =
    st === AlarmStatus.ESCALATED || st === AlarmStatus.COMMUNITY_DISPATCHED
  const isPending = st === AlarmStatus.PENDING

  const typeLabel = d.event.type === EventType.LONG_LIE ? '久躺预警' : '跌倒事件'

  return [
    {
      key: 'occur',
      label: '1. 发生',
      state: 'done',
      ts: d.event.occurredAt,
      desc: `边缘端检测到${typeLabel}（置信度 ${Math.round(d.event.confidence * 100)}%）`,
    },
    {
      key: 'notify',
      label: '2. 通知家属',
      state: isPending ? 'current' : 'done',
      ts: notifyAct?.createdAt || d.notifiedAt,
      desc: isPending
        ? `已推送主联系人（${d.elder.primaryContact?.name || d.currentHandler}），等待确认中...`
        : `已通知家属（${d.elder.primaryContact?.name || '主联系人'}）`,
    },
    {
      key: 'escalate',
      label: '3. 升级网格员',
      state: isEscalatedOrDispatched
        ? 'current'
        : escalateAct || d.escalateStep > 0
          ? 'done'
          : isAcked || isFinished
            ? 'skipped'
            : 'todo',
      ts: escalateAct?.createdAt || null,
      desc: isEscalatedOrDispatched
        ? `超时未确认或已派单，当前由网格员（${d.currentHandler}）跟进`
        : escalateAct || d.escalateStep > 0
          ? `已升级/派单至网格员（${d.currentHandler}）`
          : isAcked || isFinished
            ? '在升级窗口内已及时响应，无需升级'
            : '若倒计时归零仍未确认，将自动升级至责任网格员',
    },
    {
      key: 'ack',
      label: '4. 确认',
      state: isAcked ? 'current' : isFinished || d.ackAt ? 'done' : 'todo',
      ts: ackAct?.createdAt || d.ackAt,
      desc:
        isAcked || isFinished || d.ackAt
          ? `${ackAct?.actorName || d.currentHandler}已确认接警${
              d.responseSec ? `（响应耗时 ${d.responseSec} 秒）` : ''
            }`
          : '等待责任人确认接警',
    },
    {
      key: 'resolve',
      label: '5. 完结',
      state: isFinished ? 'current' : 'todo',
      ts: resolveAct?.createdAt || d.resolvedAt,
      desc: isFinished
        ? st === AlarmStatus.FALSE_POSITIVE
          ? `${resolveAct?.actorName || d.currentHandler}核实为误报并关闭`
          : `${resolveAct?.actorName || d.currentHandler}已完成上门处置并归档`
        : '核实处置完成后归档关闭',
    },
  ]
})

// ---------------- 右侧流水格式化 ----------------
const ACTION_LABEL_MAP: Record<string, string> = {
  NOTIFY: '首次通知',
  ESCALATE: '超时升级',
  ACK: '确认接警',
  DISPATCH: '社区派单',
  RESOLVE: '完结归档',
  MARK_FALSE: '标记误报',
  DEDUP: '去重合并',
}

const CHANNEL_LABEL_MAP: Record<string, string> = {
  PUSH: 'APP推送',
  SMS: '短信',
  CALL: '语音外呼',
  WS: '站内实时',
  INBOX: '站内信',
}

const RESULT_LABEL_MAP: Record<string, string> = {
  SENT: '已发送',
  DELIVERED: '已送达',
  FAILED: '发送失败',
}

function formatActionLabel(act: string): string {
  return ACTION_LABEL_MAP[act] || act
}

function formatChannelLabel(ch: string): string {
  return CHANNEL_LABEL_MAP[ch] || ch
}

function formatResultLabel(res: string): string {
  return RESULT_LABEL_MAP[res] || res
}

function formatActionDetail(act: AlarmAction): string {
  const dt = act.detail
  if (!dt) return ''
  if (typeof dt.note === 'string' && dt.note) return `备注：${dt.note}`
  if (dt.from && dt.to) return `流转：${String(dt.from)} → ${String(dt.to)}`
  if (dt.guardianName) return `指派网格员：${String(dt.guardianName)}`
  if (dt.target) return `接收对象：${String(dt.target)}`
  return ''
}
</script>

<style scoped lang="scss">
.drawer-shell {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: #f5f7fa;
}

.drawer-header {
  display: flex;
  flex-shrink: 0;
  align-items: center;
  justify-content: space-between;
  padding: 14px 20px;
  background: #fff;
  border-bottom: 1px solid $border-color;

  &__left {
    display: flex;
    align-items: center;
    gap: 10px;
  }

  &__title {
    font-size: 16px;
    font-weight: 700;
    color: $text-primary;
  }

  &__id {
    font-family: monospace;
    font-size: 13px;
    color: $text-regular;
  }

  &__right {
    display: flex;
    align-items: center;
    gap: 10px;
  }
}

.drawer-countdown {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 10px;
  font-size: 12px;
  color: #cf1322;
  background: #fff1f0;
  border: 1px solid #ffa39e;
  border-radius: 6px;

  strong {
    font-family: monospace;
    font-size: 15px;
    font-weight: 700;
  }

  &.is-urgent {
    color: #fff;
    background: #cf1322;
    border-color: #cf1322;
    animation: urgent-blink 0.9s ease-in-out infinite;
  }
}

.drawer-body {
  display: flex;
  flex: 1;
  min-height: 0;
  overflow: hidden;
}

.drawer-main {
  flex: 1;
  min-width: 0;
  padding: 16px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.drawer-side {
  width: 228px;
  flex-shrink: 0;
  background: #fff;
  border-left: 1px solid $border-color;
  display: flex;
  flex-direction: column;
  min-height: 0;
}

.panel-card {
  padding: 14px 16px;
  background: #fff;
  border: 1px solid $border-color-light;
  border-radius: 8px;

  &__head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 10px;
  }

  &__title {
    font-size: 14px;
    font-weight: 700;
    color: $text-primary;
    border-left: 3px solid $color-primary;
    padding-left: 8px;
  }

  &__extra {
    font-size: 12px;
    color: $text-regular;

    strong {
      color: $color-primary;
    }
  }
}

/* 老人信息卡 */
.elder-card {
  &__grid {
    display: flex;
    justify-content: space-between;
    gap: 12px;
  }

  &__name-row {
    display: flex;
    align-items: baseline;
    gap: 8px;
  }

  &__name {
    font-size: 17px;
    font-weight: 700;
    color: $text-primary;
  }

  &__age {
    font-size: 13px;
    color: $text-regular;
  }

  &__room {
    padding: 1px 7px;
    font-size: 12px;
    font-weight: 600;
    color: #0958d9;
    background: #e6f4ff;
    border-radius: 4px;
  }

  &__addr {
    margin-top: 4px;
    font-size: 12px;
    color: $text-regular;
  }

  &__tags {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
    margin-top: 8px;
  }

  &__contact {
    flex-shrink: 0;
    padding: 8px 12px;
    background: #fff7e6;
    border: 1px solid #ffe7ba;
    border-radius: 6px;
    text-align: right;
  }

  &__contact-label {
    font-size: 11px;
    color: #ad6800;
  }

  &__contact-person {
    margin-top: 2px;
    font-size: 13px;
    font-weight: 600;
    color: $text-primary;
  }

  &__contact-rel {
    font-size: 12px;
    font-weight: 400;
    color: $text-regular;
  }

  &__tel {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    margin-top: 4px;
    font-family: monospace;
    font-size: 14px;
    font-weight: 700;
    color: #d46b08;
    text-decoration: none;

    &:hover {
      text-decoration: underline;
    }
  }
}

/* 竖向 5 阶段时间轴 */
.stage-timeline {
  display: flex;
  flex-direction: column;
}

.stage-node {
  display: flex;
  gap: 12px;

  &__rail {
    display: flex;
    flex-direction: column;
    align-items: center;
    width: 18px;
    flex-shrink: 0;
  }

  &__dot {
    position: relative;
    width: 12px;
    height: 12px;
    margin-top: 4px;
    border-radius: 50%;
    background: #d9d9d9;
    border: 2px solid #fff;
    box-shadow: 0 0 0 1px #d9d9d9;
  }

  &__pulse {
    position: absolute;
    inset: -4px;
    border-radius: 50%;
    border: 2px solid #cf1322;
    animation: stage-pulse 1.4s ease-out infinite;
  }

  &__line {
    flex: 1;
    width: 2px;
    min-height: 22px;
    margin: 3px 0;
    background: #e5e6eb;
  }

  &__content {
    flex: 1;
    padding-bottom: 12px;
  }

  &__top {
    display: flex;
    align-items: center;
    gap: 8px;
  }

  &__label {
    font-size: 13px;
    font-weight: 600;
    color: $text-primary;
  }

  &__time {
    margin-left: auto;
    font-family: monospace;
    font-size: 11px;
    color: $text-regular;
  }

  &__desc {
    margin-top: 2px;
    font-size: 12px;
    color: $text-regular;
  }

  &.is-done {
    .stage-node__dot {
      background: #52c41a;
      box-shadow: 0 0 0 1px #52c41a;
    }
    .stage-node__line {
      background: #95de64;
    }
  }

  &.is-current {
    .stage-node__dot {
      background: #cf1322;
      box-shadow: 0 0 0 2px rgba(207, 19, 34, 0.25);
    }
    .stage-node__label {
      color: #cf1322;
      font-weight: 700;
    }
    .stage-node__desc {
      color: #1f2329;
      font-weight: 500;
    }
  }

  &.is-skipped {
    opacity: 0.65;
  }
}

/* 现场截图 + 视频 */
.media-grid {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.snapshot-box {
  position: relative;
  height: 210px;
  overflow: hidden;
  cursor: zoom-in;
  background: #0f131a;
  border-radius: 6px;

  &__img {
    width: 100%;
    height: 100%;
    object-fit: cover;
    display: block;
  }

  &__badge {
    position: absolute;
    right: 10px;
    bottom: 8px;
    padding: 2px 8px;
    font-size: 11px;
    color: #fff;
    background: rgba(0, 0, 0, 0.6);
    border-radius: 4px;
  }
}

.clip-box {
  overflow: hidden;
  background: #0f131a;
  border-radius: 6px;

  &__video {
    width: 100%;
    max-height: 200px;
    display: block;
  }
}

/* 右侧处置流水小栏 */
.side-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 14px;
  border-bottom: 1px solid $border-color-light;

  &__title {
    font-size: 13px;
    font-weight: 700;
    color: $text-primary;
  }

  &__count {
    font-size: 12px;
    color: $text-regular;
  }
}

.action-stream {
  flex: 1;
  padding: 12px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.action-item {
  padding: 10px;
  background: #f9fafc;
  border: 1px solid $border-color-light;
  border-radius: 6px;
  font-size: 12px;

  &__top {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 4px;
  }

  &__badge {
    padding: 1px 6px;
    font-size: 11px;
    font-weight: 600;
    color: #0958d9;
    background: #e6f4ff;
    border-radius: 4px;

    &.is-escalate {
      color: #d46b08;
      background: #fff7e6;
    }

    &.is-ack,
    &.is-resolve {
      color: #237804;
      background: #f6ffed;
    }

    &.is-mark_false {
      color: #646a73;
      background: #f2f3f5;
    }
  }

  &__time {
    font-family: monospace;
    font-size: 11px;
    color: $text-regular;
  }

  &__actor {
    color: $text-regular;
  }

  &__actor-id {
    font-size: 11px;
    color: $text-disabled;
  }

  &__channel-row {
    display: flex;
    flex-wrap: wrap;
    gap: 4px;
    margin-top: 6px;
  }

  &__detail {
    margin-top: 6px;
    padding-top: 6px;
    font-size: 11px;
    color: $text-regular;
    border-top: 1px dashed $border-color-light;
  }
}

/* 底部操作栏 */
.drawer-footer {
  display: flex;
  flex-shrink: 0;
  align-items: center;
  justify-content: space-between;
  padding: 12px 20px;
  background: #fff;
  border-top: 1px solid $border-color;

  &__handler {
    font-size: 13px;
    color: $text-regular;
  }

  &__step {
    color: #d46b08;
    font-weight: 600;
  }

  &__btns {
    display: flex;
    align-items: center;
    gap: 10px;
  }

  &__done {
    font-size: 12px;
    color: #237804;
    font-weight: 500;
  }
}

.mono-tag {
  font-family: monospace;
  font-size: 12px;
  color: $text-regular;
}

.text-muted {
  font-size: 12px;
  color: $text-disabled;
}

.preview-body {
  display: flex;
  align-items: center;
  justify-content: center;
  background: #0f131a;
  border-radius: 6px;
  overflow: hidden;
}

.preview-img {
  max-width: 100%;
  max-height: 560px;
  object-fit: contain;
}

@keyframes stage-pulse {
  0% {
    transform: scale(0.95);
    opacity: 0.9;
  }
  100% {
    transform: scale(1.7);
    opacity: 0;
  }
}

@keyframes urgent-blink {
  0%,
  100% {
    opacity: 1;
  }
  50% {
    opacity: 0.72;
  }
}
</style>
