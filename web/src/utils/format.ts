export function formatCompact(value?: number): string {
  if (value === undefined || value === null) return '0'
  if (value === 0) return '0'
  const abs = Math.abs(value)
  if (abs >= 1000000) return `${(value / 1000000).toFixed(1)}M`
  if (abs >= 1000) return `${(value / 1000).toFixed(1)}K`
  return Number(value).toFixed(0)
}

export function formatDecimal(value?: number, digits = 1): string {
  if (value === undefined || value === null || Number.isNaN(value)) {
    return '--'
  }
  return Number(value).toFixed(digits)
}

export function formatMilliseconds(value?: number, digits = 0): string {
  if (value === undefined || value === null || Number.isNaN(value)) {
    return '--'
  }
  return `${Number(value).toFixed(digits)} ms`
}

export function formatPercentage(value?: number, digits = 1): string {
  if (value === undefined || value === null || Number.isNaN(value)) {
    return '--'
  }
  return `${(value * 100).toFixed(digits)}%`
}

export function formatBytes(value?: number): string {
  if (!value) return '0 B'
  const abs = Math.abs(value)
  if (abs < 1024) return `${abs.toFixed(0)} B`
  if (abs < 1024 * 1024) return `${(abs / 1024).toFixed(1)} KB`
  if (abs < 1024 * 1024 * 1024) return `${(abs / (1024 * 1024)).toFixed(1)} MB`
  return `${(abs / (1024 * 1024 * 1024)).toFixed(2)} GB`
}

