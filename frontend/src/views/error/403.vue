<template>
  <div class="forbidden">
    <div class="code">403</div>
    <p class="desc">抱歉，您暂无权限访问该页面</p>
    <el-button type="primary" @click="router.replace('/')">返回首页</el-button>
  </div>
</template>

<script setup lang="ts">
const router = useRouter()
</script>

<style scoped lang="scss">
.forbidden {
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
    color: $color-warning;
  }

  .desc {
    margin: 16px 0 24px;
    color: $text-regular;
  }
}
</style>
