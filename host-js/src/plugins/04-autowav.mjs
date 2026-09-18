/**
 * 插件：AutoWav 算法作曲 + 人声面 —— `ctx['bloodmusic.autowav']`。
 *
 * config: { selfCheck?: boolean }（本面无轻量自检调用，默认只发就绪事件）
 */

export default {
  name: 'bloodmusic-autowav',
  inject: ['bloodmusic'],
  apply(ctx, config = {}) {
    const facade = {
      /**
       * 算法作曲：{ duration?, bpm?, scale?, seed?, out? }
       * → { wav, duration_sec, bytes }
       */
      generate: (params = {}) => ctx.bloodmusic.autowavGenerate(params),
      /**
       * SAPI 念白：speak(text, { out?, rate?, volume?, voice? })
       * → { wav, duration_sec, bytes }
       */
      speak: (text, params = {}) => ctx.bloodmusic.autowavSpeak(text, params),
    }
    ctx.provide('bloodmusic.autowav', facade)

    if (config.selfCheck !== false) {
      // 无无副作用的轻量探测方法，直接宣布就绪（真实调用在 --check / tests 里做）
      Promise.resolve().then(() => ctx.emit('bloodmusic/capability-ready', {
        id: 'autowav', detail: { methods: ['generate', 'speak'] },
      }))
    }
  },
}
