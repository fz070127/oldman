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
        <el-breadcrumb-item
          v-for="item in breadcrumbs"
          :key="item.path"
          :to="item.to ? { path: item.to } : undefined"
        >
          {{ item.title }}
        </el-breadcrumb-item>
      </el-breadcrumb>
    </div>

    <div class="navbar__right">
      <!-- 搜索（占位：点击展开输入框） -->
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

      <!-- 实时通道状态 -->
      <el-tooltip :content="wsStatusText" placement="bottom">
        <span class="navbar__ws" :class="`is-${ws.status.value}`">
          <i class="navbar__ws-dot" />
          <span class="navbar__ws-text">{{ wsStatusLabel }}</span>
        </span>
      </el-tooltip>

      <!-- 告警提示音开关（持久化 localStorage） -->
      <el-tooltip :content="alarmStore.muted ? '提示音已关闭，点击开启' : '提示音已开启，点击静音'" placement="bottom">
        <el-icon
          class="navbar__action"
          :class="{ 'is-muted': alarmStore.muted }"
          :size="18"
          @click="alarmStore.toggleMuted()"
        >
          <MuteNotification v-if="alarmStore.muted" />
          <Headset v-else />
        </el-icon>
      </el-tooltip>

      <!-- 通知铃铛 + 待处理告警数（WS 实时 +1，重连后用 pending-count 校准） -->
      <el-tooltip content="待处理告警" placement="bottom">
        <el-badge
          :value="alarmStore.pendingCount"
          :max="99"
          :hidden="alarmStore.pendingCount <= 0"
          class="navbar__badge"
          :class="{ 'is-ringing': ringing }"
        >
          <el-icon class="navbar__action" :size="18" @click="goAlarm"><Bell /></el-icon>
        </el-badge>
      </el-tooltip>

      <!-- 用户下拉：昵称 + 角色中文名 -->
      <el-dropdown trigger="click" @command="onCommand">
        <div class="navbar__user">
          <el-avatar :size="28" :src="userStore.userInfo?.avatar || undefined">
            {{ userStore.displayName.slice(0, 1) }}
          </el-avatar>
          <span class="navbar__username">{{ userStore.displayName }}</span>
          <el-tag v-if="userStore.roleName" size="small" effect="plain" class="navbar__role-tag">
            {{ userStore.roleName }}
          </el-tag>
          <el-icon><ArrowDown /></el-icon>
        </div>
        <template #dropdown>
          <el-dropdown-menu>
            <el-dropdown-item command="profile">个人中心</el-dropdown-item>
            <el-dropdown-item command="password">修改密码</el-dropdown-item>
            <el-dropdown-item divided command="logout">退出登录</el-dropdown-item>
          </el-dropdown-menu>
        </template>
      </el-dropdown>
    </div>

    <!-- 修改密码弹窗 -->
    <el-dialog
      v-model="pwdDialogVisible"
      title="修改密码"
      width="420px"
      destroy-on-close
      @closed="resetPwdForm"
    >
      <el-form ref="pwdFormRef" :model="pwdForm" :rules="pwdRules" label-width="88px">
        <el-form-item label="原密码" prop="oldPassword">
          <el-input v-model="pwdForm.oldPassword" type="password" placeholder="请输入原密码" show-password />
        </el-form-item>
        <el-form-item label="新密码" prop="newPassword">
          <el-input
            v-model="pwdForm.newPassword"
            type="password"
            placeholder="请输入至少 6 位新密码"
            show-password
          />
        </el-form-item>
        <el-form-item label="确认新密码" prop="confirmPassword">
          <el-input
            v-model="pwdForm.confirmPassword"
            type="password"
            placeholder="请再次输入新密码"
            show-password
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="pwdDialogVisible = false">取 消</el-button>
        <el-button type="primary" :loading="pwdSubmitting" @click="submitPassword">确 定</el-button>
      </template>
    </el-dialog>
  </header>
</template>

<script setup lang="ts">
import type { FormInstance, FormRules } from 'element-plus'
import {
  ArrowDown,
  Bell,
  Expand,
  Fold,
  Headset,
  MuteNotification,
  Search,
} from '@element-plus/icons-vue'
import { updatePassword } from '@/api/auth'
import { useWebSocket } from '@/hooks/useWebSocket'
import { useAlarmStore } from '@/stores/alarm'
import { useAppStore } from '@/stores/app'
import { useUserStore } from '@/stores/user'

const appStore = useAppStore()
const userStore = useUserStore()
const alarmStore = useAlarmStore()
const ws = useWebSocket()
const route = useRoute()
const router = useRouter()

// ---------------- 实时通道状态 / 告警铃铛 ----------------
const wsStatusLabel = computed(() => {
  switch (ws.status.value) {
    case 'open':
      return '实时'
    case 'connecting':
      return '连接中'
    case 'reconnecting':
      return '重连中'
    default:
      return '离线'
  }
})
const wsStatusText = computed(() => {
  const mode = import.meta.env.VITE_USE_MOCK === 'true' ? 'Mock 通道（SSE 桥）' : 'WebSocket'
  if (ws.status.value === 'reconnecting' && ws.nextRetryMs.value) {
    return `${mode} 已断开，${Math.round(ws.nextRetryMs.value / 1000)}s 后重连`
  }
  return `${mode}：${wsStatusLabel.value}`
})

