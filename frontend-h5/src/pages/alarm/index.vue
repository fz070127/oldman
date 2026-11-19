<template>
  <view class="alarm-page">
    <!-- 顶部紧急告警横幅：大号红色标题「检测到跌倒」 -->
    <view class="alarm-hero-card">
      <view class="alarm-level-row">
        <view class="level-pill">
          <text class="level-pill-text">{{ alarm?.level || 'P0' }} 紧急告警</text>
        </view>
        <text class="status-tag-text">
          {{ alarm ? getAlarmStatusMeta(alarm.status).label : '待处理' }}
        </text>
      </view>

      <text class="alarm-big-title">检测到跌倒</text>

      <!-- 时间 + 老人姓名房号 -->
      <view class="alarm-info-grid">
        <view class="info-row">
          <text class="info-label">发生时间：</text>
          <text class="info-value">
            {{ alarm ? formatDateTime(alarm.event.occurredAt, true) : '2026-11-19 16:42:15' }}
          </text>
        </view>
        <view class="info-row">
          <text class="info-label">老人信息：</text>
          <text class="info-value highlight">
            {{ alarm?.elder.name || '王秀兰' }}（{{ alarm?.elder.age || 78 }}岁 · {{ alarm?.elder.address || '幸福里社区 3 栋 302 室' }}）
          </text>
        </view>
        <view class="info-row">
          <text class="info-label">AI 判定：</text>
          <text class="info-value">
            置信度 {{ alarm ? Math.round(alarm.event.confidence * 100) : 94 }}% · 倒地静止 {{ alarm?.event.features.stillDurationSec || 15 }} 秒
          </text>
        </view>
      </view>
    </view>

    <!-- 处理后状态反馈条：显示「已通知社区，网格员正在前往」 -->
    <view v-if="isHandled" class="handled-banner">
      <view class="handled-icon">✓</view>
      <view class="handled-content">
        <text class="handled-title">已通知社区，网格员正在前往</text>
        <text class="handled-sub">
          当前责任人：{{ alarm?.currentHandler || '李网格（13700002222）' }}
        </text>
      </view>
    </view>

    <!-- 现场截图（脱敏图）卡片 -->
    <view class="snapshot-card">
      <view class="card-header">
        <text class="card-title">现场截图（脱敏图）</text>
        <text class="privacy-badge">隐私已脱敏</text>
      </view>
      <view class="snapshot-wrapper">
        <image
          class="snapshot-img"
          :src="alarm?.event.snapshotUrl || '/static/fall-snapshot.png'"
          mode="widthFix"
        />
        <view class="snapshot-overlay-top">
          <text class="overlay-text">EDGE-0001 · 客厅监测区 · 隐私脱敏模式</text>
        </view>
        <view class="snapshot-overlay-bottom">
          <text class="overlay-alert-tag">
            FALL 跌倒确认 ({{ alarm ? Math.round(alarm.event.confidence * 100) : 94 }}%)
          </text>
        </view>
      </view>
    </view>

    <!-- 两个大按钮（并排，高度 64px / 128rpx） -->
    <view class="action-section">
      <view class="dual-btn-row">
        <button
          class="big-action-btn btn-ack"
          :loading="loadingAction === 'ack'"
          @click="confirmAck"
        >
          <text class="btn-main-text">我马上过去</text>
        </button>

        <button
          class="big-action-btn btn-dispatch"
          :loading="loadingAction === 'dispatch'"
          @click="confirmDispatch"
        >
          <text class="btn-main-text">联系不上，求助社区</text>
        </button>
      </view>
    </view>

    <!-- 底部小字「如情况紧急请直接拨打 120」+ [拨打 120] 按钮 -->
    <view class="emergency-footer">
      <text class="emergency-note">如情况紧急请直接拨打 120</text>
      <button class="call-120-btn" @click="handleCall120">
        拨打 120
      </button>
    </view>

    <!-- 处置时间轴 -->
    <view v-if="alarm && alarm.timeline.length" class="timeline-card">
      <text class="card-title">处置进展记录</text>
      <view class="timeline-list">
        <view
          v-for="(step, idx) in alarm.timeline"
          :key="idx"
          class="timeline-item"
        >
          <view class="timeline-dot" :class="{ active: idx === alarm.timeline.length - 1 }" />
          <view class="timeline-body">
            <text class="timeline-time">{{ formatDateTime(step.ts, true) }}</text>
            <text class="timeline-text">{{ step.text }}</text>
          </view>
        </view>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { onLoad } from '@dcloudio/uni-app'
