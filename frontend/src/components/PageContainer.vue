<template>
  <div class="page-container">
    <div v-if="title || $slots.title || $slots.extra" class="page-container__header">
      <div class="page-container__title">
        <slot name="title">{{ title }}</slot>
      </div>
      <div class="page-container__extra">
        <!-- 右侧操作区 -->
        <slot name="extra" />
      </div>
    </div>
    <div class="page-container__body" :style="{ padding: bodyPadding }">
      <slot />
    </div>
  </div>
</template>

<script setup lang="ts">
/** 页面容器：白底卡片 + 标题 + 右侧操作区插槽 */
withDefaults(
  defineProps<{
    title?: string
    bodyPadding?: string
  }>(),
  { title: '', bodyPadding: '20px' },
)
</script>

<style scoped lang="scss">
.page-container {
  background: $bg-white;
  border-radius: $radius-large;
  box-shadow: $shadow-card;

  &__header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    min-height: 56px;
    padding: 12px 20px;
    border-bottom: 1px solid $border-color-light;
  }

  &__title {
    font-size: 16px;
    font-weight: 600;
    color: $text-primary;
  }

  &__extra {
    display: flex;
    align-items: center;
    gap: 8px;
  }
}
</style>
