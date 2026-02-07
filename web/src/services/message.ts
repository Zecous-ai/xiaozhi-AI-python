import { http } from './request'
import api from './api'
import type { Message, MessageQueryParams } from '@/types/message'
import type { ChatMemory } from '@/types/memory'

/**
 * 查询消息列表
 */
export function queryMessages(params: Partial<MessageQueryParams>) {
  return http.getPage<Message>(api.message.query, params)
}

export function queryChatMemory(params: {
  roleId: number
  deviceId: string
  start?: number
  limit?: number
  startTime?: string
  endTime?: string
}) {
  const { roleId, deviceId, start = 1, limit = 10, startTime, endTime } = params

  const queryParams: Partial<MessageQueryParams> = {
    start,
    limit,
    deviceId,
    roleId,
  }

  if (startTime) queryParams.startTime = startTime
  if (endTime) queryParams.endTime = endTime

  return http.getPage<ChatMemory>(api.message.query, queryParams)
}

/**
 * 删除消息
 */
export function deleteMessage(messageId: number | string) {
  return http.delete(`${api.message.delete}/${messageId}`)
}

/**
 * 更新消息
 */
export function updateMessage(data: Partial<Message>) {
  return http.putJSON(`${api.message.update}/${data.messageId}`, data)
}

