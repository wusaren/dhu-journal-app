<template>
  <div class="about">
    <h1>关于期刊管理系统</h1>
    <p>这是一个基于Vue 3 + TypeScript + Element Plus构建的期刊管理应用</p>
    <el-button type="primary" @click="$router.back()">返回首页</el-button>
  </div>
</template>

<script setup lang="ts">
</script>

<style scoped>
.about {
  text-align: center;
  padding: 2rem;
}
</style>