import type { Directive, DirectiveBinding } from 'vue'
import { useUserStore } from '@/stores/user'

export type PermissionValue = string | string[]

function checkAndApply(el: HTMLElement, binding: DirectiveBinding<PermissionValue>) {
  const { value } = binding
  if (!value) return

  const userStore = useUserStore()
  const codes = Array.isArray(value) ? value : [value]
  if (codes.length === 0) return

  const allowed = codes.some((code) => userStore.hasPermission(code))
  if (!allowed && el.parentNode) {
    el.parentNode.removeChild(el)
  }
}

/**
 * 按钮级权限指令
 * @example v-permission="'alarm:ack'"
 * @example v-permission="['elder:write', 'device:write']"
 */
export const permissionDirective: Directive<HTMLElement, PermissionValue> = {
  mounted(el, binding) {
    checkAndApply(el, binding)
  },
  updated(el, binding) {
    checkAndApply(el, binding)
  },
}
