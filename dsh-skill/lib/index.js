/**
 * 蓝珊 · 珊瑚识别 Skill 插件（DSH / Cordis）
 * ================================================================
 * 提供 1 个 Skill + 2 个工具，供蓝珊 Agent 自主调度：
 *
 *   Skill: coral-identification      珊瑚种类识别与白化程度评估
 *   Tool : identify_coral            对一张水下照片做双任务识别
 *   Tool : coral_service_status      查询推理服务与模型状态（只读）
 *
 * 工具能力来自本地/远端推理服务（coral_ml/scripts/serve.py），
 * 本插件只做"编排 + 调用 + 结果整形"，不含任何模型计算。
 *
 * 服务地址：环境变量 CORAL_API_BASE，默认 http://127.0.0.1:8000
 */
import { readFile } from 'node:fs/promises'
import { basename, extname } from 'node:path'
import { defineTool } from '@deepseek-ai/dsh-tools'

export const name = 'dsh-coral-skill'
export const inject = ['tools', 'skills']

const API_BASE = () => (process.env.CORAL_API_BASE || 'http://127.0.0.1:8000').replace(/\/+$/, '')

/** 把分割结果整理成中文摘要（供模型直接汇报给用户） */
function summarizeCoverage(r) {
  const c = r.cover || {}
  const q = r.captureQuality || {}
  const pct = (v) => `${(Number(v || 0) * 100).toFixed(1)}%`
  const lines = []
  // 拍摄条件不合格时置顶警示——避免用户误信失真的覆盖率
  if (q.usable === false) {
    lines.push('⚠️ 拍摄条件超出模型适用边界，以下覆盖率可能严重失真：')
    lines.push(`   ${q.message || '建议在 10 米以内或加补光灯重拍'}`)
    if (q.contrast != null) lines.push(`   实测对比度 ${q.contrast}（可用阈值 ≥0.030）`)
    lines.push('')
  } else if (q.level === 'warn') {
    lines.push(`💡 ${q.message || '拍摄条件一般，建议开补光灯'}`)
    lines.push('')
  }
  lines.push('【礁区覆盖评估】',
    `  活珊瑚   ${pct(c.alivePct)}`,
    `  白化珊瑚 ${pct(c.bleachedPct)}`,
    `  死亡珊瑚 ${pct(c.deadPct)}`,
    `  藻类覆盖 ${pct(c.algaePct)}`,
    `  沙砾底质 ${pct(c.substratePct)}`,
    `  珊瑚总覆盖 ${pct(c.coralTotalPct)}（占珊瑚的白化比例 ${pct(c.bleachingShareOfCoral)}）`)
  // 白化状态：来自分类模型（分割模型的 bleachedPct 经实测跨域无效，AUC 仅 0.46）
  const bl = r.bleaching
  if (bl) {
    const rel = bl.reliable === false ? '  ⚠️置信度不足，建议人工复核' : ''
    lines.push(`【白化状态·分类模型】${bl.labelCn || bl.label}  ${pct(bl.confidence)}${rel}`)
  }
  const tp = (r.topClasses || []).slice(0, 4)
  if (tp.length) {
    lines.push('【主要底栖类别】')
    tp.forEach((t) => lines.push(`  ${t.name}  ${pct(t.pct)}`))
  }
  const cr = r.coralRegion
  if (cr && cr.reliable === false) {
    lines.push(`【珊瑚属识别】置信度不足（${cr.note || '低于门槛'}），本次不给出属级结论`)
  } else if (cr && cr.top && cr.top.length) {
    lines.push('【珊瑚属识别】')
    cr.top.forEach((t) => lines.push(`  ${t.genus}  ${pct(t.confidence)}`))
  }
  lines.push(`（耗时 ${r.inferenceMs ?? '?'} ms）`)
  return lines.join('\n')
}

/** 纯文本渲染助手：canonical value 已经是结构化 JSON，这里只做展示投影。 */
function textRender(fn) {
  return (_args, value) => [{ type: 'text', text: fn(value) }]
}

const MIME = {
  '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.png': 'image/png',
  '.webp': 'image/webp', '.bmp': 'image/bmp',
}

