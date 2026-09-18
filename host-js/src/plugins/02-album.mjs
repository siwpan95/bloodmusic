/**
 * 插件：专辑/单曲面 —— `ctx['bloodmusic.album']`。
 *
 * config: { selfCheck?: boolean }
 */

export default {
  name: 'bloodmusic-album',
  inject: ['bloodmusic'],
  apply(ctx, config = {}) {
    const facade = {
      /** 列出可制作风格 → { styles } */
      styles: () => ctx.bloodmusic.albumStyles(),
      /**
       * 快速单曲：{ style?, seed?, bpm?, bars?, out_dir? }
       * → { title, style, bpm, key, bars, seed, duration_sec, output_dir, wav }
       */
      quick: (params = {}) => ctx.bloodmusic.albumQuick(params),
    }
    ctx.provide('bloodmusic.album', facade)

    if (config.selfCheck !== false) {
      Promise.resolve()
        .then(() => ctx.bloodmusic.albumStyles())
        .then(({ styles }) => ctx.emit('bloodmusic/capability-ready', {
          id: 'album', detail: { styles: styles.length },
        }))
        .catch((error) => ctx.logger?.warn?.(`album 自检失败：${error.message}`))
    }
  },
}
