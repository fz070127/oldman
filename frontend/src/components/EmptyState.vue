<template>
  <div class="empty-state">
    <svg class="empty-state__svg" viewBox="0 0 160 120" fill="none" xmlns="http://www.w3.org/2000/svg">
      <ellipse cx="80" cy="104" rx="56" ry="8" fill="#EEF2F8" />
      <rect x="34" y="24" width="92" height="68" rx="8" fill="#F7F9FC" stroke="#D9E2F1" stroke-width="2" />
      <line x1="48" y1="44" x2="96" y2="44" stroke="#C5D2E8" stroke-width="3" stroke-linecap="round" />
      <line x1="48" y1="58" x2="112" y2="58" stroke="#DCE4F2" stroke-width="3" stroke-linecap="round" />
      <line x1="48" y1="72" x2="82" y2="72" stroke="#DCE4F2" stroke-width="3" stroke-linecap="round" />
      <circle cx="114" cy="76" r="16" fill="#E8F1FF" stroke="#1677FF" stroke-width="2" />
      <path d="M109 76H119M114 71V81" stroke="#1677FF" stroke-width="2" stroke-linecap="round" />
    </svg>
    <p class="empty-state__desc">{{ description }}</p>
    <div v-if="actionText || $slots.default" class="empty-state__action">
      <slot>
        <el-button type="primary" size="small" @click="emit('action')">{{ actionText }}</el-button>
      </slot>
    </div>
  </div>
</template>

<script setup lang="ts">
/** 空态组件：SVG 插画 + 文案 + 可选操作按钮 */
withDefaults(
  defineProps<{
    description?: string
    actionText?: string
  }>(),
  {
    description: '暂无符合条件的数据',
    actionText: '',
  },
)

const emit = defineEmits<{
  (e: 'action'): void
}>()
</script>

<style scoped lang="scss">
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 36px 16px;
  text-align: center;

  &__svg {
    width: 140px;
    height: 105px;
  }

  &__desc {
    margin-top: 8px;
    font-size: 14px;
    color: $text-regular;
  }

  &__action {
    margin-top: 14px;
  }
}
</style>
