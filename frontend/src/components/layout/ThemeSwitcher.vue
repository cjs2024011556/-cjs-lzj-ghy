<template>
  <el-tooltip :content="theme.theme === 'dark' ? '切换到亮色' : '切换到暗色'" placement="bottom">
    <el-button text circle @click="theme.toggle()">
      <el-icon :size="18">
        <Sunny v-if="theme.theme === 'dark'" />
        <Moon v-else />
      </el-icon>
    </el-button>
  </el-tooltip>
</template>

<script setup lang="ts">
import { Sunny, Moon } from '@element-plus/icons-vue'
import { useThemeStore } from '@/stores/theme'

const theme = useThemeStore()
</script>
