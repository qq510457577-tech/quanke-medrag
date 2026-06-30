// pages/symptoms/symptoms.js
const app = getApp();

Page({
  data: {
    symptoms: [
      { description: '', durationYears: 0, durationMonths: 0, durationDays: 0, severity: 1 }
    ],
    commonSymptoms: ['头晕', '头痛', '胸痛', '腹痛', '腰痛', '咳嗽', '发热', '乏力', '恶心', '心悸', '气短', '腹泻'],
    years: Array.from({length: 11}, (_, i) => i),
    months: Array.from({length: 12}, (_, i) => i),
    days: Array.from({length: 31}, (_, i) => i),
    severityText: ['', '轻', '较轻', '中', '较重', '重'],
    isLoading: false
  },

  onLoad() {
    // Load saved symptoms
    const saved = wx.getStorageSync('symptoms');
    if (saved && saved.length > 0) {
      this.setData({ symptoms: saved });
    }
  },

  // 症状描述输入
  onSymptomInput(e) {
    const index = e.currentTarget.dataset.index;
    const symptoms = this.data.symptoms;
    symptoms[index].description = e.detail.value;
    this.setData({ symptoms });
  },

  // 持续时间变化
  onDurationChange(e) {
    const index = e.currentTarget.dataset.index;
    const type = e.currentTarget.dataset.type;
    const value = parseInt(e.detail.value);
    const symptoms = this.data.symptoms;
    
    if (type === 'years') symptoms[index].durationYears = value;
    else if (type === 'months') symptoms[index].durationMonths = value;
    else if (type === 'days') symptoms[index].durationDays = value;
    
    this.setData({ symptoms });
  },

  // 设置严重程度
  setSeverity(e) {
    const index = e.currentTarget.dataset.index;
    const level = e.currentTarget.dataset.level;
    const symptoms = this.data.symptoms;
    symptoms[index].severity = level;
    this.setData({ symptoms });
  },

  // 添加症状
  addSymptom() {
    const symptoms = this.data.symptoms;
    symptoms.push({ description: '', durationYears: 0, durationMonths: 0, durationDays: 0, severity: 1 });
    this.setData({ symptoms });
  },

  // 删除症状
  removeSymptom(e) {
    const index = e.currentTarget.dataset.index;
    const symptoms = this.data.symptoms;
    if (symptoms.length > 1) {
      symptoms.splice(index, 1);
      this.setData({ symptoms });
    }
  },

  // 快速添加症状
  quickAddSymptom(e) {
    const symptom = e.currentTarget.dataset.symptom;
    const symptoms = this.data.symptoms;
    
    // 找第一个空的位置
    const emptyIndex = symptoms.findIndex(s => !s.description.trim());
    if (emptyIndex >= 0) {
      symptoms[emptyIndex].description = symptom;
    } else {
      symptoms.push({ description: symptom, durationYears: 0, durationMonths: 0, durationDays: 0, severity: 1 });
    }
    
    this.setData({ symptoms });
  },

  // 验证表单
  validate() {
    const symptoms = this.data.symptoms;
    const hasValidSymptom = symptoms.some(s => s.description.trim());
    
    if (!hasValidSymptom) {
      wx.showToast({
        title: '请至少填写一个症状',
        icon: 'none'
      });
      return false;
    }
    
    return true;
  },

  // 提交症状，开始诊断
  async submitSymptoms() {
    if (!this.validate()) return;

    this.setData({ isLoading: true });

    try {
      const patientInfo = app.globalData.patientInfo;
      const symptoms = this.data.symptoms.filter(s => s.description.trim());

      // 调用后端API
      const response = await this.callAPI('/diagnosis/start', {
        patient: patientInfo,
        symptoms: symptoms,
        session_id: null
      });

      // 保存诊断数据
      app.globalData.sessionId = response.session_id;
      app.globalData.currentQuestions = response.current_questions || [];
      app.globalData.diagnosisHypothesis = response.diagnosis_hypothesis || [];
      app.globalData.reasoningChain = response.reasoning_chain || '';
      app.globalData.currentQuestionIndex = 0;

      // 保存到本地
      wx.setStorageSync('symptoms', symptoms);

      // 跳转到问答页面
      wx.navigateTo({
        url: '/pages/question/question'
      });

    } catch (error) {
      console.error('诊断失败:', error);
      wx.showToast({
        title: '诊断服务暂时不可用',
        icon: 'none'
      });
    } finally {
      this.setData({ isLoading: false });
    }
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

  goBack() {
    wx.navigateBack();
  }
});
