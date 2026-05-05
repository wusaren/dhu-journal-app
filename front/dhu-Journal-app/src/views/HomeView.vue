<template>
  <div class="home-view">
    <div class="welcome-section">
      <div class="section-title">
        <h2>东华学报编辑与论文检测系统</h2>
        <p>欢迎使用期刊编辑与论文格式检测管理平台</p>
      </div>

      <div class="feature-list">
        <!-- 信息提取模块 -->
        <div class="feature-group">
          <h3 class="group-title">信息提取</h3>
          <div class="feature-item" @click="goTo('/paper-management')">
            <div class="feature-icon" style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);">
              <i class="el-icon-document"></i>
            </div>
            <div class="feature-content">
              <h3>论文管理</h3>
              <p>管理投稿论文，包括查看、编辑、审核等功能</p>
            </div>
          </div>

          <div class="feature-item" @click="goTo('/journal-management')">
            <div class="feature-icon" style="background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);">
              <i class="el-icon-notebook-2"></i>
            </div>
            <div class="feature-content">
              <h3>期刊管理</h3>
              <p>管理期刊信息，包括期号、目录、发布等</p>
            </div>
          </div>

          <div class="feature-item" @click="goTo('/preliminary-review')">
            <div class="feature-icon" style="background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);">
              <i class="el-icon-check"></i>
            </div>
            <div class="feature-content">
              <h3>初审系统</h3>
              <p>进行论文的初步审核和筛选工作</p>
            </div>
          </div>
        </div>

        <!-- 格式检测模块 -->
        <div class="feature-group">
          <h3 class="group-title">格式检测</h3>
          <div class="feature-item" @click="goTo('/master-paper-review')">
            <div class="feature-icon" style="background: linear-gradient(135deg, #43e97b 0%, #38f9d7 100%);">
              <i class="el-icon-document-checked"></i>
            </div>
            <div class="feature-content">
              <h3>硕士论文规范性检测</h3>
              <p>对硕士论文进行格式规范性检测和审核</p>
            </div>
          </div>

          <div class="feature-item" @click="goTo('/operator')">
            <div class="feature-icon" style="background: linear-gradient(135deg, #fa709a 0%, #fee140 100%);">
              <i class="el-icon-s-tools"></i>
            </div>
            <div class="feature-content">
              <h3>批量检测工作台</h3>
              <p>批量检测论文目录，一键生成批注文档和检测报告</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { useRouter } from 'vue-router'

const router = useRouter()

const goTo = (path: string) => {
  router.push(path)
}
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

.section-title {
  padding: 40px 20px 20px;
  text-align: center;
}

.section-title h2 {
  margin: 0 0 10px 0;
  font-size: 2rem;
  font-weight: 600;
  color: #333;
}

.section-title p {
  margin: 0;
  color: #666;
  font-size: 1rem;
}

.feature-list {
  display: flex;
  flex-direction: column;
  gap: 2.5rem;
  width: 100%;
  max-width: 900px;
  margin: 2rem auto 0;
  padding: 0 20px 40px;
}

.feature-group {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.group-title {
  text-align: left;
  font-size: 1rem;
  color: #909399;
  font-weight: 500;
  margin: 0 0 0.5rem 0;
  padding-left: 0.5rem;
  border-left: 3px solid #9c0e0e;
}

.feature-item {
  display: flex;
  align-items: center;
  padding: 1.5rem 2rem;
  background: #f8f9fa;
  border-radius: 12px;
  transition: all 0.3s ease;
  cursor: pointer;
  min-height: 100px;
  text-align: left;
}

.feature-item:hover {
  background: #e9ecef;
  transform: translateX(5px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
}

.feature-icon {
  font-size: 2rem;
  color: white;
  margin-right: 1.5rem;
  min-width: 60px;
  height: 60px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.feature-icon i {
  font-size: 1.8rem;
}

.feature-content h3 {
  color: #333;
  margin: 0 0 0.5rem 0;
  font-size: 1.2rem;
  font-weight: 600;
}

.feature-content p {
  color: #666;
  margin: 0;
  line-height: 1.5;
}
</style>
