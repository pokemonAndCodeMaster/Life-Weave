import type { WorkOutputRef } from '../../api/workView'

export function kindLabel(output: WorkOutputRef): string {
  if (output.kind === 'research') return '研究成果'
  if (output.kind === 'development') return output.id.startsWith('delivery:') ? '代码交付' : '开发记录'
  if (output.kind === 'artifact') return '人工成果'
  return '记录'
}
export function stateLabel(state: string): string {
  return ({ succeeded: '已完成', failed: '失败', running: '进行中', waiting: '等待中', planned: '待开始', cancelled: '已取消', manual: '人工登记', partial: '部分结果', awaiting_acceptance: '待验收', accepted: '已接受', rejected: '需要修改', delivery_failed: '交付失败', integrated: '已集成' } as Record<string, string>)[state] || state
}
