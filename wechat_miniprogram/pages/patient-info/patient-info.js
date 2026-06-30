// pages/patient-info/patient-info.js
const app = getApp();

Page({
  data: {
    age: '',
    gender: '',
    history: '',
    allergies: ''
  },

  onLoad() {
    // Load saved data if any
    const savedData = wx.getStorageSync('patient_info');
    if (savedData) {
      this.setData(savedData);
    }
  },

  onAgeInput(e) {
    this.setData({ age: e.detail.value });
  },

  onGenderSelect(e) {
    this.setData({ gender: e.currentTarget.dataset.gender });
  },

  selectGender(e) {
    const gender = e.currentTarget.dataset.gender;
    this.setData({ gender });
  },

  onHistoryInput(e) {
    this.setData({ history: e.detail.value });
  },

  onAllergiesInput(e) {
    this.setData({ allergies: e.detail.value });
  },

  // 验证表单
  validate() {
    if (!this.data.age) {
      wx.showToast({
        title: '请输入年龄',
        icon: 'none'
      });
      return false;
    }

    const ageNum = parseInt(this.data.age);
    if (isNaN(ageNum) || ageNum < 0 || ageNum > 150) {
      wx.showToast({
        title: '请输入有效年龄',
        icon: 'none'
      });
      return false;
    }

    if (!this.data.gender) {
      wx.showToast({
        title: '请选择性别',
        icon: 'none'
      });
      return false;
    }

    return true;
  },

  // 下一步：描述症状
  goToSymptoms() {
    if (!this.validate()) return;

    // 保存患者信息到全局
    const patientInfo = {
      age: this.data.age,
      gender: this.data.gender,
      history: this.data.history || '无',
      allergies: this.data.allergies || '无'
    };
    
    app.globalData.patientInfo = patientInfo;
    wx.setStorageSync('patient_info', patientInfo);

    wx.navigateTo({
      url: '/pages/symptoms/symptoms'
    });
  },

  goBack() {
    wx.navigateBack();
  }
});
