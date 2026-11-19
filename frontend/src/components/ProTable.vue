<template>
  <div v-loading="loading" class="pro-table">
    <el-table
      :data="tableData"
      :row-key="rowKey"
      :row-class-name="rowClassName"
      :border="border"
      :stripe="stripe"
      style="width: 100%"
    >
      <el-table-column
        v-for="col in columns"
        :key="col.prop || col.slot || col.label"
        :prop="col.prop"
        :label="col.label"
        :width="col.width"
        :min-width="col.minWidth"
        :align="col.align || 'left'"
        :fixed="col.fixed"
        :show-overflow-tooltip="col.showOverflowTooltip ?? true"
      >
        <template #default="scope">
          <slot v-if="col.slot" :name="col.slot" :row="scope.row" :index="scope.$index" />
          <span v-else-if="col.formatter">
            {{ col.formatter(scope.row, scope.$index) }}
          </span>
          <span v-else>
            {{ col.prop ? scope.row[col.prop] ?? '-' : '-' }}
          </span>
        </template>
      </el-table-column>

      <template #empty>
        <EmptyState :description="emptyText" />
      </template>
    </el-table>

    <div v-if="pagination && total > 0" class="pro-table__pagination">
      <el-pagination
        v-model:current-page="page"
        v-model:page-size="pageSize"
        :page-sizes="pageSizes"
        :total="total"
        layout="total, sizes, prev, pager, next, jumper"
        background
        @current-change="onPageChange"
        @size-change="onSizeChange"
      />
    </div>
  </div>
</template>

<script setup lang="ts" generic="T extends Record<string, any> = Record<string, any>">
/**
 * 通用高级表格组件 ProTable
 * - 封装 el-table + el-pagination + v-loading + EmptyState 空态
 * - 切换页码或修改筛选条件时只更新数据并通过 v-loading 遮罩，绝不卸载重挂 el-table（避免页面闪烁）
 * - 分页严格从 1 开始，默认 pageSize=20，可选 [10, 20, 50, 100]
 */
import EmptyState from './EmptyState.vue'

export interface ProTableColumn<Row = Record<string, unknown>> {
  prop?: string
  label: string
  width?: number | string
  minWidth?: number | string
  slot?: string
  align?: 'left' | 'center' | 'right'
  fixed?: boolean | 'left' | 'right'
  showOverflowTooltip?: boolean
  formatter?: (row: Row, index: number) => string | number
}

export interface ProTableResult<Row = Record<string, unknown>> {
  list: Row[]
  total: number
  page?: number
  pageSize?: number
}

export interface ProTableInstance<Row = Record<string, unknown>> {
  reload: (resetPage?: boolean) => Promise<void>
  fetchData: () => Promise<void>
  tableData: Row[]
  total: number
}

const props = withDefaults(
  defineProps<{
    columns: ProTableColumn<T>[]
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    request: (params: Record<string, any>) => Promise<ProTableResult<T>>
    searchParams?: Record<string, unknown>
    rowKey?: string
    rowClassName?: (data: { row: T; rowIndex: number }) => string
    pagination?: boolean
    defaultPageSize?: number
    pageSizes?: number[]
    border?: boolean
    stripe?: boolean
    emptyText?: string
    /** 是否在 searchParams 深度变化时自动重置到第 1 页并重新请求 */
    autoWatchSearch?: boolean
  }>(),
  {
    searchParams: () => ({}),
    rowKey: 'id',
    rowClassName: undefined,
    pagination: true,
    defaultPageSize: 20,
    pageSizes: () => [10, 20, 50, 100],
    border: false,
    stripe: false,
    emptyText: '暂无符合条件的数据',
    autoWatchSearch: true,
  },
)

// eslint-disable-next-line @typescript-eslint/no-explicit-any
defineSlots<Record<string, (props: { row: T; index: number }) => any>>()

const loading = ref(false)
const tableData = ref<T[]>([]) as Ref<T[]>
const total = ref(0)
const page = ref(1)
const pageSize = ref(props.defaultPageSize)

/** 拉取当前页数据 */
async function fetchData() {
  loading.value = true
  try {
    const query: Record<string, unknown> = {
      ...props.searchParams,
      page: page.value,
      pageSize: page.value ? pageSize.value : 20,
    }
    // 清理空字符串查询项，避免向后端传冗余空参
    Object.keys(query).forEach((k) => {
      if (query[k] === '' || query[k] === undefined || query[k] === null) {
        delete query[k]
      }
    })
    const res = await props.request(query)
    tableData.value = res?.list ?? []
    total.value = Number(res?.total ?? 0)
  } finally {
    loading.value = false
  }
}

/** 刷新：resetPage=true 时回到第 1 页 */
function reload(resetPage = false) {
  if (resetPage) page.value = 1
  return fetchData()
}

function onPageChange(newPage: number) {
  page.value = newPage
  fetchData()
}

function onSizeChange(newSize: number) {
  pageSize.value = newSize
  page.value = 1
  fetchData()
}

// 监听筛选参数变化自动查询（防抖避免连续修改触发多次）
let watchTimer: ReturnType<typeof setTimeout> | null = null
watch(
  () => props.searchParams,
  () => {
    if (!props.autoWatchSearch) return
    if (watchTimer) clearTimeout(watchTimer)
    watchTimer = setTimeout(() => {
      page.value = 1
      fetchData()
    }, 60)
  },
  { deep: true },
)

onMounted(() => {
  fetchData()
})

defineExpose({
  reload,
  fetchData,
  tableData,
  total,
})
</script>

<style scoped lang="scss">
.pro-table {
  width: 100%;

  &__pagination {
    display: flex;
    justify-content: flex-end;
    padding-top: 16px;
  }
}
</style>
