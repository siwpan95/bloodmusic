/**
 * 插件：镜像混音面 —— `ctx['bloodmusic.mirror']`。
 *
 * config: { selfCheck?: boolean }
 */

export default {
  name: 'bloodmusic-mirror',
  inject: ['bloodmusic'],
  apply(ctx, config = {}) {
    const facade = {
      /** 65 风格提示词 slug 列表 → { styles } */
      styles: () => ctx.bloodmusic.mirrorStyles(),
      /** 24 混音师签名链 slug 列表 → { mixers } */
      mixers: () => ctx.bloodmusic.mirrorMixers(),
      /**
       * 纯机生成混音：{ count?, seed?, bars?, bpm?, structure?, style?, mixer_style?, out_dir?, fmt? }
       * → { results: [{ song_path, stems, report_path, elapsed_sec }] }
       */
      remix: (params = {}) => ctx.bloodmusic.mirrorRemix(params),
    }
    ctx.provide('bloodmusic.mirror', facade)

    if (config.selfCheck !== false) {
      Promise.resolve()
        .then(() => ctx.bloodmusic.mirrorStyles())
        .then(({ styles }) => ctx.emit('bloodmusic/capability-ready', {
          id: 'mirror', detail: { styles: styles.length },
        }))
        .catch((error) => ctx.logger?.warn?.(`mirror 自检失败：${error.message}`))
    }
  },
}
