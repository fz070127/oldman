<template>
  <div class="error-page">
    <div class="error-page__card">
      <svg class="error-page__svg" viewBox="0 0 120 120" fill="none">
        <circle cx="60" cy="60" r="48" fill="#E6F4FF" stroke="#91CAFF" stroke-width="2" />
        <circle cx="56" cy="56" r="18" stroke="#1677FF" stroke-width="4" />
        <path d="M69 69L82 82" stroke="#1677FF" stroke-width="4" stroke-linecap="round" />
        <path d="M51 56H61" stroke="#1677FF" stroke-width="3" stroke-linecap="round" />
      </svg>
      <div class="error-page__code is-primary">404</div>
      <h2 class="error-page__title">访问的页面不存在</h2>
      <p class="error-page__desc">抱歉，您访问的链接地址有误或该页面已被移除，请检查地址后重试</p>
      <div class="error-page__actions">
        <el-button @click="router.back()">返回上一页</el-button>
        <el-button type="primary" @click="router.replace('/')">返回工作台</el-button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
const router = useRouter()
</script>

<style scoped lang="scss">
.error-page {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 100vh;
  padding: 24px;
  background: $bg-page;

  &__card {
    display: flex;
    flex-direction: column;
    align-items: center;
    max-width: 460px;
    padding: 48px 40px;
    text-align: center;
    background: $bg-white;
    border-radius: $radius-large;
    box-shadow: $shadow-card;
  }

  &__svg {
    width: 96px;
    height: 96px;
    margin-bottom: 12px;
  }

  &__code {
    font-size: 76px;
    font-weight: 800;
    line-height: 1.05;

    &.is-primary {
      color: $color-primary;
    }
  }

  &__title {
    margin: 12px 0 8px;
    font-size: 20px;
    font-weight: 600;
    color: $text-primary;
  }

  &__desc {
    margin: 0 0 28px;
    font-size: 14px;
    line-height: 1.6;
    color: $text-regular;
  }

  &__actions {
    display: flex;
    gap: 12px;
  }
}
</style>
