<template>
  <view class="records-page">
    <!-- 顶部统计与筛选栏 -->
    <view class="filter-bar">
      <view
        v-for="tab in filterTabs"
        :key="tab.value"
        class="filter-tab"
        :class="{ active: activeFilter === tab.value }"
        @click="activeFilter = tab.value"
      >
        <text class="filter-tab-text">{{ tab.label }}</text>
      </view>
    </view>

    <!-- 时间倒序告警记录列表 -->
    <view class="record-list">
      <view
        v-for="item in filteredList"
        :key="item.id"
        class="record-card"
        @click="goAlarmDetail(item.id)"
      >
        <!-- 卡片头部：级别色块 + 类型 + 状态标签 -->
        <view class="record-header">
          <view class="type-wrap">
            <view class="level-tag" :class="`level-${item.level.toLowerCase()}`">
              <text class="level-tag-text">{{ getLevelLabel(item.level) }}</text>
            </view>
            <text class="record-type">{{ getEventTypeLabel(item.eventType) }}</text>
          </view>

          <view class="status-pill" :class="`pill-${getAlarmStatusMeta(item.status).theme}`">
            <text class="status-pill-text">{{ getAlarmStatusMeta(item.status).label }}</text>
          </view>
        </view>

        <!-- 卡片主体：老人姓名 + 房号 + 时间 + 责任人 -->
        <view class="record-body">
          <view class="meta-line">
            <text class="meta-label">老人姓名：</text>
            <text class="meta-val strong">{{ item.elderName }}（{{ item.communityName }} {{ item.roomNo }}）</text>
          </view>
          <view class="meta-line">
            <text class="meta-label">告警时间：</text>
            <text class="meta-val">{{ formatDateTime(item.createdAt, true) }}</text>
          </view>
          <view class="meta-line">
            <text class="meta-label">当前处置：</text>
            <text class="meta-val">{{ item.currentHandler }}</text>
          </view>
        </view>

        <!-- 卡片底部：操作入口 -->
        <view class="record-footer">
          <text class="confidence-text">AI 识别置信度 {{ Math.round(item.confidence * 100) }}%</text>
          <text class="detail-btn-text">查看详情 ›</text>
        </view>
      </view>

      <view v-if="filteredList.length === 0" class="empty-box">
        <text class="empty-text">暂无符合条件的告警记录</text>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { onShow } from '@dcloudio/uni-app'
import { getAlarmList } from '@/api/alarm'
import type { AlarmItem } from '@/types'
import {
  formatDateTime,
  getAlarmStatusMeta,
  getEventTypeLabel,
  getLevelLabel,
} from '@/utils/format'

const filterTabs = [
  { label: '全部记录', value: 'ALL' },
  { label: '待处理', value: 'PENDING' },
  { label: '处理中', value: 'HANDLING' },
  { label: '已完结', value: 'DONE' },
]

const activeFilter = ref('ALL')
const list = ref<AlarmItem[]>([])

const filteredList = computed(() => {
  if (activeFilter.value === 'ALL') return list.value
  if (activeFilter.value === 'PENDING') {
    return list.value.filter((i) => i.status === 'PENDING' || i.status === 'ESCALATED')
  }
  if (activeFilter.value === 'HANDLING') {
    return list.value.filter(
      (i) => i.status === 'ACKNOWLEDGED' || i.status === 'COMMUNITY_DISPATCHED'
    )
  }
  return list.value.filter((i) => i.status === 'RESOLVED' || i.status === 'FALSE_POSITIVE')
})

async function fetchRecords() {
  const res = await getAlarmList()
  list.value = res.list
}

function goAlarmDetail(id: string) {
  uni.navigateTo({
    url: `/pages/alarm/index?id=${id}`,
  })
}

onMounted(() => {
  fetchRecords()
})

onShow(() => {
  fetchRecords()
})
</script>

<style scoped lang="scss">
.records-page {
  min-height: 100vh;
  background-color: #f5f7fa;
  padding: 24rpx 28rpx 160rpx;
  box-sizing: border-box;
}

.filter-bar {
  display: flex;
  background-color: #ffffff;
  border-radius: 24rpx;
  padding: 10rpx;
  margin-bottom: 28rpx;
  box-shadow: 0 4rpx 14rpx rgba(16, 24, 40, 0.04);
}

.filter-tab {
  flex: 1;
  height: 96rpx;
  min-height: 48px;
  border-radius: 18rpx;
  display: flex;
  align-items: center;
  justify-content: center;
}

.filter-tab.active {
  background-color: #2b7fff;
}

.filter-tab-text {
  font-size: 32rpx;
  font-weight: 600;
  color: #475467;
}

.filter-tab.active .filter-tab-text {
  color: #ffffff;
}

.record-list {
  display: flex;
  flex-direction: column;
  gap: 24rpx;
}

.record-card {
  background-color: #ffffff;
  border-radius: 24rpx;
  padding: 30rpx;
  box-shadow: 0 8rpx 22rpx rgba(16, 24, 40, 0.05);
}

.record-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding-bottom: 22rpx;
  margin-bottom: 22rpx;
  border-bottom: 2rpx solid #f2f4f7;
}

.type-wrap {
  display: flex;
  align-items: center;
  gap: 14rpx;
}

.level-tag {
  padding: 6rpx 16rpx;
  border-radius: 10rpx;
}

.level-tag-text {
  font-size: 32rpx;
  font-weight: 700;
  color: #ffffff;
}

.level-p0 {
  background-color: #ff4d4f;
}

.level-p1 {
  background-color: #fa8c16;
}

.level-p2 {
  background-color: #2b7fff;
}

.record-type {
  font-size: 38rpx;
  font-weight: 700;
  color: #101828;
}

.status-pill {
  padding: 8rpx 20rpx;
  border-radius: 14rpx;
}

.status-pill-text {
  font-size: 32rpx;
  font-weight: 600;
}

.pill-danger {
  background-color: #fff1f0;
  color: #ff4d4f;
}

.pill-primary {
  background-color: #eef5ff;
  color: #2b7fff;
}

.pill-warning {
  background-color: #fff7e6;
  color: #d46b08;
}

.pill-success {
  background-color: #ecfdf5;
  color: #059669;
}

.pill-muted {
  background-color: #f2f4f7;
  color: #667085;
}

.record-body {
  display: flex;
  flex-direction: column;
  gap: 14rpx;
  margin-bottom: 22rpx;
}

.meta-line {
  display: flex;
  align-items: flex-start;
}

.meta-label {
  font-size: 32rpx;
  color: #667085;
  width: 170rpx;
  flex-shrink: 0;
}

.meta-val {
  font-size: 32rpx;
  color: #344054;
  flex: 1;
}

.meta-val.strong {
  font-weight: 700;
  color: #101828;
}

.record-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding-top: 18rpx;
  border-top: 2rpx dashed #e4e7ec;
}

.confidence-text {
  font-size: 32rpx;
  color: #667085;
}

.detail-btn-text {
  font-size: 32rpx;
  font-weight: 700;
  color: #2b7fff;
}

.empty-box {
  background-color: #ffffff;
  border-radius: 24rpx;
  padding: 80rpx 32rpx;
  text-align: center;
}

.empty-text {
  font-size: 32rpx;
  color: #667085;
}
</style>
