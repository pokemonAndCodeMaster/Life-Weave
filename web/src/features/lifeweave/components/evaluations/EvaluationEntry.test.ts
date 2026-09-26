import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import EvaluationEntry from './EvaluationEntry.vue'
import type { EvaluationTask } from '../../api/lifeweave'

const entry: EvaluationTask = {
  id: 'eval-one', workspace: 'personal', itemId: 'item-one', targetKind: 'capability',
  candidateId: 'cap-one', candidateVersion: 'v1', repeatOf: null, title: '攻略验证',
  instruction: '解释阵容', criteria: '有来源与限制', state: 'running', runId: 'run-one',
  outcome: null, assessment: null, evidenceId: null, createdAt: '2026-09-26T00:00:00Z',
  run: { id: 'run-one', state: 'succeeded', engine: 'codex', itemId: 'item-one' },
  evidence: [{ id: 'evidence-one', status: 'accepted', summary: '人工核验通过' }],
}

describe('EvaluationEntry', () => {
  it('sends the selected repository and knowledge as frozen run inputs', async () => {
    const wrapper = mount(EvaluationEntry, { props: { entry: { ...entry, state: 'planned', runId: null, run: undefined },
      workspace: 'personal', busy: false,
      methods: [{ id: 'method-one', title: '论文方法', description: '研究' }],
      knowledge: [{ ref: 'local:研究.md', title: '工作台 / 研究' }] },
      global: { stubs: { RouterLink: true } } })
    await wrapper.find('input[placeholder="不填则在空的隔离目录运行"]').setValue('/home/yyh/project/lifeweave')
    await wrapper.findAll('select')[2]!.setValue('method-one')
    await wrapper.findAll('select')[3]!.setValue(['local:研究.md'])
    await wrapper.find('form').trigger('submit')
    expect(wrapper.emitted('start')?.[0]).toEqual(['eval-one', {
      engine: 'codex', permission: 'read-only', model: undefined,
      directory: '/home/yyh/project/lifeweave', methodId: 'method-one', knowledgeRefs: ['local:研究.md'],
    }])
  })

  it('requires an accepted evidence choice and a reason before submitting a passing judgment', async () => {
    const wrapper = mount(EvaluationEntry, { props: { entry, workspace: 'personal', busy: false },
      global: { stubs: { RouterLink: true } } })
    await wrapper.find('select').setValue('passed')
    expect((wrapper.find('button[type="submit"]').element as HTMLButtonElement).disabled).toBe(true)
    await wrapper.findAll('select')[1]!.setValue('evidence-one')
    await wrapper.find('textarea').setValue('对照来源与限制均满足')
    await wrapper.find('form').trigger('submit')
    expect(wrapper.emitted('assess')?.[0]).toEqual(['eval-one', {
      outcome: 'passed', assessment: '对照来源与限制均满足', evidenceId: 'evidence-one',
    }])
  })

  it('turns an assessed run into an explicit, editable improvement suggestion', async () => {
    const wrapper = mount(EvaluationEntry, { props: {
      entry: { ...entry, state: 'assessed', outcome: 'failed', assessment: '缺少来源解释', improvementId: null },
      workspace: 'personal', busy: false,
    }, global: { stubs: { RouterLink: true } } })
    await wrapper.findAll('button').find(button => button.text() === '形成改进建议')!.trigger('click')
    expect(wrapper.text()).toContain('不会自动创建或发布 Agent')
    await wrapper.find('select').setValue('agent')
    await wrapper.findAll('textarea')[1]!.setValue('解释每条来源')
    await wrapper.find('form').trigger('submit')
    expect(wrapper.emitted('improve')?.[0]).toEqual(['eval-one', {
      targetKind: 'agent', problem: '缺少来源解释', desiredBehavior: '解释每条来源',
      validationPlan: '沿评测 eval-one 的同一任务和通过标准再评，比较运行过程与结果。',
    }])
  })

  it('lets a completed script call be judged without inventing a model run', async () => {
    const pluginEntry: EvaluationTask = {
      ...entry, targetKind: 'plugin', candidateId: null, candidateVersion: null,
      pluginId: 'lifeweave.checks.repository', pluginVersion: '1.0.0', pluginCallId: 'pcall-one',
      pluginCall: { id: 'pcall-one', plugin_id: 'lifeweave.checks.repository', plugin_version: '1.0.0',
        implementation_digest: 'abc123', operation: 'verify_inputs', state: 'succeeded', run_id: null },
      runId: null, run: undefined, evidence: [],
    }
    const wrapper = mount(EvaluationEntry, { props: { entry: pluginEntry, workspace: 'personal', busy: false },
      global: { stubs: { RouterLink: true } } })
    expect(wrapper.text()).toContain('固定调用')
    await wrapper.find('select').setValue('passed')
    await wrapper.find('textarea').setValue('检查结果与实际输入一致')
    await wrapper.find('form').trigger('submit')
    expect(wrapper.emitted('assess')?.[0]).toEqual(['eval-one', {
      outcome: 'passed', assessment: '检查结果与实际输入一致',
    }])
  })
})
