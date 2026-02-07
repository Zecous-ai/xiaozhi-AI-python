<script setup lang="ts">
import { ref, reactive, computed, onMounted, onBeforeUnmount } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter, useRoute, onBeforeRouteLeave } from 'vue-router'
import { message as antMessage, type TablePaginationConfig } from 'ant-design-vue'
import { useTable } from '@/composables/useTable'
import { useExport } from '@/composables/useExport'
import { useLoadingStore } from '@/store/loading'
import { queryRoles } from '@/services/role'
import { queryDevices } from '@/services/device'
import { deleteMessage, queryChatMemory } from '@/services/message'
import AudioPlayer from '@/components/AudioPlayer.vue'
import TableActionButtons from '@/components/TableActionButtons.vue'
import type { Role } from '@/types/role'
import type { Device } from '@/types/device'
import type { ChatMemory, MemoryQueryParams } from '@/types/memory'
import dayjs, { Dayjs } from 'dayjs'
import { useEventBus } from '@vueuse/core'

const { t } = useI18n()
const router = useRouter()
const route = useRoute()
const loadingStore = useLoadingStore()

// 获取路由参数
const roleId = computed(() => parseInt(route.query.roleId as string) || 0)
const routeDeviceId = computed(() => route.query.deviceId as string || '')

// 表格和分页
const {
  loading,
  data,
  pagination,
  handleTableChange,
  loadData,
} = useTable<ChatMemory>()

// 使用导出 composable
const { exporting, exportToExcel } = useExport()

// 事件总线
const stopAllAudioBus = useEventBus<void>('stop-all-audio')

// 角色信息
const currentRole = ref<Role | null>(null)

// 设备列表
const devices = ref<Device[]>([])
const selectedDeviceId = ref<string>('')

// Tab标签
const activeTab = ref<'chat' | 'summary' | 'long'>('chat')

// 时间范围
const timeRange = ref<[Dayjs, Dayjs]>([dayjs().startOf('month'), dayjs().endOf('month')])

// 日期快捷选项
const rangePresets = computed(() => [
  { label: t('message.today'), value: [dayjs().startOf('day'), dayjs().endOf('day')] },
  { label: t('message.thisMonth'), value: [dayjs().startOf('month'), dayjs().endOf('month')] },
])

// 表格列配置
const columns = computed(() => {
  const baseColumns = [
    {
      title: t('message.conversationTime'),
      dataIndex: 'createTime',
      width: 180,
      align: 'center' as const,
    },
    {
      title: t('device.deviceName'),
      dataIndex: 'deviceName',
      width: 120,
      align: 'center' as const,
    },
  ]

  if (activeTab.value === 'summary') {
    return [
      ...baseColumns,
      {
        title: t('memory.summary'),
        dataIndex: 'summary',
        width: 300,
        align: 'center' as const,
      },
      {
        title: t('table.action'),
        dataIndex: 'operation',
        width: 110,
        fixed: 'right' as const,
        align: 'center' as const,
      },
    ]
  } else if (activeTab.value === 'long') {
    return [
      ...baseColumns,
      {
        title: t('memory.content'),
        dataIndex: 'text',
        width: 300,
        align: 'center' as const,
      },
      {
        title: t('table.action'),
        dataIndex: 'operation',
        width: 110,
        fixed: 'right' as const,
        align: 'center' as const,
      },
    ]
  } else {
    // chat tab
    return [
      ...baseColumns,
      {
        title: t('message.messageSender'),
        dataIndex: 'sender',
        width: 100,
        align: 'center' as const,
      },
      {
        title: t('message.messageContent'),
        dataIndex: 'message',
        width: 300,
        align: 'center' as const,
      },
      {
        title: t('message.voice'),
        dataIndex: 'audioPath',
        width: 400,
        align: 'center' as const,
      },
      {
        title: t('table.action'),
        dataIndex: 'operation',
        width: 110,
        fixed: 'right' as const,
        align: 'center' as const,
      },
    ]
  }
})

/**
 * 加载角色信息
 */
async function loadRoleInfo() {
  if (!roleId.value) return

  try {
    const res = await queryRoles({ start: 1, limit: 1, roleId: roleId.value })
    if (res.data?.list && res.data.list.length > 0) {
      const role = res.data.list[0]
      if (role) {
        currentRole.value = role
      }
    }
  } catch (error) {
    console.error('加载角色信息失败:', error)
  }
}

/**
 * 加载设备列表
 */
