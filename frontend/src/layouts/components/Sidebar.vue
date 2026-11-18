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
import { useUserStore } from '@/stores/user'
import { asyncRoutes, isDynamicRoutesLoaded } from '@/router'
import SidebarItem from './SidebarItem.vue'

const appStore = useAppStore()
const userStore = useUserStore()
const route = useRoute()

const collapsed = computed(() => appStore.sidebarCollapsed)

/**
 * 菜单数据：取已挂载的动态业务路由。
 *
 * 注意：Vue Router 4 的 `getRoutes()` 返回的是扁平 matcher 列表，
 * `router.addRoute('Layout', child)` 之后子路由并不会进入父级 matcher 的
 * `children` 字段（该字段永远是空数组）。因此不能靠 Layout.children 取菜单，
 * 必须从扁平列表里按「已注册的动态路由名」筛选。
 * 同时依赖 userStore.menus，确保切换账号/动态刷新时响应式更新。
 */
const menuRoutes = computed(() => {
  void userStore.menus.length
  void isDynamicRoutesLoaded()
  const menuSet = new Set(userStore.menus)
  return asyncRoutes.filter((r) => r.meta?.menuKey && menuSet.has(r.meta.menuKey) && !r.meta?.hidden)
})

const activeMenu = computed(() => {
  if (route.path.startsWith('/elder')) return '/elder'
  if (route.path.startsWith('/device')) return '/device'
  return route.path
})
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
