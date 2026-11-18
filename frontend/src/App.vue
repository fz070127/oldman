<template>
  <el-config-provider :locale="locale" :size="'default'">
    <router-view />
  </el-config-provider>
</template>

<script setup lang="ts">
import { locale } from '@/i18n'
</script>