/** 新告警到达时铃铛摇 1.2s */
const ringing = ref(false)
let ringTimer: ReturnType<typeof setTimeout> | null = null
watch(
  () => alarmStore.pendingCount,
  (n, old) => {
    if (n <= (old ?? 0)) return
    ringing.value = true
    if (ringTimer) clearTimeout(ringTimer)
    ringTimer = setTimeout(() => (ringing.value = false), 1200)
  },
)

function goAlarm() {
  if (router.hasRoute('Alarm')) router.push('/alarm')
}

/** 面包屑：取匹配链上有标题的路由，详情页自动补齐上级列表面包屑 */
const PARENT_BREADCRUMB_MAP: Record<string, { title: string; path: string }> = {
  elder: { title: '老人档案', path: '/elder' },
  device: { title: '设备管理', path: '/device' },
  event: { title: '事件中心', path: '/event' },
}

const breadcrumbs = computed(() => {
  const matched = route.matched
    .filter((r) => r.meta?.title)
    .map((r) => ({
      path: r.path,
      title: String(r.meta.title),
      to: undefined as string | undefined,
    }))
  const menuKey = String(route.meta?.menuKey || '')
  if (route.meta?.hidden && PARENT_BREADCRUMB_MAP[menuKey]) {
    const parent = PARENT_BREADCRUMB_MAP[menuKey]
    if (!matched.some((m) => m.title === parent.title)) {
      matched.unshift({
        path: parent.path,
        title: parent.title,
        to: parent.path,
      })
    }
  }
  return matched
})

const searchOpen = ref(false)
const keyword = ref('')
const searchInputRef = ref<{ focus: () => void }>()
async function openSearch() {
  searchOpen.value = true
  await nextTick()
  searchInputRef.value?.focus()
}

// ---------------- 修改密码弹窗 ----------------
const pwdDialogVisible = ref(false)
const pwdSubmitting = ref(false)
const pwdFormRef = ref<FormInstance>()
const pwdForm = reactive({
  oldPassword: '',
  newPassword: '',
  confirmPassword: '',
})

const pwdRules: FormRules = {
  oldPassword: [{ required: true, message: '请输入原密码', trigger: 'blur' }],
  newPassword: [
    { required: true, message: '请输入新密码', trigger: 'blur' },
    { min: 6, max: 32, message: '密码长度需在 6~32 位之间', trigger: 'blur' },
  ],
  confirmPassword: [
    { required: true, message: '请再次输入新密码', trigger: 'blur' },
    {
      validator: (_rule, value: string, callback) => {
        if (value !== pwdForm.newPassword) {
          callback(new Error('两次输入的新密码不一致'))
          return
        }
        callback()
      },
      trigger: 'blur',
    },
  ],
}

function resetPwdForm() {
  pwdForm.oldPassword = ''
  pwdForm.newPassword = ''
  pwdForm.confirmPassword = ''
  pwdFormRef.value?.clearValidate()
}

async function submitPassword() {
  if (pwdSubmitting.value) return
  const valid = await pwdFormRef.value?.validate().catch(() => false)
  if (!valid) return

  pwdSubmitting.value = true
  try {
    await updatePassword({
      oldPassword: pwdForm.oldPassword,
      newPassword: pwdForm.newPassword,
    })
    ElMessage.success('密码修改成功，请使用新密码重新登录')
    pwdDialogVisible.value = false
    await userStore.logout()
  } catch {
    // 业务错误已由 request 拦截器统一提示
  } finally {
    pwdSubmitting.value = false
  }
}

async function onCommand(cmd: string) {
  if (cmd === 'profile') {
    ElMessage.info('个人中心建设中')
    return
  }
  if (cmd === 'password') {
    pwdDialogVisible.value = true
    return
  }
  if (cmd === 'logout') {
    await ElMessageBox.confirm('确定退出登录吗？', '提示', { type: 'warning' })
    await userStore.logout()
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

    &.is-ringing :deep(.el-icon) {
      color: $color-danger;
      animation: bell-ring 0.6s ease-in-out 2;
      transform-origin: 50% 0;
    }
  }

  &__action.is-muted {
    color: $text-disabled;
  }

  &__ws {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 2px 10px;
    font-size: 12px;
    color: $text-regular;
    background: #f5f6f8;
    border-radius: 10px;
    cursor: default;

    &.is-open {
      color: #237804;
      background: #f6ffed;

      .navbar__ws-dot {
        background: $color-success;
        box-shadow: 0 0 0 0 rgba(82, 196, 26, 0.6);
        animation: ws-breath 2s infinite;
      }
    }

    &.is-reconnecting,
    &.is-connecting {
      color: #d46b08;
      background: #fff7e6;

      .navbar__ws-dot {
        background: $color-warning;
      }
    }
  }

  &__ws-dot {
    display: inline-block;
    width: 8px;
    height: 8px;
    background: #c0c4cc;
    border-radius: 50%;
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

  &__role-tag {
    font-size: 12px;
  }
}

@keyframes bell-ring {
  0%,
  100% {
    transform: rotate(0);
  }
  20% {
    transform: rotate(18deg);
  }
  40% {
    transform: rotate(-16deg);
  }
  60% {
    transform: rotate(10deg);
  }
  80% {
    transform: rotate(-6deg);
  }
}

@keyframes ws-breath {
  0% {
    box-shadow: 0 0 0 0 rgba(82, 196, 26, 0.55);
  }
  70% {
    box-shadow: 0 0 0 6px rgba(82, 196, 26, 0);
  }
  100% {
    box-shadow: 0 0 0 0 rgba(82, 196, 26, 0);
  }
}
</style>
