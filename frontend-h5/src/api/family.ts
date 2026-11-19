import {
  mockGetFamilyElders,
  mockGetNotificationSettings,
  mockSaveNotificationSettings,
} from '@/mock'
import type { FamilyElderItem, FamilyNotificationSettings } from '@/types'

function delay(ms = 100): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

/** 获取我监护的老人列表（契约 3.8 GET /api/v1/family/elders） */
export async function getFamilyElders(): Promise<FamilyElderItem[]> {
  await delay(100)
  const res = mockGetFamilyElders()
  return res.data
}

/** 获取家属通知设置 */
export async function getNotificationSettings(): Promise<FamilyNotificationSettings> {
  await delay(60)
  return mockGetNotificationSettings()
}

/** 更新家属通知设置 */
export async function updateNotificationSettings(
  settings: FamilyNotificationSettings
): Promise<FamilyNotificationSettings> {
  await delay(80)
  return mockSaveNotificationSettings(settings)
}
