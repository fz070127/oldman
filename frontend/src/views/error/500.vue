<template>
  <div class="error-page">
    <div class="error-page__card">
      <svg class="error-page__svg" viewBox="0 0 120 120" fill="none">
        <circle cx="60" cy="60" r="48" fill="#FFF1F0" stroke="#FFA39E" stroke-width="2" />
        <rect
          x="36"
          y="38"
          width="48"
          height="44"
          rx="6"
          fill="#FFF9F9"
          stroke="#CF1322"
          stroke-width="3"
        />
        <path d="M60 50V62" stroke="#CF1322" stroke-width="4" stroke-linecap="round" />
        <circle cx="60" cy="70" r="2.5" fill="#CF1322" />
      </svg>
      <div class="error-page__code is-danger">500</div>
      <h2 class="error-page__title">服务器内部异常</h2>
      <p class="error-page__desc">抱歉，服务器遇到意外状况暂时无法完成请求，请稍后刷新重试或返回工作台</p>
      <div class="error-page__actions">
        <el-button @click="reloadPage">刷新重试</el-button>
        <el-button type="primary" @click="router.replace('/')">返回工作台</el-button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
const router = useRouter()

function reloadPage() {
  window.location.reload()
}
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

    &.is-danger {
      color: $color-danger;
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
