<template>
  <el-config-provider :locale="locale" :size="'default'">
    <router-view />
  </el-config-provider>
</template>

<script setup lang="ts">
import { locale } from '@/i18n'
import { setupRealtime } from '@/stores/alarm'

// 全局唯一实时连接：只在根组件初始化一次，路由切换不受影响
onMounted(() => {
  setupRealtime()
})
</script>
