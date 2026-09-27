import type { OutputCatalogFile, OutputFileCategory, OutputFileStatus } from '../../api/outputFiles'

export interface FileTotals {
  count: number
  additions: number
  deletions: number
  binary: number
}

export interface FileTreeNode {
  name: string
  path: string
  file?: OutputCatalogFile
  children: FileTreeNode[]
  totals: FileTotals
}

export const categories: Array<{ id: OutputFileCategory; label: string }> = [
  { id: 'document', label: '文档' },
  { id: 'code', label: '代码变更' },
  { id: 'verification', label: '验证材料' },
  { id: 'attachment', label: '附件' },
  { id: 'record', label: '决策与操作记录' },
]

export const statusLabels: Record<OutputFileStatus, string> = {
  added: '新增', modified: '修改', deleted: '删除', renamed: '重命名', unchanged: '未变更',
}

export function fileTotals(files: OutputCatalogFile[]): FileTotals {
  return files.reduce((totals, file) => {
    totals.count += 1
    totals.additions += file.additions ?? 0
    totals.deletions += file.deletions ?? 0
    totals.binary += Number(file.binary)
    return totals
  }, { count: 0, additions: 0, deletions: 0, binary: 0 })
}

export function uniqueCatalogFiles(files: OutputCatalogFile[]): OutputCatalogFile[] {
  // The catalog is for one fixed version. A path has one canonical category.
  return [...new Map(files.map(file => [file.path, file])).values()]
}

export function buildFileTree(files: OutputCatalogFile[]): FileTreeNode {
  const root: FileTreeNode = { name: '', path: '', children: [], totals: fileTotals(files) }
  const branches = new Map<string, FileTreeNode>([['', root]])
  for (const file of files) {
    const parts = file.path.split('/').filter(Boolean)
    let parent = root
    for (let index = 0; index < parts.length; index += 1) {
      const name = parts[index]!
      const path = parts.slice(0, index + 1).join('/')
      let node = branches.get(path)
      if (!node) {
        node = { name, path, children: [], totals: { count: 0, additions: 0, deletions: 0, binary: 0 } }
        branches.set(path, node)
        parent.children.push(node)
      }
      if (index === parts.length - 1) node.file = file
      parent = node
    }
  }
  function finish(node: FileTreeNode): FileTotals {
    if (node.file) node.totals = fileTotals([node.file])
    else if (node !== root) {
      node.totals = node.children.reduce((totals, child) => {
        const childTotals = finish(child)
        totals.count += childTotals.count
        totals.additions += childTotals.additions
        totals.deletions += childTotals.deletions
        totals.binary += childTotals.binary
        return totals
      }, { count: 0, additions: 0, deletions: 0, binary: 0 })
    } else node.children.forEach(finish)
    node.children.sort((left, right) => Number(!!left.file) - Number(!!right.file) || left.name.localeCompare(right.name, 'zh-CN'))
    return node.totals
  }
  finish(root)
  return root
}
