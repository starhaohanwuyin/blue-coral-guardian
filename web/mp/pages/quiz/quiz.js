/**
 * 知识问答页
 * 逐题作答即时反馈 → 结果页 → 提交成绩（api.submitQuiz）
 */
const api = require('../../utils/api.js')
const util = require('../../utils/util.js')

const LETTERS = ['A', 'B', 'C', 'D']

Page({
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
      this.setData({ questions: list || [] })
    }).catch((e) => util.toast(e.message || '加载失败'))
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
    this.setData({
      index: 0,
      score: 0,
      selected: -1,
      answered: false,
      isCorrect: false,
      finished: false
    })
  },

  goKnowledge() {
    wx.switchTab({ url: '/pages/knowledge/knowledge' })
  }
})
