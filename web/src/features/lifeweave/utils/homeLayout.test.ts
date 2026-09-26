import { describe, expect, it } from 'vitest'
import { defaultHomeLayout, moveHomeCard, normalizeHomeLayout } from './homeLayout'

describe('home layout presets', () => {
  it('starts personal and team spaces with different, complete card orders', () => {
    const personal = defaultHomeLayout('personal')
    const team = defaultHomeLayout('team')
    expect(personal.map(card => card.key)).toEqual(['attention', 'active', 'capture', 'context', 'environment'])
    expect(team.map(card => card.key)).toEqual(['attention', 'context', 'active', 'capture', 'environment'])
    expect(team.find(card => card.key === 'context')?.column).toBe('main')
  })

  it('keeps valid user choices and repairs old or malformed saved cards', () => {
    const layout = normalizeHomeLayout({ cards: [
      { key: 'capture', column: 'main', visible: false },
      { key: 'capture', column: 'aside', visible: true },
      { key: 'unknown', column: 'main', visible: true },
    ] }, 'personal')
    expect(layout).toHaveLength(5)
    expect(layout[0]).toEqual({ key: 'capture', column: 'main', visible: false })
    expect(new Set(layout.map(card => card.key)).size).toBe(5)
    expect(moveHomeCard(layout, 'capture', 1)[1]?.key).toBe('capture')
    expect(layout[0]?.key).toBe('capture')
  })
})
