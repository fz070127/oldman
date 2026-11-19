<template>
  <view class="profile-page">
    <!-- 顶部账号信息卡片（圆角 12px / 24rpx） -->
    <view class="account-card">
      <view class="account-main">
        <image class="account-avatar" :src="userInfo.avatar" mode="aspectFill" />
        <view class="account-info">
          <view class="name-line">
            <text class="account-name">{{ userInfo.nickname }}</text>
            <view class="role-badge">
              <text class="role-badge-text">认证家属</text>
            </view>
          </view>
          <text class="account-phone">账号：{{ userInfo.phone }}</text>
          <text class="account-community">社区：{{ userInfo.communityName }}（监护 {{ elders.length }} 位老人）</text>
        </view>
      </view>
    </view>

    <!-- 通知设置（开关） -->
    <view class="panel-card">
      <text class="panel-title">通知设置</text>

      <view class="setting-list">
        <view class="setting-row">
          <view class="setting-text-group">
            <text class="setting-name">告警推送通知</text>
            <text class="setting-desc">跌倒或久躺时实时推送通知</text>
          </view>
          <switch
            :checked="settings.pushEnabled"
            color="#2B7FFF"
            @change="onToggleSetting('pushEnabled', $event)"
          />
        </view>

        <view class="setting-row">
          <view class="setting-text-group">
            <text class="setting-name">紧急短信通知</text>
            <text class="setting-desc">P0/P1 告警同步发送手机短信</text>
          </view>
          <switch
            :checked="settings.smsEnabled"
            color="#2B7FFF"
            @change="onToggleSetting('smsEnabled', $event)"
          />
        </view>

        <view class="setting-row">
          <view class="setting-text-group">
            <text class="setting-name">夜间电话强提醒</text>
            <text class="setting-desc">60 秒未确认自动语音电话呼叫</text>
          </view>
          <switch
            :checked="settings.callNightEnabled"
            color="#2B7FFF"
            @change="onToggleSetting('callNightEnabled', $event)"
          />
        </view>
      </view>
    </view>

    <!-- 社区服务热线 -->
    <view class="panel-card">
      <view class="guardian-row">
        <view class="guardian-info">
          <text class="setting-name">责任网格员：李网格</text>
          <text class="setting-desc">13700002222 · 幸福里社区</text>
        </view>
        <button class="call-guardian-btn" @click="callGuardian">
          联系网格员
        </button>
      </view>
    </view>

    <!-- 退出登录大按钮（高度 >= 48px） -->
    <button class="logout-btn" @click="handleLogout">
      退出登录
    </button>
  </view>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { onShow } from '@dcloudio/uni-app'
import { getCurrentUser, logout } from '@/api/auth'
import {
  getFamilyElders,
  getNotificationSettings,
  updateNotificationSettings,
} from '@/api/family'
import type {
  FamilyElderItem,
  FamilyNotificationSettings,
  UserInfo,
} from '@/types'

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
const settings = ref<FamilyNotificationSettings>({
  pushEnabled: true,
  smsEnabled: true,
  callNightEnabled: true,
})

async function loadProfile() {
  const [user, elderList, notify] = await Promise.all([
    getCurrentUser(),
    getFamilyElders(),
    getNotificationSettings(),
  ])
  userInfo.value = user
  elders.value = elderList
  settings.value = notify
}

async function onToggleSetting(
  key: keyof FamilyNotificationSettings,
  event: unknown
) {
  const detail = (event as { detail?: { value?: boolean } })?.detail
  const nextVal = Boolean(detail?.value)
  settings.value = {
    ...settings.value,
    [key]: nextVal,
  }
  await updateNotificationSettings(settings.value)
  uni.showToast({
    title: nextVal ? '已开启通知' : '已关闭通知',
    icon: 'none',
  })
}

function callGuardian() {
  uni.makePhoneCall({
    phoneNumber: '13700002222',
    fail: () => {
      uni.showToast({
        title: '正在呼叫李网格：13700002222',
        icon: 'none',
      })
    },
  })
}

function handleLogout() {
  uni.showModal({
    title: '确认退出登录',
    content: '退出登录后将无法实时接收跌倒告警推送，确定要退出当前账号吗？',
    confirmText: '退出登录',
    cancelText: '取消',
    confirmColor: '#FF4D4F',
    success: async (res) => {
      if (res.confirm) {
        await logout()
        uni.reLaunch({
          url: '/pages/login/index',
        })
      }
    },
  })
}

onMounted(() => {
  loadProfile()
})

onShow(() => {
  loadProfile()
})
</script>

<style scoped lang="scss">
.profile-page {
  min-height: 100vh;
  background-color: #f5f7fa;
  padding: 28rpx 28rpx 160rpx;
  box-sizing: border-box;
}

