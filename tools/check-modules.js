#!/usr/bin/env node
/**
 * 静态闸门：检查小程序 JS 里是否**使用了未声明的模块变量**。
 *
 * 背景（真实事故）：pages/ai/ai.js 里用了 `config.DEFAULT_SITE`，但该文件从未
 * `const config = require(...)`（只有一处行内 `require(...).CORAL_API`）。
 * 结果：点击「开始识别」→ startAnalysis 内同步抛 ReferenceError
 *   → promise 根本没建立 → `.catch` 不执行 → 页面**永远停在 loading**，
 *   而且服务端日志里没有任何请求（因为请求压根没发出去）。
 * 这类错误：
 *   · 语法检查（node --check）查不出来 —— 它不是语法错误
 *   · 单元测试也查不出来 —— 只测了其它函数、没点按钮
 *   · 开发者工具「编译无报错」同样查不出来
 * 所以用一个 3 秒的静态扫描兜住。
 *
 * 用法：node tools/check-modules.js   （在任何目录下都可运行）
 * 退出码：0 = 通过；1 = 发现未声明使用
 */
const fs = require('fs')
const path = require('path')

const ROOT = path.resolve(__dirname, '..')
const SCAN_DIRS = ['pages', 'components', 'utils', 'tools']
const EXTRA_FILES = ['app.js']
const MODULES = ['config', 'util', 'api', 'app', 'mock', 'req']

function walk(dir, out) {
  if (!fs.existsSync(dir)) return out
  for (const name of fs.readdirSync(dir)) {
    const p = path.join(dir, name)
    const st = fs.statSync(p)
    if (st.isDirectory()) {
      if (name === 'node_modules' || name === '.git') continue
      walk(p, out)
    } else if (name.endsWith('.js')) {
      if (p === __filename) continue   // 不扫自己：脚本里有 'app.js' 这类字符串会误报
      out.push(p)
    }
  }
  return out
}

const files = []
for (const d of SCAN_DIRS) walk(path.join(ROOT, d), files)
for (const f of EXTRA_FILES) {
  const p = path.join(ROOT, f)
  if (fs.existsSync(p)) files.push(p)
}

const problems = []
for (const file of files) {
  const src = fs.readFileSync(file, 'utf8')
  // 去掉注释，避免注释里提到 "utils/api.js" 之类的误报
  const code = src
    .replace(/\/\*[\s\S]*?\*\//g, '')
    .replace(/(^|[^:])\/\/[^\n]*/g, '$1')
  for (const m of MODULES) {
    const used = new RegExp('\\b' + m + '\\s*\\.')
    const declared = new RegExp('(const|let|var)\\s+' + m + '\\s*=')
    if (used.test(code) && !declared.test(code)) {
      const line = code.split('\n').findIndex((l) => used.test(l)) + 1
      problems.push(
        `${path.relative(ROOT, file)}:${line} 使用了未声明的模块变量 \`${m}\`（缺少 const ${m} = require(...)）`
      )
    }
  }
}

console.log(`已扫描 ${files.length} 个 JS 文件`)
if (problems.length) {
  console.error('\n❌ 发现未声明的模块变量使用（会导致运行时 ReferenceError）：')
  for (const p of problems) console.error('  · ' + p)
  console.error('\n修复：在文件顶部加对应 require，例如 const config = require(\'../../utils/config.js\')')
  process.exit(1)
}
console.log('✅ 未发现未声明的模块变量使用')
