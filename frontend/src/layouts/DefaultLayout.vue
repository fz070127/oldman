<template>
  <div class="layout">
    <Navbar />
    <AlarmBanner />
    <div class="layout__body">
      <Sidebar />
      <div class="layout__main">
        <TabsBar />
        <!-- 内容区：独立滚动 -->
        <main class="layout__content">
          <router-view v-slot="{ Component, route }">
            <transition name="fade-slide" mode="out-in">
              <component :is="Component" :key="route.path" />
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
</script>

<style scoped lang="scss">
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
