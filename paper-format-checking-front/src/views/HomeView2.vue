<template>
  <div class="home-view">
    <div class="welcome-section">
      <div class="feature-list">
        <div class="feature-item">
          <div class="feature-icon">
            <i class="el-icon-document"></i>
          </div>
          <div class="feature-content">
            <h3>论文管理</h3>
            <p>管理投稿论文，包括查看、编辑、审核等功能</p>
          </div>
        </div>
        
        <div class="feature-item">
          <div class="feature-icon">
            <i class="el-icon-notebook-2"></i>
          </div>
          <div class="feature-content">
            <h3>期刊管理</h3>
            <p>管理期刊信息，包括期号、目录、发布等</p>
          </div>
        </div>
        
        <div class="feature-item">
          <div class="feature-icon">
            <i class="el-icon-check"></i>
          </div>
          <div class="feature-content">
            <h3>初审系统</h3>
            <p>进行论文的初步审核和筛选工作</p>
          </div>
        </div>
      </div>

     
    </div>
  </div>
</template>

<script setup lang="ts">
</script>

<style scoped>
.home-view {
  padding: 0;
  width: 100%;
  height: 100%;
  box-sizing: border-box;
}

.welcome-section {
  text-align: center;
  width: 100%;
  max-width: none;
  margin: 0;
}

.title-with-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 1rem;
  margin-bottom: 1rem;
}



.welcome-section h1 {
  color: #333;
  margin: 0;
  font-size: 2.5rem;
  font-weight: 600;
}

.subtitle {
  color: #666;
  font-size: 1.2rem;
  margin-bottom: 3rem;
}

.feature-list {
  display: flex;
  flex-direction: column;
  gap: 2rem;
  width: 100%;
  max-width: 900px;
  margin: 3rem auto 0;
}

.feature-item {
  display: flex;
  align-items: center;
  padding: 2.5rem;
  background: #f8f9fa;
  border-radius: 16px;
  transition: all 0.3s ease;
  cursor: pointer;
  min-height: 120px;
}

.feature-item:hover {
  background: #e9ecef;
  transform: translateX(5px);
}

.feature-icon {
  font-size: 2.5rem;
  color: #667eea;
  margin-right: 1.5rem;
  min-width: 60px;
  text-align: center;
}

.feature-content h3 {
  color: #333;
  margin: 0 0 0.5rem 0;
  font-size: 1.3rem;
  font-weight: 600;
}

.feature-content p {
  color: #666;
  margin: 0;
  line-height: 1.5;
}

.quick-stats {
  background: #f8f9fa;
  padding: 2rem;
  border-radius: 12px;
  margin-top: 2rem;
}

.quick-stats :deep(.el-statistic__head) {
  font-size: 1rem;
  color: #666;
  margin-bottom: 0.5rem;
}

.quick-stats :deep(.el-statistic__number) {
  font-size: 2rem;
  font-weight: 600;
  color: #333;
}
</style>