.account-card {
  background: linear-gradient(135deg, #2b7fff 0%, #1a62db 100%);
  border-radius: 24rpx;
  padding: 36rpx 32rpx;
  color: #ffffff;
  margin-bottom: 28rpx;
  box-shadow: 0 10rpx 28rpx rgba(43, 127, 255, 0.25);
}

.account-main {
  display: flex;
  align-items: center;
}

.account-avatar {
  width: 116rpx;
  height: 116rpx;
  border-radius: 58rpx;
  border: 4rpx solid rgba(255, 255, 255, 0.9);
  margin-right: 28rpx;
  background-color: #ffffff;
  flex-shrink: 0;
}

.account-info {
  flex: 1;
}

.name-line {
  display: flex;
  align-items: center;
  gap: 16rpx;
  margin-bottom: 10rpx;
}

.account-name {
  font-size: 42rpx;
  font-weight: 700;
  color: #ffffff;
}

.role-badge {
  background-color: rgba(255, 255, 255, 0.22);
  padding: 4rpx 18rpx;
  border-radius: 12rpx;
}

.role-badge-text {
  font-size: 32rpx;
  color: #ffffff;
  font-weight: 600;
}

.account-phone {
  display: block;
  font-size: 32rpx;
  color: rgba(255, 255, 255, 0.94);
  margin-bottom: 6rpx;
}

.account-community {
  display: block;
  font-size: 32rpx;
  color: rgba(255, 255, 255, 0.9);
}

.bind-summary {
  background-color: rgba(255, 255, 255, 0.14);
  border-radius: 18rpx;
  padding: 22rpx 16rpx;
  display: flex;
  align-items: center;
  justify-content: space-around;
}

.summary-item {
  display: flex;
  flex-direction: column;
  align-items: center;
}

.summary-num {
  font-size: 36rpx;
  font-weight: 700;
  color: #ffffff;
  margin-bottom: 4rpx;
}

.summary-label {
  font-size: 32rpx;
  color: rgba(255, 255, 255, 0.88);
}

.summary-divider {
  width: 2rpx;
  height: 56rpx;
  background-color: rgba(255, 255, 255, 0.24);
}

.panel-card {
  background-color: #ffffff;
  border-radius: 24rpx;
  padding: 32rpx;
  margin-bottom: 28rpx;
  box-shadow: 0 6rpx 18rpx rgba(16, 24, 40, 0.05);
}

.panel-title {
  display: block;
  font-size: 38rpx;
  font-weight: 700;
  color: #101828;
  margin-bottom: 24rpx;
}

.elder-mini-list {
  display: flex;
  flex-direction: column;
  gap: 20rpx;
}

.elder-mini-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 20rpx 24rpx;
  background-color: #f8fafc;
  border-radius: 16rpx;
}

.elder-mini-left {
  flex: 1;
}

.elder-mini-name {
  display: block;
  font-size: 34rpx;
  font-weight: 700;
  color: #101828;
  margin-bottom: 6rpx;
}

.elder-mini-addr {
  display: block;
  font-size: 32rpx;
  color: #667085;
}

.elder-mini-status {
  font-size: 32rpx;
  font-weight: 700;
  padding: 6rpx 18rpx;
  border-radius: 12rpx;
}

.elder-mini-status.online {
  background-color: #ecfdf5;
  color: #059669;
}

.elder-mini-status.offline {
  background-color: #f2f4f7;
  color: #667085;
}

.setting-list {
  display: flex;
  flex-direction: column;
}

.setting-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 24rpx 0;
  border-bottom: 2rpx solid #f2f4f7;
}

.setting-row:last-child {
  border-bottom: none;
  padding-bottom: 0;
}

.setting-text-group {
  flex: 1;
  padding-right: 24rpx;
}

.setting-name {
  display: block;
  font-size: 34rpx;
  font-weight: 600;
  color: #101828;
  margin-bottom: 8rpx;
}

.setting-desc {
  display: block;
  font-size: 32rpx;
  color: #667085;
  line-height: 1.4;
}

.guardian-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 20rpx;
}

.guardian-info {
  flex: 1;
}

.call-guardian-btn {
  margin: 0;
  height: 96rpx;
  min-height: 48px;
  line-height: 96rpx;
  padding: 0 28rpx;
  background-color: #eef5ff;
  color: #2b7fff;
  font-size: 32rpx;
  font-weight: 700;
  border-radius: 20rpx;
  border: none;
  flex-shrink: 0;
}

.call-guardian-btn::after {
  border: none;
}

.logout-btn {
  width: 100%;
  height: 104rpx;
  min-height: 52px;
  line-height: 104rpx;
  background-color: #ffffff;
  color: #ff4d4f;
  border: 3rpx solid #ff4d4f;
  border-radius: 24rpx;
  font-size: 36rpx;
  font-weight: 700;
  margin-top: 12rpx;
}

.logout-btn::after {
  border: none;
}
</style>
