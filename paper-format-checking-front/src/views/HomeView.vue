<!-- src/views/HomeView.vue -->
<template>
  <div class="home-container">
    <div class="selection-container">
      <div class="selection-cards">
        <el-card class="selection-card" shadow="hover" @click="goTo('undergrad')">
          <h3>本科论文格式检测</h3>
          <p>适用于本科生毕业论文的格式自动检测与报告生成。</p>
          <el-button type="primary" class="select-btn" @click.stop="goTo('undergrad')">进入</el-button>
        </el-card>

        <el-card class="selection-card" shadow="hover" @click="goTo('graduate')">
          <h3>研究生论文格式检测</h3>
          <p>适用于硕士/博士论文的更严格格式检测与标注。</p>
          <el-button type="primary" class="select-btn" @click.stop="goTo('graduate')">进入</el-button>
        </el-card>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { useRouter } from 'vue-router'

const router = useRouter()

function goTo(level: string) {
  router.push({ 
    name: 'PreliminaryReview', 
    query: { level } 
  })
}
</script>

<style scoped>
.home-container {
  width: 100%;
  height: 100%;
}

.selection-container {
  padding: 32px;
  max-width: 1200px;
  margin: 0 auto;
}

.selection-cards {
  display: flex;
  flex-direction: column; /* 垂直排列 */
  gap: 28px;
  align-items: center;
}

.selection-card {
  width: 100%;
  max-width: 840px; /* 放大卡片宽度 */
  padding: 28px;
  min-height: 220px; /* 增加高度 */
  cursor: pointer;
  transition: transform 0.3s ease;
}

.selection-card:hover {
  transform: translateY(-5px);
}

.selection-card h3 {
  margin: 0 0 12px 0;
  color: #333;
  font-size: 22px;
}

.selection-card p {
  margin: 0 0 20px 0;
  color: #666;
  line-height: 1.6;
  font-size: 16px;
}

.select-btn {
  margin-top: 12px;
  width: 220px;
  height: 44px;
  color: #ffffff;
  background-color: rgb(163, 15, 15);
  font-size: 16px;
  border-radius: 6px;
}

/* 在更窄屏幕上让按钮自适应宽度 */
@media (max-width: 480px) {
  .select-btn {
    width: 100%;
  }
  .selection-card {
    padding: 20px;
    max-width: 100%;
    min-height: 180px;
  }
  .selection-container {
    padding: 20px;
  }
}
</style>