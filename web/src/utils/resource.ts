/**
 * 资源 URL 处理工具
 */

/**
 * 获取资源URL（处理相对路径）
 * 参考 Vue2 项目的实现
 */
export function getResourceUrl(path?: string): string | undefined {
  if (!path) return undefined
  
  // 如果已经是完整URL，直接返回
  if (path.startsWith('http://') || path.startsWith('https://')) {
    return path
  }
  
  // 确保URL以/开头
  if (!path.startsWith('/')) {
    path = '/' + path
  }

  // 使用完整的后端地址（开发和生产环境都需要）
  const backendUrl = import.meta.env.VITE_BACKEND_URL || 'http://localhost:8091'

  if (backendUrl) {
    // 移除开头的斜杠，因为我们要将完整的URL传给组件
    if (path.startsWith('/')) {
      path = path.substring(1)
    }

    // 构建完整的URL
    return `${backendUrl}/${path}`
  }

  // 如果没有配置后端URL，返回相对路径
  return path
}
