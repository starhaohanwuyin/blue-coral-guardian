/**
 * 蓝珊 · 珊瑚识别 Skill 插件（DSH / Cordis）
 * ================================================================
 * 提供 1 个 Skill + 2 个工具，供蓝珊 Agent 自主调度：
 *
 *   Skill: coral-identification      珊瑚种类识别与白化程度评估
 *   Tool : identify_coral            对一张水下照片做双任务识别
 *   Tool : coral_service_status      查询推理服务与模型状态（只读）
 *
 * 工具能力来自本地/远端推理服务（coral_ml/scripts/serve_fusion.py），
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

/**
 * 调用 serve_fusion.py 的 /analyze。
 * lat/lon/year 可选：给了服务端会顺带返回气候背景与修复优先级研判。
 */
async function callAnalyze(imagePath, signal, lat, lon, year) {
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

  const qs = new URLSearchParams()
  if (lat != null) qs.set('lat', String(lat))
  if (lon != null) qs.set('lon', String(lon))
  if (year != null) qs.set('year', String(year))
  const suffix = qs.toString() ? `?${qs}` : ''

  let res
  try {
    res = await fetch(`${API_BASE()}/analyze${suffix}`, { method: 'POST', body: form, signal })
  } catch (e) {
    throw new Error(
      `无法连接珊瑚识别服务 ${API_BASE()}：${e.message}。` +
      `请先启动：cd coral_ml/scripts && python serve_fusion.py`,
    )
  }
  if (!res.ok) {
    const t = await res.text().catch(() => '')
    throw new Error(`识别服务返回 ${res.status}：${t.slice(0, 300)}`)
  }
  return await res.json()
}

// 向后兼容旧名
const callPredict = callAnalyze

/** 推测结果的中文摘要（给模型和用户看的自然语言）。 */
function summarize(r) {
  // 适配 serve_fusion.py /analyze 的返回结构：
  //   cover{覆盖率} + coralRegion{属识别} + bleaching{白化状态}
  const cr = r.coralRegion || {}
  const top = (cr.top && cr.top[0]) || {}
  const bl = r.bleaching || {}
  const c = r.cover || {}
  const q = r.captureQuality || {}
  const pct = (v) => `${(Number(v || 0) * 100).toFixed(1)}%`
  const lines = []
  if (q.usable === false) {
    lines.push('⚠ 拍摄条件超出模型适用边界，以下结果可能严重失真：')
    lines.push(`　　${q.message || '建议在 10 米以内或加补光灯重拍'}`)
  }
  if (cr.reliable === false) {
    lines.push(`【珊瑚属】置信度不足（${cr.note || '低于门槛'}），本次不给出属级结论`)
  } else {
    lines.push(`【珊瑚属】${top.genus || '未知'}  置信度 ${pct(top.confidence)}`)
    const rest = (cr.top || []).slice(1, 3)
    if (rest.length) lines.push('　　其他可能：' + rest.map((t) => `${t.genus} ${pct(t.confidence)}`).join(' / '))
  }
  if (bl.label || bl.labelCn) {
    const rel = bl.reliable === false ? '（置信度不足，建议人工复核）' : ''
    lines.push(`【白化状态】${bl.labelCn || bl.label}  置信度 ${pct(bl.confidence)}${rel}`)
  } else {
    lines.push('【白化状态】白化分类模型未加载')
  }
  lines.push(`【覆盖】活珊瑚 ${pct(c.alivePct)}　珊瑚总覆盖 ${pct(c.coralTotalPct)}`)
  if (q.level === 'warn') lines.push(`💡 ${q.message || '拍摄条件一般，建议开补光灯'}`)
  lines.push(`（耗时 ${r.inferenceMs ?? '?'} ms；结果仅供保育决策参考）`)
  return lines.join('\n')
}

