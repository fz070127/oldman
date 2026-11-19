<template>
  <section class="screen-card" :class="{ 'is-alert': alert }">
    <!-- 四角青色装饰角标 -->
    <span class="screen-card__corner is-tl" />
    <span class="screen-card__corner is-tr" />
    <span class="screen-card__corner is-bl" />
    <span class="screen-card__corner is-br" />

    <!-- 左上角带斜切装饰角的标题条 -->
    <header v-if="title" class="screen-card__header">
      <div class="screen-card__title-bar">
        <span class="screen-card__title-dot" />
        <h2 class="screen-card__title">{{ title }}</h2>
        <span v-if="subtitle" class="screen-card__subtitle">{{ subtitle }}</span>
      </div>
      <div v-if="$slots.extra" class="screen-card__extra">
        <slot name="extra" />
      </div>
    </header>

    <div class="screen-card__body">
      <slot />
    </div>
  </section>
</template>

<script setup lang="ts">
defineProps<{
  title?: string
  subtitle?: string
  alert?: boolean
}>()
</script>

<style scoped lang="scss">
.screen-card {
  position: relative;
  display: flex;
  flex-direction: column;
  width: 100%;
  height: 100%;
  min-height: 0;
  background: rgba(16, 32, 72, 0.6);
  border: 1px solid rgba(0, 229, 255, 0.32);
  box-shadow:
    inset 0 0 24px rgba(0, 229, 255, 0.12),
    0 4px 20px rgba(0, 0, 0, 0.32);
  transition:
    border-color 0.3s ease,
    box-shadow 0.3s ease;

  &.is-alert {
    border-color: rgba(255, 59, 92, 0.72);
    box-shadow:
      inset 0 0 28px rgba(255, 59, 92, 0.22),
      0 0 18px rgba(255, 59, 92, 0.25);
  }

  &__corner {
    position: absolute;
    width: 10px;
    height: 10px;
    pointer-events: none;

    &.is-tl {
      top: -1px;
      left: -1px;
      border-top: 2px solid #00e5ff;
      border-left: 2px solid #00e5ff;
    }

    &.is-tr {
      top: -1px;
      right: -1px;
      border-top: 2px solid #00e5ff;
      border-right: 2px solid #00e5ff;
    }

    &.is-bl {
      bottom: -1px;
      left: -1px;
      border-bottom: 2px solid #00e5ff;
      border-left: 2px solid #00e5ff;
    }

    &.is-br {
      right: -1px;
      bottom: -1px;
      border-right: 2px solid #00e5ff;
      border-bottom: 2px solid #00e5ff;
    }
  }

  &__header {
    display: flex;
    flex-shrink: 0;
    align-items: center;
    justify-content: space-between;
    height: 40px;
    padding-right: 14px;
    border-bottom: 1px solid rgba(0, 229, 255, 0.16);
    background: linear-gradient(90deg, rgba(0, 229, 255, 0.1) 0%, rgba(16, 32, 72, 0) 75%);
  }

  /* 左上角斜切装饰角标题条 */
  &__title-bar {
    position: relative;
    display: inline-flex;
    align-items: center;
    gap: 8px;
    height: 100%;
    padding: 0 28px 0 14px;
    background: linear-gradient(90deg, rgba(0, 229, 255, 0.24) 0%, rgba(33, 150, 243, 0.08) 100%);
    clip-path: polygon(0 0, calc(100% - 14px) 0, 100% 100%, 0 100%);
  }

  &__title-dot {
    width: 4px;
    height: 16px;
    background: #00e5ff;
    box-shadow: 0 0 8px #00e5ff;
  }

  &__title {
    margin: 0;
    font-size: 16px;
    font-weight: 600;
    letter-spacing: 1px;
    color: #eaf6ff;
  }

  &__subtitle {
    font-size: 11px;
    letter-spacing: 1px;
    color: rgba(0, 229, 255, 0.65);
    text-transform: uppercase;
  }

  &__extra {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    font-size: 12px;
    color: rgba(200, 225, 255, 0.78);
  }

  &__body {
    position: relative;
    flex: 1;
    min-height: 0;
    padding: 12px 14px;
  }
}
</style>
