<template>
  <div class="empty-state" :class="{ 'is-error': mode === 'error' }">
    <!-- 错误态 SVG 插画 -->
    <svg
      v-if="mode === 'error'"
      class="empty-state__svg"
      viewBox="0 0 160 120"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
    >
      <ellipse cx="80" cy="104" rx="56" ry="8" fill="#FFF1F0" />
      <rect
        x="34"
        y="24"
        width="92"
        height="68"
        rx="8"
        fill="#FFF9F9"
        stroke="#FFA39E"
        stroke-width="2"
      />
      <line
        x1="48"
        y1="44"
        x2="92"
        y2="44"
        stroke="#FFCCC7"
        stroke-width="3"
        stroke-linecap="round"
      />
      <line
        x1="48"
        y1="58"
        x2="106"
        y2="58"
        stroke="#FFE7E6"
        stroke-width="3"
        stroke-linecap="round"
      />
      <circle cx="114" cy="76" r="16" fill="#FFF1F0" stroke="#CF1322" stroke-width="2" />
      <path
        d="M114 69V77M114 82H114.02"
        stroke="#CF1322"
        stroke-width="2.2"
        stroke-linecap="round"
      />
    </svg>

    <!-- 空数据态 SVG 插画 -->
    <svg
      v-else
      class="empty-state__svg"
      viewBox="0 0 160 120"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
    >
      <ellipse cx="80" cy="104" rx="56" ry="8" fill="#EEF2F8" />
      <rect
        x="34"
        y="24"
        width="92"
        height="68"
        rx="8"
        fill="#F7F9FC"
        stroke="#D9E2F1"
        stroke-width="2"
      />
      <line
        x1="48"
        y1="44"
        x2="96"
        y2="44"
        stroke="#C5D2E8"
        stroke-width="3"
        stroke-linecap="round"
      />
      <line
        x1="48"
        y1="58"
        x2="112"
        y2="58"
        stroke="#DCE4F2"
        stroke-width="3"
        stroke-linecap="round"
      />
      <line
        x1="48"
        y1="72"
        x2="82"
        y2="72"
        stroke="#DCE4F2"
        stroke-width="3"
        stroke-linecap="round"
      />
      <circle cx="114" cy="76" r="16" fill="#E8F1FF" stroke="#1677FF" stroke-width="2" />
      <path d="M109 76H119M114 71V81" stroke="#1677FF" stroke-width="2" stroke-linecap="round" />
    </svg>

    <h4 class="empty-state__title">
      {{ title || (mode === 'error' ? '数据加载失败' : '暂无相关记录') }}
    </h4>
    <p class="empty-state__desc">{{ description }}</p>

    <div v-if="actionText || $slots.default" class="empty-state__action">
      <slot>
        <el-button
          :type="mode === 'error' ? 'danger' : 'primary'"
          :plain="mode !== 'error'"
          size="small"
          @click="emit('action')"
        >
          {{ actionText }}
        </el-button>
      </slot>
    </div>
  </div>
</template>

<script setup lang="ts">
/**
 * 空态与错误重试通用组件：
 * - mode="empty"：SVG 插画 + 标题 + 详细引导说明 + 可选刷新/重置按钮（绝不只有“暂无数据”四个字）
 * - mode="error"：异常 SVG 插画 + 错误说明 +「加载失败，点击重试」按钮
 */
withDefaults(
  defineProps<{
    mode?: 'empty' | 'error'
    title?: string
    description?: string
    actionText?: string
  }>(),
  {
    mode: 'empty',
    title: '',
    description: '当前筛选条件下暂无匹配记录，可尝试调整筛选条件或刷新列表',
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
  line-height: 1.5;
  text-align: center;

  &__svg {
    width: 140px;
    height: 105px;
  }

  &__title {
    margin: 8px 0 4px;
    font-size: 15px;
    font-weight: 600;
    color: $text-primary;
  }

  &.is-error &__title {
    color: $color-danger;
  }

  &__desc {
    max-width: 420px;
    margin: 0;
    font-size: 13px;
    color: $text-regular;
  }

  &__action {
    margin-top: 14px;
  }
}
</style>
