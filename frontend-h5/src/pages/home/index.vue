<template>
  <view class="home-page">
    <!-- 顶部温暖问候栏 -->
    <view class="greeting-header">
      <view class="greeting-main">
        <text class="greeting-title">{{ greetingText }}，{{ userInfo.nickname }}</text>
        <text class="greeting-sub">幸福里社区智能监护中 · 实时为您守护家人</text>
      </view>
      <image class="family-avatar" :src="userInfo.avatar" mode="aspectFill" />
    </view>

    <!-- 模块一：我的老人卡片（横向滑动） -->
    <view class="section-block">
      <view class="section-header">
        <text class="section-title">我的老人（{{ elders.length }}位）</text>
        <text class="section-hint">左右滑动 · 点击查看</text>
      </view>

      <scroll-view class="elder-scroll" scroll-x="true" show-scrollbar="false">
        <view class="elder-card-list">
          <view
            v-for="elder in elders"
            :key="elder.id"
            class="elder-card"
            :class="{ 'has-alarm': elder.todayAlarmCount > 0 }"
            @click="goAlarmDetail(elder.latestAlarmId)"
          >
            <!-- 顶部：头像 + 姓名/房号 + 在线大圆点状态 -->
            <view class="elder-top">
              <image class="elder-avatar" :src="elder.avatar" mode="aspectFill" />
              <view class="elder-meta">
                <view class="elder-name-row">
                  <text class="elder-name">{{ elder.name }}</text>
                  <text class="elder-relation">{{ elder.relation }} · {{ elder.age }}岁</text>
                </view>
                <text class="elder-room">房号：{{ elder.communityName }} {{ elder.roomNo }}</text>
              </view>
            </view>

            <!-- 中部：在线大圆点状态（绿=在线 / 灰=离线） -->
            <view class="device-status-row">
              <view class="status-dot" :class="elder.online ? 'dot-online' : 'dot-offline'" />
              <text class="device-status-text" :class="elder.online ? 'text-online' : 'text-offline'">
                {{ elder.online ? '监测设备在线' : '监测设备离线' }}
              </text>
              <text v-for="tag in elder.healthTags" :key="tag" class="health-tag">
                {{ tag }}
              </text>
            </view>

            <!-- 底部：今日状态文案（"一切正常" / "有 1 条告警"）+ 行动引导按钮 -->
            <view
              class="today-status-bar"
              :class="elder.todayAlarmCount > 0 ? 'status-alarm' : 'status-normal'"
            >
              <view class="today-status-left">
                <text class="today-label">今日状态：</text>
                <text class="today-value">{{ elder.statusText }}</text>
              </view>
              <text class="today-action">
                {{ elder.todayAlarmCount > 0 ? '立即处理 ›' : '查看记录 ›' }}
              </text>
            </view>
          </view>
        </view>
      </scroll-view>
    </view>

    <!-- 模块二：最近 3 条记录（时间 / 类型 / 状态） -->
    <view class="section-block">
      <view class="section-header">
        <text class="section-title">最近 3 条记录</text>
        <view class="more-link" @click="goAllRecords">
          <text class="more-link-text">全部记录 ›</text>
        </view>
      </view>

      <view class="recent-list">
        <view
          v-for="item in recentAlarms"
          :key="item.id"
          class="recent-card"
          @click="goAlarmDetail(item.id)"
        >
          <view class="recent-main">
            <view class="recent-title-row">
              <text class="recent-type" :class="item.level === 'P0' ? 'type-p0' : ''">
                {{ getEventTypeLabel(item.eventType) }}
              </text>
              <text class="recent-elder">{{ item.elderName }}（{{ item.roomNo }}）</text>
            </view>
            <text class="recent-time">时间：{{ formatDateTime(item.createdAt, true) }}</text>
          </view>

          <view class="recent-right">
            <view class="status-badge" :class="`badge-${getAlarmStatusMeta(item.status).theme}`">
              <text class="status-badge-text">{{ getAlarmStatusMeta(item.status).label }}</text>
            </view>
          </view>
        </view>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { onShow } from '@dcloudio/uni-app'