import { ackAlarm, dispatchAlarm, getAlarmDetail } from '@/api/alarm'
import type { AlarmDetail } from '@/types'
import { formatDateTime, getAlarmStatusMeta } from '@/utils/format'

const alarmId = ref('A001')
const alarm = ref<AlarmDetail | null>(null)
const loadingAction = ref<'' | 'ack' | 'dispatch'>('')
const hasTriggeredHandle = ref(false)

const isHandled = computed(() => {
  if (hasTriggeredHandle.value) return true
  if (!alarm.value) return false
  return (
    alarm.value.status === 'COMMUNITY_DISPATCHED' ||
    alarm.value.status === 'ACKNOWLEDGED' ||
    alarm.value.status === 'RESOLVED'
  )
})

function resolveIdFromUrl(): string {
  if (typeof window !== 'undefined' && window.location) {
    const hash = window.location.hash || ''
    const queryMatch = hash.match(/[?&]id=([^&#]+)/)
    if (queryMatch && queryMatch[1]) {
      return decodeURIComponent(queryMatch[1])
    }
    const pathMatch = hash.match(/\/pages\/alarm\/([^/?#]+)/)
    if (pathMatch && pathMatch[1] && pathMatch[1] !== 'index') {
      return decodeURIComponent(pathMatch[1])
    }
  }
  return 'A001'
}

async function fetchDetail(id: string) {
  const data = await getAlarmDetail(id)
  alarm.value = data
}

onLoad((options) => {
  const id = (options && options.id) || resolveIdFromUrl()
  alarmId.value = id
  fetchDetail(id)
})

onMounted(() => {
  if (!alarm.value) {
    const id = alarmId.value || resolveIdFromUrl()
    fetchDetail(id)
  }
})

/** 二次确认：[我马上过去] -> ack */
function confirmAck() {
  uni.showModal({
    title: '确认亲自前往',
    content: '确认您已收到跌倒告警并马上前往老人家中核实吗？系统将同步告知社区网格员。',
    confirmText: '确认前往',
    cancelText: '取消',
    confirmColor: '#2B7FFF',
    success: async (res) => {
      if (res.confirm) {
        loadingAction.value = 'ack'
        try {
          const updated = await ackAlarm(alarmId.value, {
            note: '家属已确认：我马上过去，社区网格员同步备勤前往',
          })
          alarm.value = updated
          hasTriggeredHandle.value = true
          uni.showToast({
            title: '已确认响应并同步社区',
            icon: 'success',
          })
        } finally {
          loadingAction.value = ''
        }
      }
    },
  })
}

/** 二次确认：[联系不上，求助社区] -> dispatch */
function confirmDispatch() {
  uni.showModal({
    title: '确认求助社区网格员',
    content: '确认联系不上老人，立即呼叫幸福里社区网格员上门紧急处置吗？',
    confirmText: '立即求助',
    cancelText: '取消',
    confirmColor: '#FF4D4F',
    success: async (res) => {
      if (res.confirm) {
        loadingAction.value = 'dispatch'
        try {
          const updated = await dispatchAlarm(alarmId.value, {
            guardianId: 'G01',
            note: '家属联系不上老人，紧急求助社区网格员前往',
          })
          alarm.value = updated
          hasTriggeredHandle.value = true
          uni.showToast({
            title: '已通知社区网格员前往',
            icon: 'success',
          })
        } finally {
          loadingAction.value = ''
        }
      }
    },
  })
}

/** 二次确认：拨打 120 急救电话 */
function handleCall120() {
  uni.showModal({
    title: '紧急拨打 120',
    content: '如怀疑老人发生骨折或意识不清，请立即呼叫 120 急救中心。是否立即拨打？',
    confirmText: '立即拨打',
    cancelText: '取消',
    confirmColor: '#FF4D4F',
    success: (res) => {
      if (res.confirm) {
        uni.makePhoneCall({
          phoneNumber: '120',
          fail: () => {
            uni.showToast({
              title: '正在为您呼叫 120 急救中心',
              icon: 'none',
            })
          },
        })
      }
    },
  })
}
</script>

<style scoped lang="scss">
.alarm-page {
  min-height: 100vh;
  background-color: #f5f7fa;
  padding: 24rpx 28rpx 64rpx;
  box-sizing: border-box;
}

.alarm-hero-card {
  background: linear-gradient(180deg, #fff1f0 0%, #ffffff 100%);
  border: 3rpx solid #ff4d4f;
  border-radius: 24rpx;
  padding: 32rpx;
  margin-bottom: 24rpx;
  box-shadow: 0 10rpx 28rpx rgba(255, 77, 79, 0.12);
}

.alarm-level-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16rpx;
}

.level-pill {
  background-color: #ff4d4f;
  padding: 6rpx 20rpx;
  border-radius: 12rpx;
}

.level-pill-text {
  color: #ffffff;
  font-size: 32rpx;
  font-weight: 700;
}

.status-tag-text {
  font-size: 32rpx;
  font-weight: 700;
  color: #cf1322;
}

.alarm-big-title {
  display: block;
  font-size: 56rpx;
  font-weight: 800;
  color: #ff4d4f;
  letter-spacing: 2rpx;
  margin-bottom: 24rpx;
  line-height: 1.25;
}

.alarm-info-grid {
  display: flex;
  flex-direction: column;
  gap: 14rpx;
  background-color: #ffffff;
  border-radius: 16rpx;
  padding: 22rpx 24rpx;
  border: 2rpx solid #ffccc7;
}

.info-row {
  display: flex;
  align-items: flex-start;
  line-height: 1.45;
}

.info-label {
  font-size: 32rpx;
  color: #667085;
  flex-shrink: 0;
  width: 165rpx;
}

.info-value {
  font-size: 32rpx;
  color: #1d2939;
  font-weight: 500;
  flex: 1;
}

.info-value.highlight {
  font-weight: 700;
  color: #101828;
}

.handled-banner {
  background-color: #ecfdf5;
  border: 3rpx solid #10b981;
  border-radius: 24rpx;
  padding: 28rpx 30rpx;
  margin-bottom: 24rpx;
  display: flex;
  align-items: center;
  box-shadow: 0 8rpx 20rpx rgba(16, 185, 129, 0.14);
}

.handled-icon {
  width: 64rpx;
  height: 64rpx;
  border-radius: 32rpx;
  background-color: #10b981;
  color: #ffffff;
  font-size: 38rpx;
  font-weight: 700;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-right: 24rpx;
  flex-shrink: 0;
}

.handled-content {
  flex: 1;
}

.handled-title {
  display: block;
  font-size: 36rpx;
  font-weight: 700;
  color: #065f46;
  margin-bottom: 6rpx;
}

.handled-sub {
  display: block;
  font-size: 32rpx;
  color: #047857;
}

.snapshot-card {
  background-color: #ffffff;
  border-radius: 24rpx;
  padding: 28rpx;
  margin-bottom: 28rpx;
  box-shadow: 0 6rpx 20rpx rgba(16, 24, 40, 0.05);
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 20rpx;
}

.card-title {
  font-size: 36rpx;
  font-weight: 700;
  color: #101828;
  white-space: nowrap;
}

.privacy-badge {
  font-size: 32rpx;
  color: #2b7fff;
  background-color: #eef5ff;
  padding: 6rpx 18rpx;
  border-radius: 12rpx;
  font-weight: 600;
  white-space: nowrap;
}

.snapshot-wrapper {
  position: relative;
  border-radius: 18rpx;
  overflow: hidden;
  background-color: #1c2333;
}

.snapshot-img {
  width: 100%;
  display: block;
}

.snapshot-overlay-top {
  position: absolute;
  top: 16rpx;
  left: 16rpx;
  right: 16rpx;
  background-color: rgba(16, 24, 40, 0.72);
  padding: 10rpx 18rpx;
  border-radius: 10rpx;
}

.overlay-text {
  color: #e4e7ec;
  font-size: 32rpx;
}

.snapshot-overlay-bottom {
  position: absolute;
  bottom: 16rpx;
  left: 16rpx;
}

.overlay-alert-tag {
  background-color: rgba(255, 77, 79, 0.92);
  color: #ffffff;
  font-size: 32rpx;
  font-weight: 700;
  padding: 8rpx 18rpx;
  border-radius: 10rpx;
}

.action-section {
  margin-bottom: 28rpx;
}

.action-tip {
  display: block;
  font-size: 32rpx;
  color: #344054;
  font-weight: 600;
  margin-bottom: 18rpx;
}

.dual-btn-row {
  display: flex;
  flex-direction: row;
  gap: 20rpx;
}

.big-action-btn {
  flex: 1;
  height: 128rpx;
  min-height: 64px;
  border-radius: 24rpx;
  border: none;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0 16rpx;
  margin: 0;
  box-sizing: border-box;
}

.big-action-btn::after {
  border: none;
}

.btn-ack {
  background-color: #2b7fff;
  color: #ffffff;
  box-shadow: 0 8rpx 22rpx rgba(43, 127, 255, 0.3);
}

.btn-dispatch {
  background-color: #ff4d4f;
  color: #ffffff;
  box-shadow: 0 8rpx 22rpx rgba(255, 77, 79, 0.3);
}

.btn-main-text {
  font-size: 32rpx;
  font-weight: 700;
  color: #ffffff;
  line-height: 1.3;
  text-align: center;
}

.timeline-card {
  background-color: #ffffff;
  border-radius: 24rpx;
  padding: 28rpx;
  margin-bottom: 28rpx;
  box-shadow: 0 6rpx 18rpx rgba(16, 24, 40, 0.05);
}

.timeline-list {
  margin-top: 20rpx;
  display: flex;
  flex-direction: column;
  gap: 22rpx;
}

.timeline-item {
  display: flex;
  align-items: flex-start;
}

.timeline-dot {
  width: 20rpx;
  height: 20rpx;
  border-radius: 10rpx;
  background-color: #d0d5dd;
  margin-top: 12rpx;
  margin-right: 20rpx;
  flex-shrink: 0;
}

.timeline-dot.active {
  background-color: #2b7fff;
  box-shadow: 0 0 0 6rpx rgba(43, 127, 255, 0.2);
}

.timeline-body {
  flex: 1;
}

.timeline-time {
  display: block;
  font-size: 32rpx;
  color: #667085;
  margin-bottom: 4rpx;
}

.timeline-text {
  display: block;
  font-size: 32rpx;
  color: #1d2939;
  line-height: 1.45;
}

.emergency-footer {
  background-color: #fff1f0;
  border: 2rpx solid #ffa39e;
  border-radius: 24rpx;
  padding: 24rpx 28rpx;
  text-align: center;
  margin-bottom: 24rpx;
}

.emergency-note {
  display: block;
  font-size: 32rpx;
  color: #cf1322;
  font-weight: 600;
  margin-bottom: 20rpx;
}

.call-120-btn {
  width: 100%;
  height: 96rpx;
  min-height: 48px;
  line-height: 96rpx;
  background-color: #ffffff;
  color: #ff4d4f;
  border: 3rpx solid #ff4d4f;
  border-radius: 20rpx;
  font-size: 36rpx;
  font-weight: 700;
}

.call-120-btn::after {
  border: none;
}
</style>
