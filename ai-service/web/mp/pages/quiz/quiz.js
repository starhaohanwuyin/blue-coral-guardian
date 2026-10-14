/**
 * 知识问答页
 * 逐题作答即时反馈 → 结果页 → 提交成绩（api.submitQuiz）
 */
const api = require('../../utils/api.js')
const util = require('../../utils/util.js')

const LETTERS = ['A', 'B', 'C', 'D']
const ROUND_SIZE = 5              // 每轮抽几题

/** Fisher–Yates 洗牌（不改原数组） */
function shuffle(arr) {
  const a = (arr || []).slice()
  for (let i = a.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1))
    ;[a[i], a[j]] = [a[j], a[i]]
  }
  return a
}

/** 抽题：从题库随机取 n 题，并把每题选项也打乱（同步修正 answer） */
function drawRound(bank, n) {
  return shuffle(bank).slice(0, Math.min(n, bank.length)).map((q) => {
    const pairs = (q.options || []).map((text, i) => ({ text, right: i === q.answer }))
    const mixed = shuffle(pairs)
    return {
      q: q.q,
      options: mixed.map((p) => p.text),
      answer: mixed.findIndex((p) => p.right),
      explain: q.explain || ''
    }
  })
}

const pageI18n = require('../../utils/page-i18n.js')

Page(pageI18n.wrap({
  data: {
    questions: [],
    index: 0,
    score: 0,
    selected: -1,
    answered: false,
    isCorrect: false,
    correctLetter: '',
    finished: false
  },

  onLoad() {
    api.getQuizQuestions().then((list) => {
      this._bank = list || []
      this.startRound()
    }).catch((e) => util.toast(e.message || '加载失败'))
  },

  /* 开新一轮：从题库随机抽题 */
  startRound() {
    this.setData({
      questions: drawRound(this._bank || [], ROUND_SIZE),
      index: 0,
      score: 0,
      selected: -1,
      answered: false,
      isCorrect: false,
      correctLetter: '',
      finished: false
    })
  },

  onSelect(e) {
    if (this.data.answered) return
    const i = Number(e.currentTarget.dataset.index)
    const q = this.data.questions[this.data.index]
    const isCorrect = i === q.answer
    this.setData({
      selected: i,
      answered: true,
      isCorrect,
      correctLetter: LETTERS[q.answer],
      score: this.data.score + (isCorrect ? 1 : 0)
    })
  },

  onNext() {
    const next = this.data.index + 1
    if (next >= this.data.questions.length) {
      this.setData({ finished: true })
      api.submitQuiz(this.data.score, this.data.questions.length).catch(() => {})
      return
    }
    this.setData({ index: next, selected: -1, answered: false, isCorrect: false })
  },

  onRestart() {
    this.startRound()            // 再来一轮：重新随机抽题
  },

  goKnowledge() {
    wx.switchTab({ url: '/pages/knowledge/knowledge' })
  }
}))