import { getCurrentUser } from '@/api/auth'
import { getFamilyElders } from '@/api/family'
import { getAlarmList } from '@/api/alarm'
import type { AlarmItem, FamilyElderItem, UserInfo } from '@/types'
import {
  formatDateTime,
  getAlarmStatusMeta,
  getEventTypeLabel,
  getGreetingByTime,
} from '@/utils/format'

const userInfo = ref<UserInfo>({
  id: 'U010',
  username: '13800000001',
  nickname: '张女士',
  phone: '13800000001',
  roleCode: 'FAMILY',
  avatar: '/static/avatar-family.png',
  communityId: 'C01',
  communityName: '幸福里社区',
  permissions: ['family:read', 'alarm:ack'],
  menus: ['family'],
})

const elders = ref<FamilyElderItem[]>([])
const alarms = ref<AlarmItem[]>([])

const greetingText = computed(() => getGreetingByTime())
const recentAlarms = computed(() => alarms.value.slice(0, 3))

async function loadHomeData() {
  const [user, elderList, alarmPage] = await Promise.all([
    getCurrentUser(),
    getFamilyElders(),
    getAlarmList(),
  ])
  userInfo.value = user
  elders.value = elderList
  alarms.value = alarmPage.list
}

function goAlarmDetail(alarmId: string) {
  const targetId = alarmId || 'A001'
  uni.navigateTo({
    url: `/pages/alarm/index?id=${targetId}`,
  })
}

function goAllRecords() {
  uni.switchTab({
    url: '/pages/records/index',
  })
}

onMounted(() => {
  loadHomeData()
})

onShow(() => {
  loadHomeData()
})
</script>

<style scoped lang="scss">
.home-page {
  min-height: 100vh;
  background-color: #f5f7fa;
  padding: 28rpx 28rpx 160rpx;
  box-sizing: border-box;
}

.greeting-header {
  background: linear-gradient(135deg, #2b7fff 0%, #1d68e6 100%);
  border-radius: 24rpx;
  padding: 36rpx 32rpx;
  display: flex;
  align-items: center;
  justify-content: space-between;
  color: #ffffff;
  box-shadow: 0 10rpx 28rpx rgba(43, 127, 255, 0.25);
  margin-bottom: 36rpx;
}

.greeting-main {
  flex: 1;
  padding-right: 20rpx;
}

.greeting-title {
  display: block;
  font-size: 42rpx;
  font-weight: 700;
  color: #ffffff;
  margin-bottom: 10rpx;
}

.greeting-sub {
  display: block;
  font-size: 32rpx;
  color: rgba(255, 255, 255, 0.92);
  line-height: 1.4;
}

.family-avatar {
  width: 96rpx;
  height: 96rpx;
  border-radius: 48rpx;
  border: 4rpx solid rgba(255, 255, 255, 0.85);
  background-color: #ffffff;
  flex-shrink: 0;
}

.section-block {
  margin-bottom: 36rpx;
}

.section-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 20rpx;
}

.section-title {
  font-size: 38rpx;
  font-weight: 700;
  color: #101828;
  white-space: nowrap;
  flex-shrink: 0;
}

.section-hint {
  font-size: 32rpx;
  color: #667085;
  white-space: nowrap;
}

.more-link {
  padding: 8rpx 0;
}

.more-link-text {
  font-size: 32rpx;
  font-weight: 600;
  color: #2b7fff;
}

.elder-scroll {
  width: 100%;
  white-space: nowrap;
}

.elder-scroll ::-webkit-scrollbar {
  display: none;
  width: 0;
  height: 0;
}

.elder-card-list {
  display: inline-flex;
  gap: 24rpx;
  padding-bottom: 8rpx;
}

.elder-card {
  width: 610rpx;
  background-color: #ffffff;
  border-radius: 24rpx;
  padding: 32rpx;
  box-sizing: border-box;
  box-shadow: 0 8rpx 24rpx rgba(16, 24, 40, 0.06);
  border: 2rpx solid #e4e7ec;
  white-space: normal;
  flex-shrink: 0;
}

.elder-card.has-alarm {
  border: 3rpx solid #ff4d4f;
  box-shadow: 0 10rpx 28rpx rgba(255, 77, 79, 0.14);
}

.elder-top {
  display: flex;
  align-items: center;
  margin-bottom: 24rpx;
}

