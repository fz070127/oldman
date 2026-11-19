<template>
  <div class="pro-table">
    <!-- 首次加载或无数据刷新时的表格骨架屏（避免只放转圈） -->
    <div v-if="loading && tableData.length === 0" class="pro-table__skeleton">
      <el-skeleton animated>
        <template #template>
          <div class="skeleton-table">
            <div class="skeleton-table__head">
              <el-skeleton-item
                v-for="idx in Math.min(columns.length, 7)"
                :key="`h-${idx}`"
                variant="text"
                class="skeleton-cell"
              />
            </div>
            <div v-for="rowIdx in 6" :key="`r-${rowIdx}`" class="skeleton-table__row">
              <el-skeleton-item
                v-for="colIdx in Math.min(columns.length, 7)"
                :key="`c-${rowIdx}-${colIdx}`"
                variant="text"
                class="skeleton-cell"
              />
            </div>
          </div>
        </template>
      </el-skeleton>
    </div>

    <div v-show="!(loading && tableData.length === 0)" v-loading="loading && tableData.length > 0">
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
          <EmptyState
            v-if="loadError"
            mode="error"
            title="数据加载失败"
            :description="errorMessage || '网络连接异常或服务器暂不可用，请检查网络后点击重试'"
            action-text="加载失败，点击重试"
            @action="fetchData"
          />
          <EmptyState
            v-else
            mode="empty"
            title="暂无匹配记录"
            :description="emptyText"
            action-text="刷新重试"
            @action="reload(true)"
          />
        </template>
      </el-table>

      <div
        v-if="pagination && total > 0 && tableData.length > 0 && !loadError"
        class="pro-table__pagination"
      >
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
  </div>
</template>

<script setup lang="ts" generic="T extends Record<string, any> = Record<string, any>">
/**
 * 通用高级表格组件 ProTable
 * - 封装 el-table + el-pagination + el-skeleton 骨架屏 + EmptyState 空态 + 断网/异常错误重试
 * - 已有数据时翻页通过 v-loading 遮罩，绝不卸载重挂 el-table（避免页面闪烁）
 * - 分页严格从 1 开始，默认 pageSize=20，数据为空或加载失败时隐藏分页器
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
    emptyText: '当前筛选条件下暂无符合要求的数据，可调整筛选条件或点击刷新',
    autoWatchSearch: true,
  },
)

// eslint-disable-next-line @typescript-eslint/no-explicit-any
defineSlots<Record<string, (props: { row: T; index: number }) => any>>()

const loading = ref(false)
const loadError = ref(false)
const errorMessage = ref('')
const tableData = ref<T[]>([]) as Ref<T[]>
const total = ref(0)
const page = ref(1)
const pageSize = ref(props.defaultPageSize)

/** 拉取当前页数据（自动捕获网络/接口异常并切换至错误重试态） */
async function fetchData() {
  loading.value = true
  loadError.value = false
  errorMessage.value = ''
  try {
    const query: Record<string, unknown> = {
      ...props.searchParams,
      page: page.value,
      pageSize: page.value ? pageSize.value : 20,
    }
    Object.keys(query).forEach((k) => {
      if (query[k] === '' || query[k] === undefined || query[k] === null) {
        delete query[k]
      }
    })
    const res = await props.request(query)
    tableData.value = res?.list ?? []
    total.value = Number(res?.total ?? 0)
  } catch (err) {
    loadError.value = true
    tableData.value = []
    total.value = 0
    const msg = (err as { message?: string })?.message
    errorMessage.value = msg || '网络连接失败，请检查网络或服务状态后点击下方按钮重试'
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

  &__skeleton {
    padding: 12px 0;
  }

  &__pagination {
    display: flex;
    justify-content: flex-end;
    padding-top: 16px;
  }
}

.skeleton-table {
  display: flex;
  flex-direction: column;
  gap: 14px;

  &__head,
  &__row {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(80px, 1fr));
    gap: 16px;
    padding: 10px 12px;
  }

  &__head {
    background: #f7f9fc;
    border-radius: 6px;
  }

  &__row {
    border-bottom: 1px solid #f0f2f5;
  }
}

.skeleton-cell {
  height: 18px;
}
</style>
