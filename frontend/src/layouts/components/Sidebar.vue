<template>
  <aside class="sidebar" :class="{ 'is-collapsed': collapsed }">
    <el-scrollbar class="sidebar__scroll">
      <el-menu
        :default-active="activeMenu"
        :collapse="collapsed"
        :collapse-transition="false"
        :unique-opened="true"
        background-color="#001529"
        text-color="rgba(255,255,255,0.75)"
        active-text-color="#ffffff"
        router
      >
        <SidebarItem v-for="item in menuRoutes" :key="item.path" :item="item" :base-path="'/' + item.path" />
      </el-menu>
    </el-scrollbar>
    <div class="sidebar__footer" @click="appStore.toggleSidebar()">
      <el-icon :size="16">
        <Expand v-if="collapsed" />
        <Fold v-else />
      </el-icon>
      <span v-show="!collapsed" class="ml-8">收起菜单</span>
    </div>
  </aside>
</template>

<script setup lang="ts">
import { Expand, Fold } from '@element-plus/icons-vue'
import { useAppStore } from '@/stores/app'
import SidebarItem from './SidebarItem.vue'

const appStore = useAppStore()
const route = useRoute()
const router = useRouter()

const collapsed = computed(() => appStore.sidebarCollapsed)

/** 菜单数据：取具名路由 Layout 的子路由（过滤 hidden），addRoute 后同样生效 */
const menuRoutes = computed(() => {
  const layout = router.getRoutes().find((r) => r.name === 'Layout')
  return (layout?.children ?? []).filter((r) => !r.meta?.hidden)
})

const activeMenu = computed(() => route.path)
</script>

<style scoped lang="scss">
.sidebar {
  display: flex;
  flex-direction: column;
  flex-shrink: 0;
  width: $sidebar-width;
  background: $sidebar-bg;
  transition: width 0.2s ease;

  &.is-collapsed {
    width: $sidebar-collapsed-width;
  }

  &__scroll {
    flex: 1;
    min-height: 0;
  }

  :deep(.el-menu) {
    border-right: none;
  }

  :deep(.el-menu-item.is-active) {
    background-color: $sidebar-active-bg !important;
  }

  :deep(.el-sub-menu .el-menu) {
    background-color: #000c17 !important;
  }

  &__footer {
    display: flex;
    align-items: center;
    justify-content: center;
    height: 44px;
    color: $sidebar-text;
    cursor: pointer;
    border-top: 1px solid rgba(255, 255, 255, 0.08);

    &:hover {
      color: #fff;
    }
  }
}
</style>