.elder-avatar {
  width: 104rpx;
  height: 104rpx;
  border-radius: 52rpx;
  margin-right: 24rpx;
  background-color: #eef5ff;
  flex-shrink: 0;
}

.elder-meta {
  flex: 1;
}

.elder-name-row {
  display: flex;
  align-items: baseline;
  flex-wrap: wrap;
  gap: 14rpx;
  margin-bottom: 8rpx;
}

.elder-name {
  font-size: 40rpx;
  font-weight: 700;
  color: #101828;
}

.elder-relation {
  font-size: 32rpx;
  color: #475467;
  font-weight: 500;
}

.elder-room {
  display: block;
  font-size: 32rpx;
  color: #344054;
}

.device-status-row {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 14rpx;
  padding: 18rpx 20rpx;
  background-color: #f8fafc;
  border-radius: 16rpx;
  margin-bottom: 24rpx;
}

.status-dot {
  width: 24rpx;
  height: 24rpx;
  border-radius: 12rpx;
  flex-shrink: 0;
}

.dot-online {
  background-color: #10b981;
  box-shadow: 0 0 0 6rpx rgba(16, 185, 129, 0.2);
}

.dot-offline {
  background-color: #98a2b3;
  box-shadow: 0 0 0 6rpx rgba(152, 162, 179, 0.2);
}

.device-status-text {
  font-size: 32rpx;
  font-weight: 600;
  margin-right: 8rpx;
}

.text-online {
  color: #059669;
}

.text-offline {
  color: #667085;
}

.health-tag {
  font-size: 32rpx;
  color: #2b7fff;
  background-color: #eef5ff;
  padding: 4rpx 16rpx;
  border-radius: 10rpx;
}

.today-status-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 22rpx 24rpx;
  border-radius: 18rpx;
  min-height: 48px;
  box-sizing: border-box;
}

.status-alarm {
  background-color: #fff1f0;
  border: 2rpx solid #ffa39e;
}

.status-normal {
  background-color: #ecfdf5;
  border: 2rpx solid #a7f3d0;
}

.today-status-left {
  display: flex;
  align-items: center;
}

.today-label {
  font-size: 32rpx;
  color: #344054;
}

.status-alarm .today-value {
  font-size: 34rpx;
  font-weight: 700;
  color: #ff4d4f;
}

.status-normal .today-value {
  font-size: 34rpx;
  font-weight: 700;
  color: #059669;
}

.status-alarm .today-action {
  font-size: 32rpx;
  font-weight: 700;
  color: #ff4d4f;
}

.status-normal .today-action {
  font-size: 32rpx;
  font-weight: 600;
  color: #059669;
}

.recent-list {
  display: flex;
  flex-direction: column;
  gap: 20rpx;
}

.recent-card {
  background-color: #ffffff;
  border-radius: 24rpx;
  padding: 28rpx 30rpx;
  display: flex;
  align-items: center;
  justify-content: space-between;
  box-shadow: 0 6rpx 18rpx rgba(16, 24, 40, 0.05);
}

.recent-main {
  flex: 1;
  padding-right: 16rpx;
}

.recent-title-row {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 12rpx;
  margin-bottom: 10rpx;
}

.recent-type {
  font-size: 36rpx;
  font-weight: 700;
  color: #101828;
}

.recent-type.type-p0 {
  color: #ff4d4f;
}

.recent-elder {
  font-size: 32rpx;
  color: #344054;
  font-weight: 500;
}

.recent-time {
  display: block;
  font-size: 32rpx;
  color: #667085;
}

.recent-right {
  flex-shrink: 0;
}

.status-badge {
  padding: 10rpx 20rpx;
  border-radius: 14rpx;
}

.status-badge-text {
  font-size: 32rpx;
  font-weight: 600;
}

.badge-danger {
  background-color: #fff1f0;
  color: #ff4d4f;
}

.badge-primary {
  background-color: #eef5ff;
  color: #2b7fff;
}

.badge-warning {
  background-color: #fff7e6;
  color: #d46b08;
}

.badge-success {
  background-color: #ecfdf5;
  color: #059669;
}

.badge-muted {
  background-color: #f2f4f7;
  color: #667085;
}
</style>
