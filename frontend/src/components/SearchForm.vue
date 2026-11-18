<template>
  <div class="search-form">
    <el-form :inline="true" :model="modelValue" class="search-form__inner" @submit.prevent="emit('search')">
      <div class="search-form__fields" :class="{ 'is-collapsed': collapsible && collapsed }">
        <slot :collapsed="collapsed" />
      </div>
      <div class="search-form__actions">
        <el-button type="primary" :icon="Search" @click="emit('search')">查询</el-button>
        <el-button :icon="RefreshRight" @click="emit('reset')">重置</el-button>
        <el-button
          v-if="collapsible"
          link
          type="primary"
          class="search-form__toggle"
          @click="collapsed = !collapsed"
        >
          {{ collapsed ? '展开' : '收起' }}
          <el-icon class="ml-4">
            <ArrowDown v-if="collapsed" />
            <ArrowUp v-else />
          </el-icon>
        </el-button>
      </div>
    </el-form>
  </div>
</template>

<script setup lang="ts">
/** 可折叠筛选表单容器：左侧表单项插槽 + 右侧「查询 / 重置 / 展开收起」 */
import { ArrowDown, ArrowUp, RefreshRight, Search } from '@element-plus/icons-vue'

const props = withDefaults(
  defineProps<{
    modelValue?: Record<string, unknown>
    /** 是否显示展开/收起按钮 */
    collapsible?: boolean
    /** 默认是否收起 */
    defaultCollapsed?: boolean
  }>(),
  {
    modelValue: () => ({}),
    collapsible: false,
    defaultCollapsed: false,
  },
)

const emit = defineEmits<{
  (e: 'search'): void
  (e: 'reset'): void
}>()

const collapsed = ref(props.defaultCollapsed)
</script>

<style scoped lang="scss">
.search-form {
  padding: 16px 20px 4px;
  margin-bottom: 16px;
  background: $bg-white;
  border-radius: $radius-large;
  box-shadow: $shadow-card;

  &__inner {
    display: flex;
    flex-wrap: wrap;
    align-items: flex-start;
    justify-content: space-between;
    gap: 8px;
  }

  &__fields {
    display: flex;
    flex: 1;
    flex-wrap: wrap;
    align-items: center;
    min-width: 0;

    :deep(.el-form-item) {
      margin-right: 16px;
      margin-bottom: 12px;
    }
  }

  &__actions {
    display: flex;
    flex-shrink: 0;
    align-items: center;
    margin-bottom: 12px;
  }
}
</style>
