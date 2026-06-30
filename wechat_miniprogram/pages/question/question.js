// pages/question/question.js
const app = getApp();

Page({
  data: {
    currentQuestions: [],
    currentQuestionIndex: 0,
    currentQuestion: {},
    currentRound: 1,
    maxRounds: 4,
    isLoading: false,
    answeredCount: 0,
    progressPercent: 0,
    canSubmit: false,
    
    // 滑动相关
    translateX: 0,
    rotate: 0,
    startX: 0,
    startY: 0,
    isSwiping: false
  },

  onLoad() {
    const questions = app.globalData.currentQuestions || [];
    if (questions.length === 0) {
      wx.showToast({ title: '暂无问题', icon: 'none' });
      return;
    }

    // 初始化问题
    questions.forEach(q => {
      q.answer = null;
      q.answers = [];
    });

    this.setData({
      currentQuestions: questions,
      currentQuestion: questions[0] || {},
      currentQuestionIndex: 0
    });

    this.updateProgress();
  },

  // 更新进度
  updateProgress() {
    const answered = this.data.currentQuestions.filter(q => {
      if (q.input_type === 'multiple') {
        return q.answers && q.answers.length > 0;
      }
      return q.answer !== null && q.answer !== undefined && q.answer !== '';
    }).length;

    const percent = (answered / this.data.currentQuestions.length) * 100;
    const canSubmit = answered > 0;

    this.setData({
      answeredCount: answered,
      progressPercent: percent,
      canSubmit: canSubmit
    });
  },

  // 单选选择
  selectSingle(e) {
    const value = e.currentTarget.dataset.value;
    const questions = this.data.currentQuestions;
    questions[this.data.currentQuestionIndex].answer = value;
    
    this.setData({
      currentQuestions: questions,
      currentQuestion: questions[this.data.currentQuestionIndex]
    });
    
    this.updateProgress();
  },

  // 多选切换
  toggleMulti(e) {
    const value = e.currentTarget.dataset.value;
    const questions = this.data.currentQuestions;
    const q = questions[this.data.currentQuestionIndex];
    
    if (!q.answers) q.answers = [];
    
    const index = q.answers.indexOf(value);
    if (index > -1) {
      q.answers.splice(index, 1);
    } else {
      q.answers.push(value);
    }
    
    this.setData({
      currentQuestions: questions,
      currentQuestion: q
    });
    
    this.updateProgress();
  },

  // 是/否选择
  selectYesNo(e) {
    const value = e.currentTarget.dataset.value;
    const questions = this.data.currentQuestions;
    questions[this.data.currentQuestionIndex].answer = value;
    
    this.setData({
      currentQuestions: questions,
      currentQuestion: questions[this.data.currentQuestionIndex]
    });
    
    this.updateProgress();
  },

  // 触摸开始
  touchStart(e) {
    this.setData({
      startX: e.touches[0].clientX,
      startY: e.touches[0].clientY,
      isSwiping: true
    });
  },

  // 触摸移动
  touchMove(e) {
    if (!this.data.isSwiping) return;
    
    const deltaX = e.touches[0].clientX - this.data.startX;
    const deltaY = e.touches[0].clientY - this.data.startY;
    
    // 只处理水平滑动
    if (Math.abs(deltaX) > Math.abs(deltaY)) {
      // 限制滑动范围
      const maxTranslate = 100;
      const translateX = Math.max(-maxTranslate, Math.min(maxTranslate, deltaX));
      const rotate = translateX / 20;
      
      this.setData({
        translateX: translateX,
        rotate: rotate
      });
    }
  },

  // 触摸结束
  touchEnd(e) {
    if (!this.data.isSwiping) return;
    
    const deltaX = this.data.translateX;
    const threshold = 50;
    
    if (deltaX < -threshold) {
      // 左滑 - 下一题
      if (this.data.currentQuestionIndex < this.data.currentQuestions.length - 1) {
        this.nextQuestion();
      }
    } else if (deltaX > threshold) {
      // 右滑 - 上一题
      if (this.data.currentQuestionIndex > 0) {
        this.prevQuestion();
      }
    }
    
    // 重置滑动状态
    this.setData({
      translateX: 0,
      rotate: 0,
      isSwiping: false
    });
  },

  // 下一题
  nextQuestion() {
    const index = this.data.currentQuestionIndex;
    const questions = this.data.currentQuestions;
    
    if (index >= questions.length - 1) {
      // 已经是最后一题，提交答案
      this.submitAnswers();
      return;
    }
    
    const nextIndex = index + 1;
    this.setData({
      currentQuestionIndex: nextIndex,
      currentQuestion: questions[nextIndex]
    });
  },

  // 上一题
  prevQuestion() {
    const index = this.data.currentQuestionIndex;
    const questions = this.data.currentQuestions;
    
    if (index <= 0) return;
    
    const prevIndex = index - 1;
    this.setData({
      currentQuestionIndex: prevIndex,
      currentQuestion: questions[prevIndex]
    });
  },

  // 提交答案
  async submitAnswers() {
    const questions = this.data.currentQuestions;
    const answered = questions.filter(q => {
      if (q.input_type === 'multiple') {
        return q.answers && q.answers.length > 0;
      }
      return q.answer !== null && q.answer !== '';
    });

    if (answered.length === 0) {
      wx.showToast({ title: '请至少回答一个问题', icon: 'none' });
      return;
    }

    this.setData({ isLoading: true });

    try {
      // 准备答案数据
      const answers = answered.map(q => ({
        question_id: q.question_id,
        question: q.question,
        answer: q.input_type === 'multiple' ? q.answers : q.answer,
        answer_type: q.input_type
      }));

      // 调用后端API
      const response = await this.callAPI('/diagnosis/follow-up', {
        session_id: app.globalData.sessionId,
        answers: answers
      });

      // 处理返回
      if (response.next_round_questions && response.next_round_questions.length > 0) {
        // 继续下一轮
        const newQuestions = response.next_round_questions;
        newQuestions.forEach(q => {
          q.answer = null;
          q.answers = [];
        });
        
        app.globalData.currentQuestions = newQuestions;
        app.globalData.currentQuestionIndex = 0;
        
        this.setData({
          currentQuestions: newQuestions,
          currentQuestion: newQuestions[0] || {},
          currentQuestionIndex: 0,
          currentRound: this.data.currentRound + 1
        });
        
        this.updateProgress();
        
        wx.showToast({
          title: '进入下一轮',
          icon: 'success'
        });
      } else {
        // 诊断完成，跳转到结果页
        this.goToResult();
      }

    } catch (error) {
      console.error('提交答案失败:', error);
      wx.showToast({ title: '提交失败，请重试', icon: 'none' });
    } finally {
      this.setData({ isLoading: false });
    }
  },

  // 跳转到结果页
  goToResult() {
    wx.redirectTo({
      url: '/pages/result/result'
    });
  },

  // 调用API
  callAPI(endpoint, data) {
    return new Promise((resolve, reject) => {
      wx.request({
        url: `${app.globalData.apiBase}${endpoint}`,
        method: 'POST',
        data,
        header: { 'content-type': 'application/json' },
        success: (res) => {
          if (res.statusCode === 200) {
            resolve(res.data);
          } else {
            reject(res);
          }
        },
        fail: (err) => {
          reject(err);
        }
      });
    });
  },

  // 获取计算属性
  get hasNext() {
    return this.data.currentQuestionIndex < this.data.currentQuestions.length - 1;
  },

  get hasPrev() {
    return this.data.currentQuestionIndex > 0;
  },

  get isLastQuestion() {
    return this.data.currentQuestionIndex >= this.data.currentQuestions.length - 1;
  }
});
