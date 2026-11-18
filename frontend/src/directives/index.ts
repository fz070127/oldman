import type { App } from 'vue'
import { permissionDirective } from './permission'

/**
 * 全局指令注册入口
 */
export function setupDirectives(app: App) {
  app.directive('permission', permissionDirective)
}