async function loadDevices() {
  if (!roleId.value) return

  try {
    const res = await queryDevices({ roleId: roleId.value, start: 1, limit: 100 })
    if (res.data?.list && res.data.list.length > 0) {
      devices.value = res.data.list
      // 如果路由中指定了 deviceId，则使用它;否则默认选中第一个设备
      if (routeDeviceId.value && devices.value.find(d => d.deviceId === routeDeviceId.value)) {
        selectedDeviceId.value = routeDeviceId.value
      } else {
        const firstDevice = devices.value[0]
        if (firstDevice) {
          selectedDeviceId.value = firstDevice.deviceId
        }
      }
      // 加载该设备的记忆数据
      await fetchMemoryData()
    }
  } catch (error) {
    console.error('加载设备列表失败:', error)
    antMessage.error(t('common.loadFailed'))
  }
}

/**
 * 获取记忆数据
 */
async function fetchMemoryData() {
  if (!roleId.value || !selectedDeviceId.value) return

  const params: MemoryQueryParams = {
    roleId: roleId.value,
    deviceId: selectedDeviceId.value,
    start: pagination.current || 1,
    limit: pagination.pageSize || 10,
  }

  try {
    if (activeTab.value === 'chat') {
      await loadData(() => queryChatMemory({
        ...params,
        startTime: timeRange.value[0].format('YYYY-MM-DD HH:mm:ss'),
        endTime: timeRange.value[1].format('YYYY-MM-DD HH:mm:ss'),
      }))
    }
  } catch (error) {
    console.error('加载记忆数据失败:', error)
    antMessage.error(t('common.loadFailed'))
  }
}

/**
 * 返回上一页
 */
function handleBack() {
  router.back()
}

/**
 * 处理标签页切换
 */
async function handleTabChange(key: string) {
  activeTab.value = key as 'chat' | 'summary' | 'long'
  await fetchMemoryData()
}

/**
 * 处理设备切换
 */
async function handleDeviceChange(deviceId: string) {
  selectedDeviceId.value = deviceId
  await fetchMemoryData()
}

/**
 * 处理分页变化
 */
const onTableChange = (pag: TablePaginationConfig) => {
  handleTableChange(pag)
  fetchMemoryData()
}

/**
 * 获取发送方显示文本
 */
function getSenderText(sender: string) {
  return sender === 'user' ? t('message.user') : t('message.assistant')
}

/**
 * 检查音频路径是否有效
 */
function hasValidAudio(audioPath: string | undefined | null): boolean {
  if (!audioPath || !audioPath.trim()) return false
  return true
}

/**
 * 处理音频加载错误
 */
function handleAudioLoadError(record: any) {
  record.audioLoadError = true
  console.debug('音频文件加载失败:', record.audioPath)
}

/**
 * 删除聊天消息
 */
async function handleDeleteMessage(record: any) {
  loading.value = true
  try {
    const res = await deleteMessage(record.messageId)
    if (res.code === 200) {
      antMessage.success(t('common.deleteSuccess'))
      await fetchMemoryData()
    }
  } catch (error) {
    console.error('删除消息失败:', error)
    antMessage.error(t('common.deleteFailed'))
  } finally {
    loading.value = false
  }
}

/**
 * 导出当前数据
 */
async function handleExport() {
  if (!data.value || data.value.length === 0) {
    antMessage.warning(t('export.noData'))
    return
  }

  loadingStore.showLoading(t('common.exporting'))
  try {
    let columns: any[] = []
    let filename = ''

    if (activeTab.value === 'chat') {
      filename = `chat_memory_${dayjs().format('YYYY-MM-DD_HH-mm-ss')}`
      columns = [
        { key: 'deviceName', title: t('device.deviceName') },
        {
          key: 'sender',
          title: t('message.messageSender'),
          format: (val: string) => val === 'user' ? t('message.user') : t('message.assistant')
        },
        { key: 'message', title: t('message.messageContent') },
        { key: 'createTime', title: t('message.conversationTime') }
      ]
    } else if (activeTab.value === 'summary') {
      filename = `summary_memory_${dayjs().format('YYYY-MM-DD_HH-mm-ss')}`
      columns = [
        { key: 'deviceName', title: t('device.deviceName') },
        { key: 'summary', title: t('memory.summary') },
        { key: 'createTime', title: t('message.conversationTime') }
      ]
    } else {
      filename = `longterm_memory_${dayjs().format('YYYY-MM-DD_HH-mm-ss')}`
      columns = [
        { key: 'deviceName', title: t('device.deviceName') },
        { key: 'text', title: t('memory.content') },
        { key: 'createTime', title: t('message.conversationTime') }
      ]
    }

    await exportToExcel(data.value, {
      filename,
      showLoading: false,
      columns
    })
    antMessage.success(t('common.exportSuccess'))
  } catch (error) {
    console.error('导出失败:', error)
    antMessage.error(t('common.exportFailed'))
  } finally {
    loadingStore.hideLoading()
  }
}

// 路由离开前停止所有音频
onBeforeRouteLeave(() => {
  stopAllAudioBus.emit()
})