async function callPredict(imagePath, signal) {
  const ext = extname(imagePath).toLowerCase()
  if (!MIME[ext]) throw new Error(`不支持的图片格式 "${ext}"（支持 jpg/jpeg/png/webp/bmp）`)

  let buf
  try {
    buf = await readFile(imagePath)
  } catch (e) {
    throw new Error(`读取图片失败：${imagePath}（${e.code || e.message}）`)
  }
  if (buf.length === 0) throw new Error(`图片为空：${imagePath}`)

  const form = new FormData()
  form.append('file', new Blob([buf], { type: MIME[ext] }), basename(imagePath))

  let res
  try {
    res = await fetch(`${API_BASE()}/predict`, { method: 'POST', body: form, signal })
  } catch (e) {
    throw new Error(
      `无法连接珊瑚识别服务 ${API_BASE()}：${e.message}。` +
      `请先启动：cd coral_ml/scripts && python serve.py`,
    )
  }
  if (!res.ok) {
    const t = await res.text().catch(() => '')
    throw new Error(`识别服务返回 ${res.status}：${t.slice(0, 300)}`)
  }
  return await res.json()
}

/** 推测结果的中文摘要（给模型和用户看的自然语言）。 */
function summarize(r) {
  const sp = r.species || {}
  const bl = r.bleaching || {}
  const pct = (v) => `${(Number(v || 0) * 100).toFixed(1)}%`
  const lines = [
    `【珊瑚种类】${sp.nameCn || sp.name}（${sp.name}）  置信度 ${pct(sp.confidence)}`,
    `【白化程度】${bl.labelCn || bl.label}  置信度 ${pct(bl.confidence)}`,
  ]
  if (bl.probabilities) {
    lines.push('　　概率分布：' + Object.entries(bl.probabilities)
      .map(([k, v]) => `${k} ${pct(v)}`).join(' / '))
  }
  if (sp.needReview || bl.needReview) {
    lines.push('⚠ 存在低置信度项，已标记为需人工复核（安全使用边界内）。')
  }
  lines.push(`（耗时 ${r.inferenceMs ?? '?'} ms；结果仅供保育决策参考）`)
  return lines.join('\n')
}

