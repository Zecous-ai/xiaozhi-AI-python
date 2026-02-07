/**
 * 聊天消息（短期/窗口记忆）
 */
export interface ChatMemory {
    messageId: string
    deviceId: string
    roleId: number
    message: string
    sender: 'user' | 'assistant'
    createTime: string
    audioPath?: string
    messageType?: string
}

/**
 * 记忆查询参数
 */
export interface MemoryQueryParams {
    roleId: number
    deviceId: string
    start?: number
    limit?: number
}