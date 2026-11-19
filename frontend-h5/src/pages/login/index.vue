<template>
  <view class="login-page">
    <!-- 顶部温暖品牌区 -->
    <view class="brand-header">
      <view class="brand-badge">
        <text class="brand-badge-icon">♥</text>
      </view>
      <text class="brand-title">银铃守护 · 家属端</text>
      <text class="brand-subtitle">24 小时智能跌倒监测，守护父母居家平安</text>
    </view>

    <!-- 登录卡片（圆角 12px / 24rpx） -->
    <view class="login-card">
      <view class="card-heading">
        <text class="card-title">手机号快捷登录</text>
        <text class="card-desc">请使用已绑定老人档案的家属手机号登录</text>
      </view>

      <!-- 手机号输入 -->
      <view class="form-group">
        <text class="form-label">手机号码</text>
        <view class="input-box">
          <text class="input-prefix">+86</text>
          <input
            v-model="phone"
            class="form-input"
            type="number"
            :maxlength="11"
            placeholder="请输入家属手机号"
            placeholder-class="input-placeholder"
          />
        </view>
      </view>

      <!-- 验证码输入 -->
      <view class="form-group">
        <text class="form-label">短信验证码</text>
        <view class="input-box code-box">
          <input
            v-model="code"
            class="form-input"
            type="number"
            :maxlength="6"
            placeholder="请输入 6 位验证码"
            placeholder-class="input-placeholder"
          />
          <button
            class="send-code-btn"
            :disabled="countdown > 0"
            @click="handleSendCode"
          >
            {{ countdown > 0 ? `${countdown}s 后重发` : '获取验证码' }}
          </button>
        </view>
      </view>

      <!-- 演示账号提示条 -->
      <view class="demo-tip" @click="fillDemoAccount">
        <text class="demo-tip-label">演示账号：</text>
        <text class="demo-tip-val">13800000001 / 验证码 123456（点击填入）</text>
      </view>

      <!-- 登录大按钮（高度 52px / 104rpx >= 48px） -->
      <button
        class="login-btn"
        :loading="submitting"
        :disabled="submitting"
        @click="handleLogin"
      >
        立即登录
      </button>
    </view>

    <!-- 底部关怀说明 -->
    <view class="login-footer">
      <text class="footer-text">幸福里社区智慧养老服务中心 · 隐私脱敏保护已开启</text>
    </view>
  </view>
</template>

<script setup lang="ts">
import { ref, onUnmounted } from 'vue'
import { loginByPhone } from '@/api/auth'
import { MOCK_ACCOUNT } from '@/mock'

const phone = ref(MOCK_ACCOUNT.PHONE)
const code = ref(MOCK_ACCOUNT.CODE)
const submitting = ref(false)
const countdown = ref(0)
let timer: ReturnType<typeof setInterval> | null = null

function fillDemoAccount() {
  phone.value = MOCK_ACCOUNT.PHONE
  code.value = MOCK_ACCOUNT.CODE
  uni.showToast({
    title: '已填入演示账号',
    icon: 'none',
  })
}

function handleSendCode() {
  if (!/^1\d{10}$/.test(phone.value.trim())) {
    uni.showToast({
      title: '请先输入 11 位手机号码',
      icon: 'none',
    })
    return
  }
  code.value = MOCK_ACCOUNT.CODE
  countdown.value = 60
  uni.showToast({
    title: '验证码已发送：123456',
    icon: 'none',
  })
  if (timer) clearInterval(timer)
  timer = setInterval(() => {
    if (countdown.value <= 1) {
      countdown.value = 0
      if (timer) clearInterval(timer)
    } else {
      countdown.value -= 1
    }
  }, 1000)
}

async function handleLogin() {
  if (!phone.value.trim()) {
    uni.showToast({ title: '请输入手机号码', icon: 'none' })
    return
  }
  if (!code.value.trim()) {
    uni.showToast({ title: '请输入验证码', icon: 'none' })
    return
  }
  submitting.value = true
  try {
    await loginByPhone({
      phone: phone.value.trim(),
      code: code.value.trim(),
    })
    uni.showToast({
      title: '登录成功',
      icon: 'success',
    })
    setTimeout(() => {
      uni.switchTab({
        url: '/pages/home/index',
      })
    }, 200)
  } catch (err) {
    const msg = err instanceof Error ? err.message : '登录失败，请检查验证码'
    uni.showToast({
      title: msg,
      icon: 'none',
    })
  } finally {
    submitting.value = false
  }
}

