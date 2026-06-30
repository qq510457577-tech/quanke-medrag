// pages/result/result.js
const app = getApp();

Page({
  data: {
    diagnosisHypothesis: [],
    reasoningChain: '',
    requiredExaminations: [],
    optionalExaminations: [],
    riskStratification: '',
    isLoading: false
  },

  onLoad() {
    this.loadDiagnosisData();
  },

  onShow() {
    // 尝试获取最终诊断
    this.getFinalDiagnosis();
  },

  // 加载诊断数据
  loadDiagnosisData() {
    const hypothesis = app.globalData.diagnosisHypothesis || [];
    const reasoning = app.globalData.reasoningChain || '';
    
    this.setData({
      diagnosisHypothesis: hypothesis,
      reasoningChain: reasoning
    });
  },

  // 获取最终诊断
  async getFinalDiagnosis() {
    if (!app.globalData.sessionId) {
      return;
    }

    this.setData({ isLoading: true });

    try {
      const response = await this.callAPI('/diagnosis/final', {
        session_id: app.globalData.sessionId
      });

      if (response.diagnoses && response.diagnoses.length > 0) {
        this.setData({
          diagnosisHypothesis: response.diagnoses,
          requiredExaminations: response.required_examinations || [],
          optionalExaminations: response.optional_examinations || [],
          riskStratification: response.risk_stratification || ''
        });
      }

    } catch (error) {
      console.error('获取最终诊断失败:', error);
    } finally {
      this.setData({ isLoading: false });
    }
  },

  // 保存结果
  saveResult() {
    const history = wx.getStorageSync('diagnosis_history') || [];
    
    const record = {
      id: Date.now(),
      date: new Date().toLocaleString('zh-CN'),
      patientInfo: app.globalData.patientInfo,
      symptoms: wx.getStorageSync('symptoms') || [],
      diagnosisHypothesis: this.data.diagnosisHypothesis,
      reasoningChain: this.data.reasoningChain
    };
    
    history.unshift(record);
    
    // 只保留最近10条
    if (history.length > 10) {
      history.pop();
    }
    
    wx.setStorageSync('diagnosis_history', history);
    
    wx.showToast({
      title: '保存成功',
      icon: 'success'
    });
  },

  // 开始新的诊断
  startNew() {
    wx.showModal({
      title: '确认',
      content: '确定要开始新的诊断吗？',
      confirmText: '确定',
      confirmColor: '#1a5276',
      success: (res) => {
        if (res.confirm) {
          // 清除本地存储
          wx.removeStorageSync('patient_info');
          wx.removeStorageSync('symptoms');
          wx.removeStorageSync('current_diagnosis');
          
          // 重新设置全局数据
          app.globalData.sessionId = '';
          app.globalData.patientInfo = {};
          app.globalData.symptoms = [];
          app.globalData.currentQuestions = [];
          app.globalData.diagnosisHypothesis = [];
          app.globalData.reasoningChain = '';
          
          // 跳转到首页
          wx.reLaunch({
            url: '/pages/index/index'
          });
        }
      }
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
  }
});
