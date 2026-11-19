<script setup lang="ts">
import { onLaunch } from '@dcloudio/uni-app'

onLaunch(() => {
  // 家属端 H5 启动初始化
})
</script>

<style lang="scss">
page {
  background-color: #f5f7fa;
  color: #101828;
  font-size: 32rpx;
  line-height: 1.5;
  font-family: -apple-system, BlinkMacSystemFont, 'PingFang SC', 'Hiragino Sans GB',
    'Microsoft YaHei', sans-serif;
}

/* 保证全局正文 >= 16px，按钮 >= 48px */
view,
text,
input,
button {
  box-sizing: border-box;
}
</style>
