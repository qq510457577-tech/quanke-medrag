// pages/index/index.js
const app = getApp();

Page({
  data: {
    
  },

  onLoad() {
    // Check if user has used before
    const history = wx.getStorageSync('diagnosis_history') || [];
    console.log('历史记录:', history.length);
  },

  // 开始诊断
  startDiagnosis() {
    wx.showModal({
      title: '确认开始',
      content: '即将开始AI智能诊断，请根据提示依次输入患者信息和症状',
      confirmText: '开始',
      confirmColor: '#1a5276',
      success: (res) => {
        if (res.confirm) {
          // 跳转到患者信息页面
          wx.navigateTo({
            url: '/pages/patient-info/patient-info'
          });
        }
      }
    });
  },

  // 查看历史记录
  viewHistory() {
    const history = wx.getStorageSync('diagnosis_history') || [];
    if (history.length === 0) {
      wx.showToast({
        title: '暂无历史记录',
        icon: 'none'
      });
      return;
    }
    
    wx.showActionSheet({
      itemList: history.map((item, index) => {
        return `${item.date} - ${item.symptom}`;
      }),
      success: (res) => {
        const index = res.tapIndex;
        const item = history[index];
        // 可以跳转到详情页或重新加载
        wx.setStorageSync('current_diagnosis', item);
        wx.navigateTo({
          url: '/pages/result/result'
        });
      }
    });
  }
});
