<template>
  <!-- 有可见子路由 → 二级菜单 -->
  <el-sub-menu v-if="visibleChildren.length" :index="basePath">
    <template #title>
      <el-icon v-if="item.meta?.icon"><component :is="item.meta.icon" /></el-icon>
      <span>{{ item.meta?.title }}</span>
    </template>
    <SidebarItem
      v-for="child in visibleChildren"
      :key="child.path"
      :item="child"
      :base-path="resolvePath(child.path)"
    />
  </el-sub-menu>

  <!-- 叶子菜单 -->
  <el-menu-item v-else :index="basePath">
    <el-icon v-if="item.meta?.icon"><component :is="item.meta.icon" /></el-icon>
    <template #title>
      <span>{{ item.meta?.title }}</span>
    </template>
  </el-menu-item>
</template>

<script setup lang="ts">
import type { RouteRecordRaw } from 'vue-router'

defineOptions({ name: 'SidebarItem' })

const props = defineProps<{
  item: RouteRecordRaw
  /** 当前菜单的完整路径 */
  basePath: string
}>()

const visibleChildren = computed(() => (props.item.children ?? []).filter((c) => !c.meta?.hidden))

/** 拼接子路由完整路径（子路由 path 为相对路径） */
function resolvePath(childPath: string) {
  if (childPath.startsWith('/')) return childPath
  return `${props.basePath.replace(/\/$/, '')}/${childPath}`
}
</script>
