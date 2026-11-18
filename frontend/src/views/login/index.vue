<template>
  <div class="login">
    <!-- 左侧品牌区 -->
    <section class="login__brand">
      <div class="login__brand-inner">
        <div class="login__logo">
          <img src="/favicon.svg" alt="logo" />
          <span>银铃守护</span>
        </div>
        <h1 class="login__title">独居老人跌倒行为智能检测预警系统</h1>
        <p class="login__slogan">10 秒感知跌倒，60 秒闭环处置 —— 让每一次跌倒都有人知道</p>
        <ul class="login__features">
          <li><span class="dot" />边缘 AI 实时检测，隐私不出户</li>
          <li><span class="dot" />家属秒级推送，超时自动升级网格员</li>
          <li><span class="dot" />社区大屏一屏统览，处置全程留痕</li>
        </ul>
      </div>
      <div class="login__copyright">© 2026 银铃守护项目组</div>
    </section>

    <!-- 右侧表单区 -->
    <section class="login__form-wrap">
      <div class="login__card">
        <h2 class="login__card-title">欢迎登录</h2>
        <p class="login__card-sub">Web 管理端 · 管理员 / 社区 / 网格员</p>

        <el-form ref="formRef" :model="form" :rules="rules" size="large" @keyup.enter="onSubmit">
          <el-form-item prop="username">
            <el-input v-model.trim="form.username" placeholder="请输入用户名" :prefix-icon="User" clearable />
          </el-form-item>
          <el-form-item prop="password">
            <el-input
              v-model="form.password"
              type="password"
              placeholder="请输入密码"
              :prefix-icon="Lock"
              show-password
            />
          </el-form-item>
          <div class="login__options">
            <el-checkbox v-model="remember">记住我</el-checkbox>
          </div>
          <el-button type="primary" class="login__submit" :loading="loading" @click="onSubmit">
            登 录
          </el-button>
        </el-form>
        <p v-if="useMock" class="login__tip">Mock 账号：admin / guardian01 / family01（密码 123456）</p>
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
import type { FormInstance, FormRules } from 'element-plus'
import { Lock, User } from '@element-plus/icons-vue'
import { useUserStore } from '@/stores/user'
import { storage, StorageKeys } from '@/utils/storage'

const userStore = useUserStore()
const router = useRouter()
const route = useRoute()

const useMock = import.meta.env.VITE_USE_MOCK === 'true'

const formRef = ref<FormInstance>()
const loading = ref(false)

// “记住我”仅记住用户名，不保存密码
const rememberedName = storage.get(StorageKeys.REMEMBER_USERNAME) || ''
const remember = ref(!!rememberedName)
const form = reactive({ username: rememberedName, password: '' })

const rules: FormRules = {
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }],
}

async function onSubmit() {
  if (loading.value) return
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return

  loading.value = true
  try {
    await userStore.login({ username: form.username, password: form.password })
    if (remember.value) storage.set(StorageKeys.REMEMBER_USERNAME, form.username)
    else storage.remove(StorageKeys.REMEMBER_USERNAME)

    ElMessage.success('登录成功')
    const redirect = typeof route.query.redirect === 'string' ? route.query.redirect : '/'
    router.replace(redirect)
  } catch {
    // 错误提示已由 request 拦截器统一处理
  } finally {
    loading.value = false
  }
}
</script>

<style scoped lang="scss">
.login {
  display: flex;
  height: 100vh;
  min-height: 560px;
  background: $bg-white;

  // ---------- 左侧 ----------
  &__brand {
    position: relative;
    display: flex;
    flex: 0 0 56%;
    flex-direction: column;
    justify-content: center;
    padding: 0 8%;
    overflow: hidden;
    color: #fff;
    background: linear-gradient(135deg, #0a2a6b 0%, #0f4bb8 55%, #1677ff 100%);

    // 装饰光晕
    &::before,
    &::after {
      position: absolute;
      content: '';
      border-radius: 50%;
      background: rgba(255, 255, 255, 0.06);
    }
    &::before {
      top: -120px;
      right: -120px;
      width: 420px;
      height: 420px;
    }
    &::after {
      bottom: -160px;
      left: -100px;
      width: 360px;
      height: 360px;
    }
  }

  &__brand-inner {
    position: relative;
    z-index: 1;
  }

  &__logo {
    display: flex;
    align-items: center;
    gap: 12px;
    font-size: 22px;
    font-weight: 600;
    letter-spacing: 2px;

    img {
      width: 40px;
      height: 40px;
      border-radius: 10px;
      box-shadow: 0 4px 12px rgba(0, 0, 0, 0.2);
    }
  }

  &__title {
    margin-top: 48px;
    font-size: 34px;
    font-weight: 600;
    line-height: 1.4;
  }

  &__slogan {
    margin-top: 16px;
    font-size: 16px;
    opacity: 0.85;
  }

  &__features {
    margin-top: 40px;

    li {
      display: flex;
      align-items: center;
      margin-bottom: 14px;
      font-size: 14px;
      opacity: 0.9;
    }

    .dot {
      width: 6px;
      height: 6px;
      margin-right: 10px;
      background: #69b1ff;
      border-radius: 50%;
    }
  }

  &__copyright {
    position: absolute;
    bottom: 24px;
    left: 8%;
    font-size: 12px;
    opacity: 0.6;
  }

  // ---------- 右侧 ----------
  &__form-wrap {
    display: flex;
    flex: 1;
    align-items: center;
    justify-content: center;
    background: $bg-page;
  }

  &__card {
    width: 400px;
    padding: 44px 40px 32px;
    background: $bg-white;
    border-radius: 12px;
    box-shadow: 0 8px 32px rgba(15, 75, 184, 0.08);
  }

  &__card-title {
    font-size: 24px;
    font-weight: 600;
    color: $text-primary;
  }

  &__card-sub {
    margin: 8px 0 32px;
    font-size: 13px;
    color: $text-regular;
  }

  &__options {
    display: flex;
    justify-content: space-between;
    margin: -4px 0 20px;
  }

  &__submit {
    width: 100%;
    height: 44px;
    font-size: 16px;
  }

  &__tip {
    margin-top: 16px;
    font-size: 12px;
    color: $text-disabled;
    text-align: center;
  }
}

// 窄屏隐藏左侧品牌区
@media (max-width: 900px) {
  .login__brand {
    display: none;
  }
}
</style>
