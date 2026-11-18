<template>
  <PageContainer :title="title">
    <el-empty :description="`「${title}」页面建设中`" />
  </PageContainer>
</template>

<script setup lang="ts">
/** F1 阶段业务路由占位页 */
import PageContainer from '@/components/PageContainer.vue'

const route = useRoute()
const title = computed(() => route.meta.title || '')
</script>
