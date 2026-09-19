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
