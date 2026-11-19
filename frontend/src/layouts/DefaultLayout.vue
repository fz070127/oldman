<template>
  <!-- 社区大屏等全屏沉浸式路由：脱离常规侧边栏与顶栏，100vw×100vh 独立渲染 -->
  <div v-if="route.meta?.fullscreen" class="fullscreen-shell">
    <router-view />
  </div>

  <div v-else class="layout">
    <Navbar />
    <AlarmBanner />
    <div class="layout__body">
      <Sidebar />
      <div class="layout__main">
        <TabsBar />
        <!-- 内容区：独立滚动 -->
        <main class="layout__content">
          <router-view v-slot="{ Component, route: currentRoute }">
            <transition name="fade-slide" mode="out-in">
              <component :is="Component" :key="currentRoute.path" />
            </transition>
          </router-view>
        </main>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import AlarmBanner from '@/components/AlarmBanner.vue'
import Navbar from './components/Navbar.vue'
import Sidebar from './components/Sidebar.vue'
import TabsBar from './components/TabsBar.vue'

const route = useRoute()
</script>

<style scoped lang="scss">
.fullscreen-shell {
  width: 100vw;
  height: 100vh;
  overflow: hidden;
  background: #0a1128;
}

.layout {
  display: flex;
  flex-direction: column;
  height: 100vh;
  overflow: hidden;

  &__body {
    display: flex;
    flex: 1;
    min-height: 0;
  }

  &__main {
    display: flex;
    flex: 1;
    flex-direction: column;
    min-width: 0;
  }

  &__content {
    flex: 1;
    min-height: 0;
    padding: 16px;
    overflow: auto;
    background: $bg-page;
  }
}
</style>
