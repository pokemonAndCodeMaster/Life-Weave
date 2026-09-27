import DOMPurify from 'dompurify'

let renderer: Promise<typeof import('mermaid')['default']> | undefined
export const MAX_DIAGRAM_TEXT = 50_000

export async function renderMermaid(id: string, source: string): Promise<string> {
  if (source.length > MAX_DIAGRAM_TEXT) throw new Error('图定义超过 50,000 字符，请拆成较小的图。')
  // The host owns configuration and resource policy. Diagram text must not
  // enable callbacks, remote images, injected CSS, or change those settings.
  if (/%%\{|^\s*---\s*[\r\n]|\bimg\s*:|(?:https?:|javascript:|data:|file:|blob:)|@import|url\s*\(/im.test(source)) {
    throw new Error('图中包含自定义配置或外部资源。请移除这些内容后查看；源码仍保留。')
  }
  renderer ??= import('mermaid').then(({ default: mermaid }) => {
    mermaid.initialize({
      startOnLoad: false, securityLevel: 'strict', htmlLabels: false,
      fontFamily: 'Arial, sans-serif', suppressErrorRendering: true,
      maxTextSize: MAX_DIAGRAM_TEXT, maxEdges: 500,
      secure: ['securityLevel', 'startOnLoad', 'htmlLabels', 'maxTextSize', 'maxEdges', 'suppressErrorRendering', 'fontFamily', 'themeCSS'],
    })
    return mermaid
  })
  const mermaid = await renderer
  const { svg } = await mermaid.render(id, source)
  return DOMPurify.sanitize(svg, {
    USE_PROFILES: { svg: true, svgFilters: true },
    FORBID_TAGS: ['script', 'foreignObject', 'image', 'a', 'animate', 'set'],
    FORBID_ATTR: ['onload', 'onclick', 'onerror'],
  })
}
