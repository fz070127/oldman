/**
 * 数字平滑滚动动画 Hook（大屏 KPI / 图表中心统计数字专用）
 *
 * - 当 target 发生变化时，在 durationMs 内通过 requestAnimationFrame + easeOutCubic
 *   从当前展示值平滑插值过渡到新目标值
 * - 支持首次从 0 滚动到初始值（确保首屏也有明显的数字跳动过渡）
 * - 支持整数或指定小数位数（decimals）
 */
import { computed, onBeforeUnmount, ref, unref, watch, type ComputedRef, type Ref } from 'vue'

export interface UseCountUpOptions {
  /** 动画持续时间（毫秒），默认 900ms */
  duration?: number
  /** 保留小数位数，默认 0（整数） */
  decimals?: number
  /** 初始起始值，默认 0 */
  initialValue?: number
}

function easeOutCubic(t: number): number {
  return 1 - (1 - t) ** 3
}

export function useCountUp(
  target: Ref<number> | ComputedRef<number> | (() => number),
  options: UseCountUpOptions = {},
) {
  const duration = options.duration ?? 900
  const decimals = options.decimals ?? 0
  const current = ref<number>(options.initialValue ?? 0)

  let rafId: number | null = null

  function cancelAnim() {
    if (rafId !== null) {
      cancelAnimationFrame(rafId)
      rafId = null
    }
  }

  function animateTo(nextVal: number) {
    const safeTarget = Number.isFinite(nextVal) ? nextVal : 0
    cancelAnim()

    const startVal = current.value
    const delta = safeTarget - startVal
    if (Math.abs(delta) < 1e-6 || duration <= 0) {
      current.value = safeTarget
      return
    }

    const startTime = performance.now()

    const step = (now: number) => {
      const elapsed = now - startTime
      const progress = Math.min(1, elapsed / duration)
      const eased = easeOutCubic(progress)
      current.value = startVal + delta * eased

      if (progress < 1) {
        rafId = requestAnimationFrame(step)
      } else {
        current.value = safeTarget
        rafId = null
      }
    }

    rafId = requestAnimationFrame(step)
  }

  const resolveTarget = () => (typeof target === 'function' ? target() : unref(target))

  watch(
    resolveTarget,
    (val) => {
      animateTo(val)
    },
    { immediate: true },
  )

  onBeforeUnmount(() => {
    cancelAnim()
  })

  /** 格式化后的字符串（直接绑定模板显示） */
  const formatted = computed(() => {
    const factor = 10 ** decimals
    const rounded = Math.round(current.value * factor) / factor
    return decimals > 0 ? rounded.toFixed(decimals) : String(Math.round(rounded))
  })

  return {
    value: current,
    formatted,
    animateTo,
  }
}
