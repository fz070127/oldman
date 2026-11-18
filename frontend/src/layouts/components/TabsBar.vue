<template>
  <div class="tabs-bar">
    <el-scrollbar class="tabs-bar__scroll">
      <div class="tabs-bar__list">
        <div
          v-for="tab in tabsStore.tabs"
          :key="tab.path"
          class="tabs-bar__item"
          :class="{ 'is-active': tab.path === route.path }"
          @click="router.push(tab.fullPath)"
          @contextmenu.prevent="openMenu($event, tab)"
        >
          <span>{{ tab.title }}</span>
          <el-icon v-if="!tab.affix" class="tabs-bar__close" @click.stop="closeTab(tab)"><Close /></el-icon>
        </div>
      </div>
    </el-scrollbar>

    <!-- 右键菜单 -->
    <ul v-show="menu.visible" class="tabs-bar__menu" :style="{ left: menu.x + 'px', top: menu.y + 'px' }">
      <li @click="closeOthers">关闭其他</li>
      <li @click="closeAll">关闭全部</li>
    </ul>
  </div>
</template>

<script setup lang="ts">
import { Close } from '@element-plus/icons-vue'
import { useTabsStore, type TabItem } from '@/stores/tabs'

const tabsStore = useTabsStore()
const route = useRoute()
const router = useRouter()

// 固定标签 + 路由变化时追加标签
tabsStore.initAffixTabs(router.getRoutes())
watch(
  () => route.fullPath,
  () => tabsStore.addTab(route),
  { immediate: true },
)

function closeTab(tab: TabItem) {
  const next = tabsStore.closeTab(tab.path, route.path)
  if (next) router.push(next.fullPath)
  else if (tab.path === route.path) router.push('/')
}

// ---------------- 右键菜单 ----------------
const menu = reactive({ visible: false, x: 0, y: 0, target: null as TabItem | null })

function openMenu(e: MouseEvent, tab: TabItem) {
  menu.target = tab
  menu.x = e.clientX
  menu.y = e.clientY
  menu.visible = true
}

function hideMenu() {
  menu.visible = false
}

function closeOthers() {
  if (!menu.target) return
  tabsStore.closeOthers(menu.target.path)
  if (menu.target.path !== route.path) router.push(menu.target.fullPath)
  hideMenu()
}

function closeAll() {
  tabsStore.closeAll()
  const first = tabsStore.tabs[0]
  router.push(first ? first.fullPath : '/')
  hideMenu()
}

onMounted(() => document.addEventListener('click', hideMenu))
onBeforeUnmount(() => document.removeEventListener('click', hideMenu))
</script>

<style scoped lang="scss">
.tabs-bar {
  flex-shrink: 0;
  height: $tabs-height;
  background: $bg-white;
  border-bottom: 1px solid $border-color;

  &__list {
    display: flex;
    align-items: center;
    height: $tabs-height;
    padding: 0 12px;
    white-space: nowrap;
  }

  &__item {
    display: inline-flex;
    align-items: center;
    height: 28px;
    padding: 0 12px;
    margin-right: 6px;
    font-size: 13px;
    color: $text-regular;
    cursor: pointer;
    background: $bg-white;
    border: 1px solid $border-color;
    border-radius: 4px;
    transition: $transition-base;

    &:hover {
      color: $color-primary;
    }

    &.is-active {
      color: #fff;
      background: $color-primary;
      border-color: $color-primary;
    }
  }

  &__close {
    margin-left: 6px;
    font-size: 12px;
    border-radius: 50%;

    &:hover {
      background: rgba(0, 0, 0, 0.15);
    }
  }

  &__menu {
    position: fixed;
    z-index: 3000;
    padding: 4px 0;
    margin: 0;
    font-size: 13px;
    background: #fff;
    border-radius: 4px;
    box-shadow: 0 2px 12px rgba(0, 0, 0, 0.12);

    li {
      padding: 6px 16px;
      cursor: pointer;

      &:hover {
        color: $color-primary;
        background: #e8f1ff;
      }
    }
  }
}
</style>