export function apply(ctx) {
  /* ---------------- Skill 注册 ---------------- */
  ctx.skills.register({
    name: 'coral-identification',
    description: '识别水下珊瑚影像的珊瑚种类，并评估珊瑚白化程度（健康 / 白化 / 死亡）。',
    whenToUse:
      '当用户上传或指向一张水下珊瑚照片，并询问"这是什么珊瑚""珊瑚白化了吗""健康状态如何"时使用。'
      + '该 Skill 依赖本地珊瑚识别推理服务（默认 http://127.0.0.1:8000）。',
    source: 'runtime',
    invocation: { modelInvocable: true, userInvocable: true },
    content: [
      '# 珊瑚识别（coral-identification）',
      '',
      '## 能做什么',
      '- 珊瑚种类识别：30 类种级闭集分类（鹿角珊瑚、滨珊瑚、蔷薇珊瑚、杯形珊瑚等）',
      '- 白化程度评估：健康 / 白化 / 死亡 三分类',
      '- 两者在同一次调用中返回，并附带置信度与"是否需人工复核"标记',
      '',
      '## 怎么用',
      '1. 先确认用户提供了**本地图片路径**（jpg/png/webp/bmp）。',
      '2. 调用 `identify_coral(image_path=...)`。',
      '3. 把返回的 `species` 与 `bleaching` 用自然语言汇报给用户；',
      '   **务必同时说明置信度**，并在 `needReview` 为 true 时提示转人工复核。',
      '',
      '## 汇报口径（重要，属于安全使用边界）',
      '- 数值来自视觉模型测量，不要自行改写或推测百分比。',
      '- 结果仅为保育决策参考，不能作为唯一依据；',
      '- 低置信度样本必须显式提示"建议人工复核"。',
      '',
      '## 服务未启动时',
      '提示用户执行：`cd coral_ml/scripts && python serve.py`，',
      '或用 `coral_service_status` 查看服务与模型状态。',
    ].join('\n'),
  })

  /* ---------------- 工具 1：识别 ---------------- */
  ctx.tools.register(defineTool({
    name: 'identify_coral',
    description:
      '对一张本地水下珊瑚照片同时做两件事：(1) 识别珊瑚种类（30 类种级）；'
      + '(2) 评估白化程度（健康/白化/死亡）。返回每项的置信度与是否需人工复核。'
      + '当用户上传珊瑚照片并询问种类或白化状况时调用。'
      + '需要本地图片绝对路径；服务地址由 CORAL_API_BASE 指定（默认 http://127.0.0.1:8000）。',
    parameters: {
      image_path: {
        type: 'string',
        required: true,
        description: '本地珊瑚照片的绝对路径，支持 .jpg/.jpeg/.png/.webp/.bmp。',
      },
    },
    output: {
      schema: {
        type: 'object',
        additionalProperties: false,
        properties: {
          speciesName: { type: 'string', required: true, description: '识别出的珊瑚种类（拉丁学名）。' },
          speciesNameCn: { type: 'string', required: true, description: '珊瑚种类中文名。' },
          speciesConfidence: { type: 'number', required: true, description: '种类识别置信度 0–1。' },
          bleachingLabel: { type: 'string', required: true, description: '白化程度：healthy | bleached | dead。' },
          bleachingLabelCn: { type: 'string', required: true, description: '白化程度中文：健康 | 白化 | 死亡。' },
          bleachingConfidence: { type: 'number', required: true, description: '白化评估置信度 0–1。' },
          needReview: { type: 'boolean', required: true, description: '是否建议人工复核（任一项置信度不足）。' },
          disclaimer: { type: 'string', required: true, description: '使用边界声明。' },
          summary: { type: 'string', required: true, description: '人类可读的中文结论摘要。' },
        },
      },
      render: textRender((v) => v.summary),
    },
    execute: async (args, exec) => {
      exec.signal.throwIfAborted()
      const r = await callPredict(args.image_path, exec.signal)
      const sp = r.species || {}
      const bl = r.bleaching || {}
      return {
        speciesName: sp.name ?? '',
        speciesNameCn: sp.nameCn ?? sp.name ?? '',
        speciesConfidence: Number(sp.confidence ?? 0),
        bleachingLabel: bl.label ?? '',
        bleachingLabelCn: bl.labelCn ?? bl.label ?? '',
        bleachingConfidence: Number(bl.confidence ?? 0),
        needReview: Boolean(sp.needReview || bl.needReview),
        disclaimer: r.disclaimer ?? '结果仅供保育决策参考。',
        summary: summarize(r),
      }
    },
  }))

  /* ---------------- 工具 2：服务状态（只读） ---------------- */
  ctx.tools.register(defineTool({
    name: 'coral_service_status',
    description:
      '查询珊瑚识别推理服务的健康状态与已加载模型信息（类别数、测试集准确率、拒识阈值）。'
      + '在识别失败、怀疑服务未启动，或需要向用户说明模型能力边界时调用。只读，不做识别。',
    parameters: {},
    output: {
      schema: {
        type: 'object',
        additionalProperties: false,
        properties: {
          online: { type: 'boolean', required: true, description: '服务是否在线。' },
          apiBase: { type: 'string', required: true, description: '当前使用的服务地址。' },
          device: { type: 'string', description: '推理设备（cuda/cpu）。' },
          models: { type: 'string', description: '已加载模型与指标的文本摘要。' },
          detail: { type: 'string', description: '错误信息或原始返回。' },
        },
      },
      render: textRender((v) => v.models || v.detail || (v.online ? '服务在线' : '服务离线')),
    },
    execute: async (args, exec) => {
      exec.signal.throwIfAborted()
      const base = API_BASE()
      try {
        const res = await fetch(`${base}/health`, { signal: exec.signal })
        if (!res.ok) return { online: false, apiBase: base, detail: `HTTP ${res.status}` }
        const j = await res.json()
        const lines = Object.entries(j.loaded || {}).map(([k, v]) =>
          `· ${k}: ${v.classes} 类, 测试集Top-1 ${v.testTop1 != null ? (v.testTop1 * 100).toFixed(2) + '%' : '未知'}, 拒识阈值 ${v.threshold}`)
        return {
          online: true,
          apiBase: base,
          device: String(j.device ?? ''),
          models: [`服务在线（设备 ${j.device}）`, ...lines].join('\n'),
          detail: JSON.stringify(j),
        }
      } catch (e) {
        return {
          online: false, apiBase: base,
          detail: `无法连接：${e.message}。请先启动 serve.py`,
        }
      }
    },
  }))

  /* ---------------- 工具 3：礁区覆盖评估（Model A 分割） ---------------- */
  ctx.tools.register(defineTool({
    name: 'assess_coral_cover',
    description:
      '对一张**礁区样方照片**做像素级语义分割，输出活珊瑚/白化珊瑚/死亡珊瑚/藻类覆盖/沙砾底质的'
      + '**百分比**，以及珊瑚总覆盖与白化占比；若属分类模型已就绪，还会给出主要珊瑚属。'
      + '当用户询问"这片礁区覆盖率多少""白化比例多高""珊瑚健康状况如何"，'
      + '或需要对修复点位做量化评估时调用。'
      + '本工具适合**整片礁区/样方**视角的照片；若只想问"这是什么珊瑚"，用 identify_coral。',
    parameters: {
      image_path: {
        type: 'string', required: true,
        description: '本地礁区照片绝对路径，支持 .jpg/.jpeg/.png/.webp。',
      },
      enhance_first: {
        type: 'boolean',
        description: '可选：分割前先做水下色彩还原（15m 以上浑浊水域建议开启）。默认 false。',
      },
    },
    output: {
      schema: {
        type: 'object',
        additionalProperties: false,
        properties: {
          alivePct: { type: 'number', required: true, description: '活珊瑚覆盖百分比（0–1）' },
          bleachedPct: { type: 'number', required: true, description: '白化珊瑚百分比' },
          deadPct: { type: 'number', required: true, description: '死亡珊瑚百分比' },
          algaePct: { type: 'number', required: true, description: '藻类覆盖百分比' },
          substratePct: { type: 'number', required: true, description: '沙/碎石/底质百分比' },
          coralTotalPct: { type: 'number', required: true, description: '珊瑚总覆盖（活+白化+死亡）' },
          bleachingShare: { type: 'number', required: true, description: '白化占珊瑚的比例' },
          topClasses: { type: 'string', required: true, description: '主要底栖类别明细（文本）' },
          dominantGenus: { type: 'string', description: '主要珊瑚属及置信度（若属分类模型已加载且置信度达标）' },
          bleachingState: { type: 'string', required: true, description: '白化状态结论（来自分类模型，含置信度）' },
          captureQuality: { type: 'string', required: true, description: '拍摄条件判定：good/warn/poor 及说明' },
          usable: { type: 'boolean', required: true, description: '照片是否在模型适用边界内（false 时覆盖率不可信）' },
          disclaimer: { type: 'string', required: true, description: '使用边界声明' },
          summary: { type: 'string', required: true, description: '人类可读的中文结论摘要' },
        },
      },
      render: textRender((v) => v.summary),
    },
    execute: async (args, exec) => {
      exec.signal.throwIfAborted()
      const ext = extname(args.image_path || '').toLowerCase()
      if (!MIME[ext]) throw new Error(`不支持的图片格式 "${ext}"`)
      let buf
      try {
        buf = await readFile(args.image_path)
      } catch (e) {
        throw new Error(`读取图片失败：${args.image_path}（${e.code || e.message}）`)
      }
      const form = new FormData()
      form.append('file', new Blob([buf], { type: MIME[ext] }), basename(args.image_path))
      const url = `${API_BASE()}/analyze${args.enhance_first ? '?enhance_first=true' : ''}`
      let res
      try {
        res = await fetch(url, { method: 'POST', body: form, signal: exec.signal })
      } catch (e) {
        throw new Error(`无法连接评估服务 ${API_BASE()}：${e.message}。`
          + `请先启动：cd coral_ml/scripts && python serve_fusion.py`)
      }
      if (!res.ok) {
        const t = await res.text().catch(() => '')
        throw new Error(`评估服务返回 ${res.status}：${t.slice(0, 300)}`)
      }
      const r = await res.json()
      const c = r.cover || {}
      const q = r.captureQuality || {}
      const pct = (v) => `${(Number(v || 0) * 100).toFixed(1)}%`
      const tp = (r.topClasses || []).slice(0, 5)
        .map((t) => `${t.name} ${pct(t.pct)}`).join(' / ')
      const dg = r.coralRegion && r.coralRegion.reliable !== false
        && r.coralRegion.top && r.coralRegion.top.length
        ? r.coralRegion.top.map((t) => `${t.genus} ${pct(t.confidence)}`).join(' / ')
        : ''
      return {
        alivePct: Number(c.alivePct ?? 0),
        bleachedPct: Number(c.bleachedPct ?? 0),
        deadPct: Number(c.deadPct ?? 0),
        algaePct: Number(c.algaePct ?? 0),
        substratePct: Number(c.substratePct ?? 0),
        coralTotalPct: Number(c.coralTotalPct ?? 0),
        bleachingShare: Number(c.bleachingShareOfCoral ?? 0),
        topClasses: tp,
        dominantGenus: dg,
        bleachingState: r.bleaching
          ? `${r.bleaching.labelCn || r.bleaching.label} ${pct(r.bleaching.confidence)}`
            + (r.bleaching.reliable === false ? '（置信度不足，建议人工复核）' : '')
          : '未加载白化分类模型',
        captureQuality: `[${q.level || 'unknown'}] ${q.message || ''}`,
        usable: q.usable !== false,
        disclaimer: r.disclaimer ?? '结果仅供保育决策参考。',
        summary: summarizeCoverage(r),
      }
    },
  }))
}
