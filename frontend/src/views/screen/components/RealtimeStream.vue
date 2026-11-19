<template>
  <ScreenCard title="实时事件流" subtitle="REALTIME">
    <template #extra>
      <span class="stream-badge">
        <i class="stream-badge__dot" />
        最近 {{ items.length }} / 12 条
      </span>
    </template>

    <div class="stream-wrap">
      <!-- 表头 -->
      <div class="stream-head">
        <span>时间</span>
        <span>房号</span>
        <span>事件类型</span>
        <span class="is-right">级别</span>
      </div>

      <!-- 事件列表（TransitionGroup 实现顶部插入 + 整体平滑下移） -->
      <TransitionGroup v-if="items.length > 0" name="stream-item" tag="ul" class="stream-list">
        <li
          v-for="item in items"
          :key="item.id"
          class="stream-row"
          :class="[`is-${item.level.toLowerCase()}`, { 'is-fresh': item.id === latestId }]"
          :title="`${item.communityName} · ${item.elderName}（${item.roomNo}室）`"
        >
          <span class="stream-row__time">{{ formatHHmmss(item.occurredAt) }}</span>
          <span class="stream-row__room" :title="`${item.communityName} ${item.roomNo}`">
            {{ item.roomNo }}室
          </span>
          <span class="stream-row__type">
            {{ eventTypeLabel(item.type) }}
            <small class="stream-row__elder">{{ item.elderName }}</small>
          </span>
          <span class="stream-row__level" :class="`level-${item.level.toLowerCase()}`">
            {{ item.level }}
          </span>
        </li>
      </TransitionGroup>

      <div v-else class="stream-empty">暂无实时监测事件</div>
    </div>
  </ScreenCard>
</template>

<script setup lang="ts">
import dayjs from 'dayjs'
import type { RealtimeItem } from '@/types/dashboard'
import { EventType } from '@/types/event'
import ScreenCard from './ScreenCard.vue'

defineProps<{
  items: RealtimeItem[]
  latestId?: string
}>()

function formatHHmmss(ts: string): string {
  const d = dayjs(ts)
  return d.isValid() ? d.format('HH:mm:ss') : '--:--:--'
}

function eventTypeLabel(type: EventType): string {
  return type === EventType.LONG_LIE ? '久躺异常' : '疑似跌倒'
}
</script>

<style scoped lang="scss">
.stream-badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-family: 'DIN Alternate', 'Consolas', monospace;
  font-size: 12px;
  color: #00e5ff;

  &__dot {
    width: 6px;
    height: 6px;
    background: #00e676;
    border-radius: 50%;
    box-shadow: 0 0 8px #00e676;
    animation: blink 1.6s ease-in-out infinite;
  }
}

.stream-wrap {
  display: flex;
  flex-direction: column;
  height: 100%;
  overflow: hidden;
}

.stream-head {
  display: grid;
  grid-template-columns: 76px 68px 1fr 50px;
  gap: 8px;
  padding: 6px 10px;
  margin-bottom: 6px;
  font-size: 12px;
  color: rgba(0, 229, 255, 0.75);
  background: rgba(0, 229, 255, 0.08);
  border-bottom: 1px solid rgba(0, 229, 255, 0.22);

  .is-right {
    text-align: right;
  }
}

.stream-list {
  position: relative;
  display: flex;
  flex: 1;
  flex-direction: column;
  gap: 5px;
  margin: 0;
  padding: 0;
  overflow: hidden;
  list-style: none;
}

.stream-row {
  display: grid;
  grid-template-columns: 76px 68px 1fr 50px;
  align-items: center;
  gap: 8px;
  height: 36px;
  padding: 0 10px;
  font-size: 13px;
  color: #dceeff;
  background: rgba(10, 24, 58, 0.65);
  border: 1px solid rgba(0, 229, 255, 0.12);
  border-left: 3px solid rgba(0, 229, 255, 0.45);
  transition:
    background-color 0.3s ease,
    border-color 0.3s ease;

  &.is-p0 {
    border-left-color: #ff3b5c;
    background: rgba(255, 59, 92, 0.1);
  }

  &.is-p1 {
    border-left-color: #ffb300;
  }

  &.is-p2 {
    border-left-color: #2196f3;
  }

  &.is-fresh {
    border-color: rgba(255, 59, 92, 0.7);
    background: rgba(255, 59, 92, 0.22);
    box-shadow: inset 0 0 16px rgba(255, 59, 92, 0.25);
  }

  &__time {
    font-family: 'DIN Alternate', 'Consolas', 'Courier New', monospace;
    font-size: 13px;
    color: #00e5ff;
    font-variant-numeric: tabular-nums;
  }

  &__room {
    overflow: hidden;
    font-family: 'DIN Alternate', 'Consolas', monospace;
    color: #ffffff;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  &__type {
    display: flex;
    align-items: center;
    gap: 6px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  &__elder {
    font-size: 12px;
    color: rgba(185, 215, 255, 0.68);
  }

  &__level {
    justify-self: end;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    min-width: 38px;
    height: 20px;
    padding: 0 6px;
    font-family: 'DIN Alternate', 'Consolas', monospace;
    font-size: 12px;
    font-weight: 700;
    border-radius: 2px;

    &.level-p0 {
      color: #fff;
      background: #ff3b5c;
      box-shadow: 0 0 8px rgba(255, 59, 92, 0.6);
    }

    &.level-p1 {
      color: #0a1128;
      background: #ffb300;
    }

    &.level-p2 {
      color: #fff;
      background: #2196f3;
    }
  }
}

.stream-empty {
  display: flex;
  flex: 1;
  align-items: center;
  justify-content: center;
  font-size: 14px;
  color: rgba(185, 215, 255, 0.5);
}

/* 新事件从顶部插入、列表整体平滑下移过渡动画 */
.stream-item-move,
.stream-item-enter-active,
.stream-item-leave-active {
  transition: all 0.45s cubic-bezier(0.22, 1, 0.36, 1);
}

.stream-item-enter-from {
  opacity: 0;
  transform: translateY(-28px);
}

.stream-item-leave-to {
  opacity: 0;
  transform: translateY(20px);
}

.stream-item-leave-active {
  position: absolute;
  left: 0;
  right: 0;
}

@keyframes blink {
  0%,
  100% {
    opacity: 1;
  }
  50% {
    opacity: 0.3;
  }
}
</style>
