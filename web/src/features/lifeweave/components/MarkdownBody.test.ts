// @vitest-environment jsdom
import { render,screen,cleanup } from '@testing-library/vue'
import { afterEach,describe,expect,it } from 'vitest'
import MarkdownBody from './MarkdownBody.vue'
afterEach(cleanup)
describe('Markdown 的可核验来源与不可信正文',()=>{
 it('根目录文件的行号链接和子目录链接都能进入本轮源文件',()=>{
  render(MarkdownBody,{props:{content:'[入口](README.md:7) [实现](src/api/app.py:12-20)',sourceBase:'/api/lifeweave/personal/runs/run-1/source'}})
  expect(screen.getByRole('link',{name:'入口'}).getAttribute('href')).toBe('/api/lifeweave/personal/runs/run-1/source?path=README.md')
  expect(screen.getByRole('link',{name:'实现'}).getAttribute('href')).toBe('/api/lifeweave/personal/runs/run-1/source?path=src%2Fapi%2Fapp.py')
 })
 it('转写来源之后仍清除脚本、事件处理器与危险链接',()=>{
  const {container}=render(MarkdownBody,{props:{content:'<script>alert(1)</script><img src=x onerror="alert(1)"><a href="javascript:alert(1)">不可信链接</a><iframe src="https://elsewhere.test"></iframe>',sourceBase:'/safe/source'}})
  expect(container.querySelector('script,iframe,[onerror]')).toBeNull()
  expect(container.querySelector('a')?.getAttribute('href')).toBeNull()
 })
})

describe('研究成果的公式和受控图片',()=>{
 it('通过 KaTeX 排版公式，不在代码块中解释数学',()=>{
  const {container}=render(MarkdownBody,{props:{content:'行内 $E=mc^2$\n\n$$\\frac{a}{b}$$\n\n```text\n$x$\n```'}})
  expect(container.querySelectorAll('.katex')).toHaveLength(2)
  expect(container.querySelector('.katex-display')).not.toBeNull()
  expect(container.querySelector('pre')?.textContent).toContain('$x$')
 })
 it('只改写受控本地图片，外部图片不自动请求且危险内联样式被清除',()=>{
  const {container}=render(MarkdownBody,{props:{content:'![本地](figures/chart.png)\n![外部](https://external.test/track.png)\n<img src="../secret.png" style="position:fixed" onerror="alert(1)">',assetBase:'/api/lifeweave/personal/runs/run-1/assets'}})
  const image=container.querySelector('img')!
  expect(image.getAttribute('src')).toBe('/api/lifeweave/personal/runs/run-1/assets?path=figures%2Fchart.png')
  expect(container.querySelectorAll('img')).toHaveLength(1)
  expect(screen.getByRole('link',{name:'查看图片原出处'}).getAttribute('rel')).toBe('noopener noreferrer')
  expect(container.querySelector('[onerror],[style]')).toBeNull()
  image.dispatchEvent(new Event('error'))
  expect(container.textContent).toContain('加载失败')
 })
})

it('保留复杂下标与反斜杠公式分隔符，代码中的表达式保持原文',()=>{
 const {container}=render(MarkdownBody,{props:{content:'$x_i + y_j$\n\n\\[\\sum_{i=1}^n x_i\\]\n\n\\(a_b+c_d\\)\n\n`\\(code\\)`'}})
 expect(container.querySelectorAll('.katex')).toHaveLength(3)
 expect(container.querySelectorAll('.katex-display')).toHaveLength(1)
 expect(container.querySelector('code')?.textContent).toBe('\\(code\\)')
 expect(container.querySelector('.katex-error')).toBeNull()
})

it('keeps run source and image identity in knowledge while leaving code and ordinary links intact',()=>{
 const base='/api/lifeweave/personal/runs/run-first'
 const wrapper=render(MarkdownBody,{props:{content:'[出处](research/source.md) ![图](figure.png) [知识](other.md)\n\n```md\n[例](research/source.md)\n```',references:{links:{'research/source.md':base+'/source?path=research%2Fsource.md'},images:{'figure.png':base+'/assets?path=figure.png'},warnings:[]}}})
 expect(wrapper.container.querySelector('a')!.getAttribute('href')).toBe(base+'/source?path=research%2Fsource.md')
 expect(wrapper.container.querySelector('img')!.getAttribute('src')).toBe(base+'/assets?path=figure.png')
 expect(wrapper.container.querySelectorAll('a')[1]!.getAttribute('href')).toBe('other.md')
 expect(wrapper.container.querySelector('code')!.textContent).toContain('[例](research/source.md)')
})
