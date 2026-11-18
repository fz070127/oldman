<template>
  <div class="not-found">
    <div class="code">404</div>
    <p class="desc">抱歉，您访问的页面不存在</p>
    <el-button type="primary" @click="router.replace('/')">返回首页</el-button>
  </div>
</template>

<script setup lang="ts">
const router = useRouter()
</script>

<style scoped lang="scss">
.not-found {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100vh;
  background: $bg-page;

  .code {
    font-size: 96px;
    font-weight: 700;
    line-height: 1;
    color: $color-primary;
  }

  .desc {
    margin: 16px 0 24px;
    color: $text-regular;
  }
}
</style>