export function apply(ctx) {
  /* ---------------- 工具 4：环境数据插件（只读） ---------------- */
  ctx.tools.register(defineTool({
    name: 'get_climate_context',
    description:
      '环境数据插件：查询某个经纬度的海表热压力与白化风险（数据源 NOAA Coral Reef Watch）。'
      + '返回 DHW 峰值、白化预警等级（BAA 0–4）、热浪天数、与其它年份的对比。'
      + '当用户询问「这片海域水温怎么样」「有没有白化风险」「今年热不热」时调用。'
      + '坐标需在数据覆盖范围内（4.0–5.0N, 118.0–119.5E，即仙本那及周边）。',
    parameters: {
      lat: { type: 'number', required: true, description: '纬度，如 4.4' },
      lon: { type: 'number', required: true, description: '经度，如 118.8' },
      year: { type: 'number', required: false, description: '年份（2023/2024/2025），缺省取最新' },
    },
    output: {
      schema: {
        type: 'object',
        additionalProperties: false,
        properties: {
          ok: { type: 'boolean', required: true, description: '查询是否成功' },
          year: { type: 'number', required: true, description: '评估年份' },
          dhwMax: { type: 'number', required: true, description: '年度 DHW 峰值（°C·周）' },
          baaLabel: { type: 'string', required: true, description: '白化预警等级中文名' },
          baa: { type: 'number', required: true, description: 'BAA 等级 0–4' },
          daysDhwGe8: { type: 'number', required: true, description: 'DHW≥8 的天数（严重热应激）' },
          anomalyNote: { type: 'string', required: true, description: '与其它年份的对比说明' },
          verdict: { type: 'string', required: true, description: '热压力解读' },
          summary: { type: 'string', required: true, description: '中文摘要' },
        },
      },
      render: textRender((v) => v.summary),
    },
    execute: async (args, exec) => {
      exec.signal.throwIfAborted()
      const base = API_BASE()
      let j
      try {
        const qs = new URLSearchParams({ lat: String(args.lat), lon: String(args.lon) })
        if (args.year) qs.set('year', String(args.year))
        const res = await fetch(`${base}/climate?${qs}`, { signal: exec.signal })
        if (!res.ok) throw new Error(`服务返回 ${res.status}`)
        j = await res.json()
      } catch (e) {
        throw new Error(`无法连接环境数据服务 ${base}：${e.message}。请先启动 serve_fusion.py`)
      }
      if (!j.ok) {
        return { ok: false, year: 0, dhwMax: 0, baaLabel: '无数据', baa: 0,
                 daysDhwGe8: 0, anomalyNote: '', verdict: j.error || '无数据',
                 summary: `查询失败：${j.error || '该坐标无数据'}` }
      }
      const pct = (v) => `${(Number(v || 0) * 100).toFixed(1)}%`
      const lines = [
        `【海表热压力 · ${j.year} 年】`,
        `  格点：${j.gridCell.lat}°N ${j.gridCell.lon}°E（NOAA 5km）`,
        `  DHW 峰值：${j.dhwMax}　白化预警：${j.baaLabel}（${j.baa}/4）`,
        `  热浪天数：DHW≥4 共 ${j.daysDhwGe4} 天，DHW≥8 共 ${j.daysDhwGe8} 天`,
        `  年度对比：${j.anomalyNote}`,
        `  解读：${j.verdict}`,
      ]
      return {
        ok: true, year: j.year, dhwMax: j.dhwMax, baa: j.baa, baaLabel: j.baaLabel,
        daysDhwGe8: j.daysDhwGe8, anomalyNote: j.anomalyNote, verdict: j.verdict,
        summary: lines.join('\n'),
      }
    },
  }))

  /* ---------------- 工具 5：综合研判 + 保育报告 ---------------- */
  ctx.tools.register(defineTool({
    name: 'assess_restoration_priority',
    description:
      '综合研判插件：融合图像研判与 NOAA 环境数据，输出礁区修复优先级、'
      + '珊瑚苗投放适宜度，并自动生成中文保育报告。'
      + '当用户询问「哪里该优先修复」「苗投哪里好」「给我一份保育报告」时调用。'
      + '需要先用 assess_coral_cover 得到覆盖率，再把结果传进来（或用 image_path 一并分析）。',
    parameters: {
      image_path: { type: 'string', required: false,
        description: '本地珊瑚照片绝对路径；给了就自动先做图像研判' },
      alive_pct: { type: 'number', required: false, description: '活珊瑚覆盖率 0–1' },
      bleached_pct: { type: 'number', required: false, description: '白化珊瑚覆盖率 0–1' },
      dead_pct: { type: 'number', required: false, description: '死亡珊瑚覆盖率 0–1' },
      algae_pct: { type: 'number', required: false, description: '藻类覆盖率 0–1' },
      lat: { type: 'number', required: true, description: '纬度（用于查环境数据）' },
      lon: { type: 'number', required: true, description: '经度（用于查环境数据）' },
      year: { type: 'number', required: false, description: '年份，缺省最新' },
    },
    output: {
      schema: {
        type: 'object',
        additionalProperties: false,
        properties: {
          priority: { type: 'number', required: true, description: '修复优先级 0–100' },
          gradeLabel: { type: 'string', required: true, description: '优先级分级中文' },
          seedlingSuitability: { type: 'number', required: true, description: '苗投放适宜度 0–100' },
          recoveryScore: { type: 'number', required: true, description: '恢复潜力 0–100' },
          urgencyScore: { type: 'number', required: true, description: '紧迫度 0–100' },
          topAction: { type: 'string', required: true, description: '首要行动建议' },
          deploymentAdvice: { type: 'string', required: true, description: '投放建议（一句结论 + 三条依据 + 建议避开月份）；无数据时为空串' },
          avoidMonths: { type: 'string', required: true, description: '建议避开投放的月份，如「4、5、6、7 月」；无数据时为空串' },
          report: { type: 'string', required: true, description: '完整中文保育报告' },
          disclaimer: { type: 'string', required: true, description: '定位声明' },
        },
      },
      render: textRender((v) => v.report),
    },
    execute: async (args, exec) => {
      exec.signal.throwIfAborted()
      const base = API_BASE()

      // 若给了图片，先做一次图像研判拿到覆盖率
      let cover = null
      if (args.image_path) {
        const a = await callAnalyze(args.image_path, exec.signal, args.lat, args.lon, args.year)
        cover = a.cover
      } else if (args.alive_pct != null) {
        const al = Number(args.alive_pct || 0), bl = Number(args.bleached_pct || 0),
              dd = Number(args.dead_pct || 0)
        cover = { alivePct: al, bleachedPct: bl, deadPct: dd,
                  algaePct: Number(args.algae_pct || 0),
                  coralTotalPct: al + bl + dd }
      }
      if (!cover) throw new Error('需要提供 image_path 或 alive_pct 等覆盖率数值')

      const body = JSON.stringify({ cover, lat: args.lat, lon: args.lon, year: args.year })
      let j
      try {
        const res = await fetch(`${base}/priority`, {
          method: 'POST', headers: { 'Content-Type': 'application/json' },
          body, signal: exec.signal,
        })
        if (!res.ok) throw new Error(`服务返回 ${res.status}`)
        j = await res.json()
      } catch (e) {
        throw new Error(`无法连接研判服务 ${base}：${e.message}。请先启动 serve_fusion.py`)
      }
      return {
        priority: Number(j.priority ?? 0),
        gradeLabel: String(j.gradeLabel ?? ''),
        seedlingSuitability: Number(j.seedlingSuitability ?? 0),
        recoveryScore: Number(j.recovery?.score ?? 0),
        urgencyScore: Number(j.urgency?.score ?? 0),
        topAction: String((j.actions || [])[0] ?? ''),
        deploymentAdvice: String(j.deploymentAdvice?.summaryText ?? ''),
        avoidMonths: ((j.deploymentAdvice?.avoidMonths) || []).map((m) => `${m} 月`).join('、'),
        report: String(j.report ?? ''),
        disclaimer: String(j.disclaimer ?? ''),
      }
    },
  }))

  /* ---------------- 工具 6：投放建议（往年白化预警记录） ---------------- */
  ctx.tools.register(defineTool({
    name: 'get_deployment_advice',
    description:
      '**投放建议**：用往年白化预警记录（NOAA CRW DHW/BAA/HotSpot，2023–2025）判断'
      + '某个坐标「适不适合投放珊瑚苗、该避开哪几个月」。返回逐年 DHW 峰值、'
      + '达到白化警戒的年份、风险月份与建议。'
      + '当用户问「这片海适合什么时候投放」「往年什么时候白化严重」「这个点稳不稳」时调用。'
      + '⚠️ 只覆盖**热压力**一个维度（底质/水流/藻类/人力不在内），样本仅 3 年，'
      + '且**不是投放效果评估**。坐标需在 4.025–5.025N × 118.025–119.525E 内，网格外会明确报无数据。',
    parameters: {
      lat: { type: 'number', required: true, description: '纬度，如 4.425' },
      lon: { type: 'number', required: true, description: '经度，如 118.775' },
    },
    output: {
      schema: {
        type: 'object',
        additionalProperties: false,
        properties: {
          ok: { type: 'boolean', required: true, description: '查询是否成功（网格外为 false）' },
          label: { type: 'string', required: true, description: '判定，如「年年达白化警戒」「近 3 年均未达警戒」' },
          alertYears: { type: 'string', required: true, description: '达到警戒的年份' },
          avoidMonths: { type: 'string', required: true, description: '建议避开的月份' },
          safeMonths: { type: 'string', required: true, description: '无风险信号的月份' },
          advice: { type: 'string', required: true, description: '规则化建议（一句话）' },
          summary: { type: 'string', required: true, description: '人类可读的中文摘要' },
        },
      },
      render: textRender((v) => v.summary),
    },
    execute: async (args, exec) => {
      exec.signal.throwIfAborted()
      const base = API_BASE()
      let j
      try {
        const qs = new URLSearchParams({ lat: String(args.lat), lon: String(args.lon) })
        const res = await fetch(`${base}/climate/profile?${qs}`, { signal: exec.signal })
        if (!res.ok) throw new Error(`服务返回 ${res.status}`)
        j = await res.json()
      } catch (e) {
        throw new Error(`无法连接投放档案服务 ${base}：${e.message}。请先启动 serve_fusion.py`)
      }
      const monthTxt = (arr) => (arr || []).map((m) => `${m} 月`).join('、') || '无'
      if (!j.ok) {
        return { ok: false, label: '无数据', alertYears: '', avoidMonths: '', safeMonths: '',
                 advice: '', summary: `无法给出投放建议：${j.error || '该坐标无数据'}` }
      }
      const lines = [
        `【投放建议 · 格点 ${j.gridCell.lat}°N ${j.gridCell.lon}°E（NOAA 5km）】`,
        `  判定：${j.label}（达警戒年份：${(j.alertYears || []).join('、') || '无'}）`,
        `  逐年 DHW 峰值：${JSON.stringify(j.peakByYear)}`,
        `  建议避开：${monthTxt(j.avoidMonths)}　无风险月份：${monthTxt(j.safeMonths)}`,
        '',
        j.advice?.text || '',
        '',
        `⚠️ ${j.adviceNote || ''}`,
      ]
      return {
        ok: true,
        label: String(j.label ?? ''),
        alertYears: (j.alertYears || []).join('、'),
        avoidMonths: monthTxt(j.avoidMonths),
        safeMonths: monthTxt(j.safeMonths),
        advice: String(j.advice?.text ?? ''),
        summary: lines.join('\n'),
      }
    },
  }))

  /* ---------------- Skill 注册 ---------------- */
  ctx.skills.register({
    name: 'coral-identification',
    description: '识别水下珊瑚影像的珊瑚属，并评估珊瑚白化状态（健康 / 白化 / 死亡）与覆盖率。',
    whenToUse:
      '当用户上传或指向一张水下珊瑚照片，并询问"这是什么珊瑚""珊瑚白化了吗""健康状态如何"时使用。'
      + '该 Skill 依赖本地评估服务 coral_ml/scripts/serve_fusion.py（默认 http://127.0.0.1:8000）。',
    source: 'runtime',
    invocation: { modelInvocable: true, userInvocable: true },
    content: [
      '# 珊瑚识别（coral-identification）',
      '',
      '## 能做什么',
      '- 珊瑚**属**识别：**34 属**闭集分类（**属级，不是种级**），在分割出的珊瑚主体区域上判定',
      '- 白化程度评估：健康 / 白化 / 死亡 三分类（**整图级**，不是逐个体）',
      '- 覆盖率评估：活 / 白化 / 死亡 / 藻类 / 底质等百分比（区域尺度）',
      '- 珊瑚**个体计数 + 位置**（P3 附加能力，YOLOv9c 单类检测）',
      '- 环境背景与**投放建议**：NOAA 热压力 + 往年白化预警记录 → 建议避开哪几个月投放',
      '- 以上结果在同一次调用中返回，并附带置信度与"是否需人工复核"标记',
      '',
      '## 怎么用',
      '1. 先确认用户提供了**本地图片路径**（jpg/png/webp/bmp）。',
      '2. 调用 `identify_coral(image_path=...)`。',
      '3. 把返回的**属名**、白化状态与覆盖率用自然语言汇报；',
      '   **务必同时说明置信度**，并在 `needReview` 为 true 时提示转人工复核。',
      '4. 用户问"有多少株珊瑚"→ 用 `/analyze` 的 `coralCount`（或 `POST /count`）。',
      '5. 用户问"这片海适不适合投放 / 什么时候投"→ 调用 `get_deployment_advice(lat, lon)`，',
      '   或 `assess_restoration_priority` 取其中的 `deploymentAdvice`。',
      '   ⚠️ 该建议**只有热压力一个维度**（样本仅 2023–2025、5km 格点），',
      '   **不是投放效果评估**（项目没有投放后存活率数据）—— 汇报时不要写"效果好"。',
      '',
      '## 汇报口径（重要，属于安全使用边界）',
      '- 数值来自视觉模型测量，不要自行改写或推测百分比。',
      '- 结果仅为保育决策参考，不能作为唯一依据；',
      '- 低置信度样本必须显式提示"建议人工复核"。',
      '',
      '## 服务未启动时',
      '提示用户执行：`cd coral_ml/scripts && python serve_fusion.py`，',
      '或用 `coral_service_status` 查看服务与模型状态。',
    ].join('\n'),
  })

  /* ---------------- 工具 1：识别 ---------------- */
  ctx.tools.register(defineTool({
    name: 'identify_coral',
      description:
        '对一张本地水下珊瑚照片同时给出三件事：(1) 珊瑚**属**识别（34 属，'
        + '在分割出的珊瑚主体区域上判定，含置信度）；(2) 白化状态（健康/白化/死亡）；'
        + '(3) 活珊瑚与珊瑚总覆盖百分比。'
        + '当用户上传珊瑚照片并询问「这是什么珊瑚」「白化了吗」「健康状态如何」时调用。'
        + '需要本地图片绝对路径；服务地址由 CORAL_API_BASE 指定（默认 http://127.0.0.1:8000），'
        + '需先启动 coral_ml/scripts/serve_fusion.py。',
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
          genusName: { type: 'string', required: true, description: '识别出的珊瑚属（拉丁属名）；置信度不足时为空串。' },
          genusConfidence: { type: 'number', required: true, description: '属识别置信度 0–1。' },
          genusReliable: { type: 'boolean', required: true, description: '属识别是否达到置信度门槛。' },
          bleachingLabel: { type: 'string', required: true, description: '白化状态：healthy | bleached | dead。' },
          bleachingLabelCn: { type: 'string', required: true, description: '白化状态中文：健康 | 白化 | 死亡。' },
          bleachingConfidence: { type: 'number', required: true, description: '白化状态置信度 0–1。' },
          bleachingReliable: { type: 'boolean', required: true, description: '白化判定是否达到置信度门槛。' },
          alivePct: { type: 'number', required: true, description: '活珊瑚覆盖百分比 0–1。' },
          coralTotalPct: { type: 'number', required: true, description: '珊瑚总覆盖百分比 0–1。' },
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
      // /analyze 返回：cover(覆盖率) + coralRegion(属识别) + bleaching(白化状态)
      const cr = r.coralRegion || {}
      const top = (cr.top && cr.top[0]) || {}
      const bl = r.bleaching || {}
      const c = r.cover || {}
      const genusReliable = cr.reliable !== false
      const genus = genusReliable ? (top.genus ?? '') : ''
      return {
        genusName: genus,
        genusConfidence: genusReliable ? Number(top.confidence ?? 0) : 0,
        genusReliable,
        bleachingLabel: bl.label ?? '',
        bleachingLabelCn: bl.labelCn ?? bl.label ?? '',
        bleachingConfidence: Number(bl.confidence ?? 0),
        bleachingReliable: bl.reliable !== false,
        alivePct: Number(c.alivePct ?? 0),
        coralTotalPct: Number(c.coralTotalPct ?? 0),
        needReview: !genusReliable || bl.reliable === false || !genus,
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
        // serve_fusion.py /health: {segmentation, species, segModel, segCalibrated, categories}
        const lines = []
        lines.push(`· 分割模型: ${j.segModel || '—'}  ${j.segmentation === 'loaded' ? '已加载' : '缺失'}`)
        lines.push(`· 权重校准: ${j.segCalibrated === true ? '✅ 已校准' : '⚠️ 未校准（覆盖率会偏高）'}`)
        lines.push(`· 底栖类别: ${j.categories ?? '—'} 类`)
        lines.push(`· 属分类  : ${j.species === 'loaded' ? '已加载' : '未加载'}`)
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
          detail: `无法连接：${e.message}。请先启动 serve_fusion.py`,
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
