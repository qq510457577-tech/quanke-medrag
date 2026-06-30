// app.js
App({
  globalData: {
    userInfo: null,
    apiBase: 'http://113.45.44.124:10086/api',
    sessionId: '',
    patientInfo: {},
    symptoms: [],
    currentQuestions: [],
    currentQuestionIndex: 0,
    diagnosisHypothesis: [],
    finalDiagnoses: []
  },
  
  onLaunch() {
    // Check login status
    this.checkLoginStatus();
  },
  
  checkLoginStatus() {
    const token = wx.getStorageSync('token');
    if (token) {
      // Verify token validity
    }
  },
  
  // API request wrapper
  request(url, method = 'GET', data = {}) {
    return new Promise((resolve, reject) => {
      wx.request({
        url: `${this.globalData.apiBase}${url}`,
        method: method,
        data: data,
        header: {
          'content-type': 'application/json'
        },
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
})
