<template>
  <header class="navbar">
    <!-- Logo：宽度与侧边栏联动 -->
    <div class="navbar__logo" :class="{ 'is-collapsed': appStore.sidebarCollapsed }">
      <img src="/favicon.svg" alt="logo" />
      <span v-show="!appStore.sidebarCollapsed" class="navbar__logo-text">银铃守护</span>
    </div>

    <div class="navbar__left">
      <el-icon class="navbar__toggle" :size="18" @click="appStore.toggleSidebar()">
        <Expand v-if="appStore.sidebarCollapsed" />
        <Fold v-else />
      </el-icon>
      <el-breadcrumb separator="/">
        <el-breadcrumb-item v-for="item in breadcrumbs" :key="item.path">
          {{ item.meta.title }}
        </el-breadcrumb-item>
      </el-breadcrumb>
    </div>

    <div class="navbar__right">
      <!-- 搜索（F1 占位：点击展开输入框） -->
      <div class="navbar__search" :class="{ 'is-open': searchOpen }">
        <el-input
          v-if="searchOpen"
          ref="searchInputRef"
          v-model="keyword"
          size="small"
          placeholder="搜索老人 / 设备"
          @blur="searchOpen = false"
        />
        <el-icon v-else class="navbar__action" :size="18" @click="openSearch"><Search /></el-icon>
      </div>

      <!-- 通知铃铛 + 未读数 -->
      <el-badge :value="appStore.unreadCount" :max="99" :hidden="appStore.unreadCount <= 0" class="navbar__badge">
        <el-icon class="navbar__action" :size="18"><Bell /></el-icon>
      </el-badge>

      <!-- 用户下拉 -->
      <el-dropdown trigger="click" @command="onCommand">
        <div class="navbar__user">
          <el-avatar :size="28" :src="userStore.userInfo?.avatar || undefined">
            {{ userStore.displayName.slice(0, 1) }}
          </el-avatar>
          <span class="navbar__username">{{ userStore.displayName }}</span>
          <el-icon><ArrowDown /></el-icon>
        </div>
        <template #dropdown>
          <el-dropdown-menu>
            <el-dropdown-item command="profile">个人中心</el-dropdown-item>
            <el-dropdown-item divided command="logout">退出登录</el-dropdown-item>
          </el-dropdown-menu>
        </template>
      </el-dropdown>
    </div>
  </header>
</template>

<script setup lang="ts">
import { ArrowDown, Bell, Expand, Fold, Search } from '@element-plus/icons-vue'
import { useAppStore } from '@/stores/app'
import { useUserStore } from '@/stores/user'
import { useTabsStore } from '@/stores/tabs'

const appStore = useAppStore()
const userStore = useUserStore()
const tabsStore = useTabsStore()
const route = useRoute()
const router = useRouter()

/** 面包屑：取匹配链上有标题的路由 */
const breadcrumbs = computed(() => route.matched.filter((r) => r.meta?.title))

const searchOpen = ref(false)
const keyword = ref('')
const searchInputRef = ref<{ focus: () => void }>()
async function openSearch() {
  searchOpen.value = true
  await nextTick()
  searchInputRef.value?.focus()
}

async function onCommand(cmd: string) {
  if (cmd === 'profile') {
    ElMessage.info('个人中心建设中')
    return
  }
  if (cmd === 'logout') {
    await ElMessageBox.confirm('确定退出登录吗？', '提示', { type: 'warning' })
    await userStore.logout().catch(() => undefined)
    tabsStore.closeAll()
    router.replace('/login')
  }
}
</script>

<style scoped lang="scss">
.navbar {
  display: flex;
  flex-shrink: 0;
  align-items: center;
  height: $navbar-height;
  background: $bg-white;
  border-bottom: 1px solid $border-color;
  box-shadow: 0 1px 4px rgba(0, 21, 41, 0.04);
  z-index: 10;

  &__logo {
    display: flex;
    flex-shrink: 0;
    align-items: center;
    justify-content: center;
    width: $sidebar-width;
    height: 100%;
    background: $sidebar-bg;
    transition: width 0.2s ease;

    &.is-collapsed {
      width: $sidebar-collapsed-width;
    }

    img {
      width: 28px;
      height: 28px;
    }
  }

  &__logo-text {
    margin-left: 10px;
    font-size: 18px;
    font-weight: 600;
    color: #fff;
    white-space: nowrap;
    letter-spacing: 2px;
  }

  &__left {
    display: flex;
    flex: 1;
    align-items: center;
    min-width: 0;
    padding: 0 16px;
  }

  &__toggle {
    margin-right: 16px;
    color: $text-regular;
    cursor: pointer;

    &:hover {
      color: $color-primary;
    }
  }

  &__right {
    display: flex;
    align-items: center;
    gap: 20px;
    padding-right: 20px;
  }

  &__search.is-open {
    width: 200px;
  }

  &__action {
    color: $text-regular;
    cursor: pointer;

    &:hover {
      color: $color-primary;
    }
  }

  &__badge {
    display: flex;
    align-items: center;
  }

  &__user {
    display: flex;
    align-items: center;
    gap: 8px;
    cursor: pointer;
    outline: none;
  }

  &__username {
    max-width: 120px;
    overflow: hidden;
    color: $text-primary;
    white-space: nowrap;
    text-overflow: ellipsis;
  }
}
</style>
