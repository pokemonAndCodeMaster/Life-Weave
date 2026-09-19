import { resolveKnowledgePath } from './knowledgeLinks'
export function readingHtml(element:HTMLElement,workspace:string,path:string,sourceId:string) {
 const copy=element.cloneNode(true) as HTMLElement
 for(const anchor of copy.querySelectorAll<HTMLAnchorElement>('a[href]')) {
  const href=anchor.getAttribute('href')||''
  if(href.startsWith('#'))continue
  if(!href.startsWith('/')&&!/^[a-z][a-z0-9+.-]*:/i.test(href)&&href.split('#')[0]?.endsWith('.md')) {
   const target=resolveKnowledgePath(path,href)
   if(target)anchor.href=new URL(`/lifeweave/${workspace}/knowledge?source=${encodeURIComponent(sourceId)}&path=${encodeURIComponent(target)}`,location.origin).href
  } else anchor.href=new URL(href,location.href).href
 }
 for(const image of copy.querySelectorAll<HTMLImageElement>('img[src]'))image.src=new URL(image.getAttribute('src')!,location.href).href
 const styles=Array.from(document.querySelectorAll<HTMLLinkElement>('link[rel="stylesheet"]')).map(link=>{const clone=link.cloneNode() as HTMLLinkElement;clone.href=link.href;return clone.outerHTML}).join('\n')
 return `<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>LifeWeave 知识阅读版</title>${styles}<style>body{max-width:980px;margin:32px auto;padding:0 24px;line-height:1.8}img{max-width:100%}pre{overflow:auto}</style><body><p>来源链接和图片仍通过原工作台读取，需要该工作台可访问。</p>${copy.innerHTML}</body></html>`
}
