import { describe, expect, it } from 'vitest'
import { createMemoryHistory, createRouter } from 'vue-router'
import application from './index'

describe('LifeWeave entry compatibility', () => {
  it('opens the current home and preserves saved detail links with query and fragment', async () => {
    const router = createRouter({ history: createMemoryHistory(), routes: application.options.routes })
    await router.push('/')
    expect(router.currentRoute.value.path).toBe('/lifeweave/personal/conversation')
    await router.push('/gongzuo/team/items/saved-item/outputs?view=all#result')
    expect(router.currentRoute.value.fullPath).toBe('/lifeweave/team/items/saved-item/outputs?view=all#result')
    expect(router.currentRoute.value.params.itemId).toBe('saved-item')
    await router.push('/lifeweave')
    expect(router.currentRoute.value.path).toBe('/lifeweave/personal/home')
  })
})
