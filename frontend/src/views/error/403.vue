<template>
  <div class="error-page">
    <div class="error-page__card">
      <svg class="error-page__svg" viewBox="0 0 120 120" fill="none">
        <circle cx="60" cy="60" r="48" fill="#FFF7E6" stroke="#FFD591" stroke-width="2" />
        <rect x="40" y="54" width="40" height="32" rx="6" fill="#FAAD14" />
        <path
          d="M48 54V44C48 37.3726 53.3726 32 60 32C66.6274 32 72 37.3726 72 44V54"
          stroke="#D46B08"
          stroke-width="4"
          stroke-linecap="round"
        />
        <circle cx="60" cy="70" r="4" fill="#FFFFFF" />
      </svg>
      <div class="error-page__code is-warning">403</div>
      <h2 class="error-page__title">暂无访问权限</h2>
      <p class="error-page__desc">抱歉，您当前登录的角色暂无权限访问该功能模块，请联系管理员授权</p>
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

    &.is-warning {
      color: $color-warning;
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
