/**
 * 插件：SFX/合成面 —— `ctx['bloodmusic.sfx']`。
 *
 * inject: ['bloodmusic'] —— 声明式依赖：核心服务（Python 子进程）未就绪时本插件停在
 * PENDING；服务消失自动卸载、恢复自动重载（cordis inject 响应式语义）。
 * 对象形态导出（name/inject/apply 在一起）—— 函数形态 + 模块级 inject 会被
 * loader 的 unwrapExports 丢弃（players-unified 实测坑，见该项目 src/core/group.mjs 注释）。
 *
 * config: { selfCheck?: boolean } 装载后拉一次预设数做自检（默认开）。
 */

export default {
  name: 'bloodmusic-sfx',
  inject: ['bloodmusic'],
  apply(ctx, config = {}) {
    const facade = {
      /** 列出全部 SFX 预设 → { presets, count } */
      list: () => ctx.bloodmusic.sfxList(),
      /** 渲染一个预设为 WAV → { name, wav, duration_sec, sample_rate, peak } */
      render: (name, params = {}) => ctx.bloodmusic.sfxRender(name, params),
    }
    // provide 是可回收副作用：本插件卸载时 'bloodmusic.sfx' 自动摘除
    ctx.provide('bloodmusic.sfx', facade)

    if (config.selfCheck !== false) {
      Promise.resolve()
        .then(() => ctx.bloodmusic.sfxList())
        .then(({ count }) => ctx.emit('bloodmusic/capability-ready', {
          id: 'sfx', detail: { presets: count },
        }))
        .catch((error) => ctx.logger?.warn?.(`sfx 自检失败：${error.message}`))
    }
  },
}
