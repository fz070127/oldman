<template>
  <div class="system-roles-page">
    <PageContainer title="角色与权限矩阵（只读）">
      <ProTable
        ref="tableRef"
        :columns="columns"
        :request="fetchRoles"
        :pagination="false"
      >
        <template #code="{ row }">
          <span class="mono-code">{{ row.code }}</span>
        </template>

        <template #permissions="{ row }">
          <div class="perm-tags">
            <el-tag
              v-for="perm in row.permissions"
              :key="perm"
              size="small"
              :type="perm === '*' ? 'danger' : 'primary'"
              effect="plain"
            >
              {{ perm === '*' ? '*（全部超级权限）' : perm }}
            </el-tag>
          </div>
        </template>
      </ProTable>
    </PageContainer>
  </div>
</template>

<script setup lang="ts">
import { getSystemRoles } from '@/api/system'
import PageContainer from '@/components/PageContainer.vue'
import ProTable, { type ProTableColumn } from '@/components/ProTable.vue'
import type { RoleItem } from '@/types/system'

const columns: ProTableColumn<RoleItem>[] = [
  { prop: 'id', label: '角色 ID', width: 100 },
  { prop: 'code', label: '角色编码', width: 170, slot: 'code' },
  { prop: 'name', label: '角色名称', width: 150 },
  {
    prop: 'permissions',
    label: '绑定权限项（RBAC）',
    minWidth: 320,
    slot: 'permissions',
    showOverflowTooltip: false,
  },
]

async function fetchRoles() {
  const res = await getSystemRoles()
  const list = res?.list ?? []
  return {
    list,
    total: list.length,
  }
}
</script>

<style scoped lang="scss">
.mono-code {
  font-family: monospace;
  font-weight: 600;
  color: $color-primary;
}

.perm-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
</style>