// 组件销毁前停止所有音频
onBeforeUnmount(() => {
  stopAllAudioBus.emit()
})

// 初始化
onMounted(async () => {
  if (!roleId.value) {
    antMessage.error(t('common.parameterError'))
    return
  }

  await Promise.all([
    loadRoleInfo(),
    loadDevices(),
  ])
})
</script>

<template>
  <div class="memory-management-view">
    <!-- 筛选栏 -->
    <a-card :bordered="false" style="margin-bottom: 16px" class="search-card">
      <a-row :gutter="16">
        <a-col :xxl="8" :xl="12" :lg="24" :md="24" :xs="24">
          <a-form-item :label="t('device.deviceName')">
            <a-select
              v-model:value="selectedDeviceId"
              @change="handleDeviceChange"
            >
              <a-select-option
                v-for="device in devices"
                :key="device.deviceId"
                :value="device.deviceId"
              >
                {{ device.deviceName }}
              </a-select-option>
            </a-select>
          </a-form-item>
        </a-col>
        
        <a-col v-if="activeTab === 'chat'" :xxl="8" :xl="12" :lg="24" :md="24" :xs="24">
          <a-form-item :label="t('message.conversationDate')">
            <a-range-picker
              v-model:value="timeRange"
              :presets="rangePresets"
              :allow-clear="false"
              format="MM-DD"
              @change="fetchMemoryData"
            />
          </a-form-item>
        </a-col>
      </a-row>
    </a-card>

    <!-- 记忆数据表格 -->
    <a-card :bordered="false">
      <template #title>
        <a-space>
          <a-breadcrumb>
            <a-breadcrumb-item>
              <a @click="handleBack">{{ t('menu.role') }}</a>
            </a-breadcrumb-item>
            <a-breadcrumb-item v-if="currentRole">
              <a-space>
                <span>{{ currentRole.roleName }}</span>
                <a-tag color="blue" style="margin: 0">
                  {{ t('device.windowMemory') }}
                </a-tag>
              </a-space>
            </a-breadcrumb-item>
          </a-breadcrumb>
        </a-space>
      </template>
      <template #extra>
        <a-button type="primary" @click="handleExport" :loading="exporting">
          {{ t('common.export') }}
        </a-button>
      </template>
      <a-tabs :active-key="activeTab" @change="handleTabChange">
        <!-- Chat Tab -->
        <a-tab-pane key="chat" :tab="`${t('memory.chat')} (${t('device.windowMemory')})`">
          <a-table
            row-key="messageId"
            :columns="columns"
            :data-source="data"
            :loading="loading"
            :pagination="pagination"
            :scroll="{ x: 800 }"
            size="middle"
            @change="onTableChange"
          >
            <template #bodyCell="{ column, record }">
              <!-- 发送方列 -->
              <template v-if="column.dataIndex === 'sender'">
                {{ getSenderText(record.sender) }}
              </template>

              <!-- 消息内容列 -->
              <template v-else-if="column.dataIndex === 'message'">
                <a-tooltip :title="record.message" :mouse-enter-delay="0.5" placement="topLeft">
                  <span v-if="record.message" class="ellipsis-text">{{ record.message }}</span>
                  <span v-else>-</span>
                </a-tooltip>
              </template>

              <!-- 音频列 -->
              <template v-else-if="column.dataIndex === 'audioPath'">
                <div v-if="hasValidAudio(record.audioPath)" class="audio-player-container">
                  <AudioPlayer
                    :audio-url="record.audioPath"
                    @audio-load-error="() => handleAudioLoadError(record)"
                  />
                </div>
                <span v-else>{{ t('message.noAudio') }}</span>
              </template>

              <!-- 操作列 -->
              <template v-else-if="column.dataIndex === 'operation'">
                <TableActionButtons
                  :record="record"
                  show-delete
                  :delete-title="t('message.confirmDeleteMessage')"
                  @delete="() => handleDeleteMessage(record)"
                />
              </template>
            </template>
          </a-table>
        </a-tab-pane>
      </a-tabs>
    </a-card>

    <!-- 回到顶部 -->
    <a-back-top />
  </div>
</template>

<style scoped lang="scss">
.memory-management-view {
  padding: 24px;
}

.search-card :deep(.ant-form-item) {
  margin-bottom: 0;
}

.audio-player-container {
  position: relative;
  width: 100%;
  overflow: hidden;
  z-index: 1;
}

// 表格文字省略样式
.ellipsis-text {
  display: inline-block;
  width: 100%;
  overflow: hidden;
  white-space: nowrap;
  text-overflow: ellipsis;
}

// 表格单元格样式
:deep(.ant-table) {
  .ant-table-tbody > tr > td {
    max-width: 0;
  }
}
</style>
