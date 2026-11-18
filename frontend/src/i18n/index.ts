/**
 * 国际化入口
 * 当前仅中文：为 Element Plus 组件提供 zh-CN 语言包，并统一 dayjs 语言
 * （如后续需要多语言，再评估是否引入 vue-i18n，需先确认依赖）
 */
import zhCn from 'element-plus/es/locale/lang/zh-cn'
import dayjs from 'dayjs'
import 'dayjs/locale/zh-cn'

dayjs.locale('zh-cn')

export const locale = zhCn