onUnmounted(() => {
  if (timer) clearInterval(timer)
})
</script>

<style scoped lang="scss">
.login-page {
  min-height: 100vh;
  background: linear-gradient(180deg, #ebf3ff 0%, #f7f9fc 48%, #f7f9fc 100%);
  padding: 72rpx 32rpx 48rpx;
  box-sizing: border-box;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
}

.brand-header {
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  margin-bottom: 44rpx;
}

.brand-badge {
  width: 112rpx;
  height: 112rpx;
  border-radius: 28rpx;
  background: linear-gradient(135deg, #2b7fff 0%, #1a66eb 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 12rpx 28rpx rgba(43, 127, 255, 0.28);
  margin-bottom: 24rpx;
}

.brand-badge-icon {
  color: #ffffff;
  font-size: 56rpx;
  line-height: 1;
}

.brand-title {
  font-size: 46rpx;
  font-weight: 700;
  color: #1d2939;
  margin-bottom: 12rpx;
}

.brand-subtitle {
  font-size: 32rpx;
  color: #475467;
  line-height: 1.5;
}

.login-card {
  background-color: #ffffff;
  border-radius: 24rpx;
  padding: 44rpx 36rpx;
  box-shadow: 0 12rpx 36rpx rgba(16, 24, 40, 0.06);
}

.card-heading {
  margin-bottom: 36rpx;
}

.card-title {
  display: block;
  font-size: 40rpx;
  font-weight: 700;
  color: #101828;
  margin-bottom: 10rpx;
}

.card-desc {
  display: block;
  font-size: 32rpx;
  color: #667085;
  line-height: 1.4;
}

.form-group {
  margin-bottom: 32rpx;
}

.form-label {
  display: block;
  font-size: 32rpx;
  font-weight: 600;
  color: #344054;
  margin-bottom: 14rpx;
}

.input-box {
  display: flex;
  align-items: center;
  background-color: #f8fafc;
  border: 2rpx solid #d0d5dd;
  border-radius: 20rpx;
  padding: 0 24rpx;
  height: 112rpx;
  min-height: 56px;
  box-sizing: border-box;
}

.input-prefix {
  font-size: 34rpx;
  font-weight: 600;
  color: #344054;
  padding-right: 20rpx;
  margin-right: 20rpx;
  border-right: 2rpx solid #e4e7ec;
}

.form-input {
  flex: 1;
  height: 100%;
  font-size: 36rpx;
  color: #101828;
  font-weight: 500;
}

.input-placeholder {
  color: #98a2b3;
  font-size: 32rpx;
}

.code-box {
  padding-right: 8rpx;
}

.send-code-btn {
  margin: 0;
  height: 96rpx;
  min-height: 48px;
  line-height: 96rpx;
  padding: 0 24rpx;
  font-size: 32rpx;
  font-weight: 600;
  color: #2b7fff;
  background-color: #eef5ff;
  border-radius: 16rpx;
  border: none;
  flex-shrink: 0;
}

.send-code-btn::after {
  border: none;
}

.demo-tip {
  background-color: #fff8ed;
  border: 2rpx solid #fed7aa;
  border-radius: 16rpx;
  padding: 20rpx 24rpx;
  margin-bottom: 36rpx;
  display: flex;
  flex-wrap: wrap;
  align-items: center;
}

.demo-tip-label {
  font-size: 32rpx;
  font-weight: 600;
  color: #c2410c;
}

.demo-tip-val {
  font-size: 32rpx;
  color: #9a3412;
}

.login-btn {
  width: 100%;
  height: 104rpx;
  min-height: 52px;
  line-height: 104rpx;
  background: #2b7fff;
  color: #ffffff;
  font-size: 36rpx;
  font-weight: 700;
  border-radius: 24rpx;
  border: none;
  box-shadow: 0 8rpx 24rpx rgba(43, 127, 255, 0.35);
}

.login-btn::after {
  border: none;
}

.login-btn:active {
  opacity: 0.9;
}

.login-footer {
  margin-top: 40rpx;
  text-align: center;
}

.footer-text {
  font-size: 32rpx;
  color: #667085;
}
</style>
