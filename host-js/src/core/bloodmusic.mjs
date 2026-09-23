/**
 * `ctx.bloodmusic` —— 宿主核心服务：Python 引擎（BloodMusic）的 RPC 门面。
 *
 * 架构位置：
 *   cordis 插件（inject: ['bloodmusic']）
 *     → ctx.bloodmusic（本服务）
 *       → JsonRpcBridge（stdio 行分隔 JSON-RPC）
 *         → python host-js/python/rpc_server.py（bloodmusic 引擎）
 *
 * Cordis 语义落点：
 * - 服务实例即插件（构造器形态）；[Service.init]() 启动子进程并返回清理函数 ——
 *   Fiber dispose 时 Python 子进程随之被杀，**进程生命周期由框架托管**。
 * - 子进程异常退出 → 所有在途 RPC 失败 + 发出 'bloodmusic/exit' 事件；
 *   依赖本服务的插件可用 inject 响应式语义在服务恢复后自动重载。
 * - Python 侧 'progress' 通知 → 'bloodmusic/progress' 事件（进入 cordis 事件系统）。
 *
 * config: { python?, script?, cwd?, requestTimeoutMs? }
 *   python 默认取环境变量 BLOODMUSIC_PYTHON，再退回 F:\Python314\python.exe（本机
 *   唯一带完整科学栈 + editable bloodmusic 的解释器），最后退回 PATH 里的 python。
 */

import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { Service } from 'cordis'
import { JsonRpcBridge } from './bridge.mjs'

// 本文件在 src/core/ 下：上两级才是 host-js/（踩过：写成 '..' 会指到 src/，python 报 exit code=2）
const HOST_DIR = fileURLToPath(new URL('../..', import.meta.url))

export const name = 'bloodmusic'

function defaultPython() {
  if (process.env.BLOODMUSIC_PYTHON) return process.env.BLOODMUSIC_PYTHON
  // 2026-09-23 去本地化：win32 下优先 PYEXE，其次 PATH 上的 python（原硬编码 F:\Python314\python.exe）
  return process.platform === 'win32' ? (process.env.PYEXE || 'python') : 'python3'
}

export default class BloodmusicService extends Service {
  constructor(ctx, config = {}) {
    super(ctx, 'bloodmusic')
    this.config = {
      python: config.python ?? defaultPython(),
      script: config.script ?? path.join(HOST_DIR, 'python', 'rpc_server.py'),
      cwd: config.cwd ?? path.dirname(HOST_DIR), // 仓库根（bloodmusic 包所在）
      requestTimeoutMs: config.requestTimeoutMs ?? 120_000,
    }
    this.bridge = null
    this.ready = false
  }

  [Service.init]() {
    this._start()
    // Fiber dispose → 杀 Python 子进程（cordis 副作用回收的落点）
    return () => this._stop()
  }

  _start() {
    const bridge = new JsonRpcBridge(this.config).start()
    this.bridge = bridge
    this.ready = true
    bridge.on('notify', (method, params) => {
      if (method === 'progress') this.ctx.emit('bloodmusic/progress', params)
    })
    bridge.on('stderr', (text) => {
      if (text) this.ctx.logger?.debug?.(`[python] ${text}`)
    })
    bridge.on('protocol-error', (line) => {
      this.ctx.logger?.warn?.(`python stdout 出现非协议行：${line.slice(0, 120)}`)
    })
    bridge.on('exit', (error) => {
      this.ready = false
      this.ctx.logger?.warn?.(`python 子进程退出：${error.message}`)
      this.ctx.emit('bloodmusic/exit', { message: error.message })
    })
  }

  async _stop() {
    this.ready = false
    await this.bridge?.stop()
    this.bridge = null
  }

  /** 重启 Python 子进程（验证 inject 响应式 / 运维手动恢复用） */
  async restart() {
    await this._stop()
    this._start()
    return this.ping()
  }

  /** 底层 RPC 出口；timeout 可覆盖（长渲染调大，探活调小） */
  rpc(method, params = {}, opts = {}) {
    if (!this.bridge) return Promise.reject(new Error('bloodmusic 服务未就绪'))
    return this.bridge.request(method, params, { timeout: this.config.requestTimeoutMs, ...opts })
  }

  ping() { return this.rpc('ping', {}, { timeout: 10_000 }) }

  /* ---- sfx 面 ---- */
  sfxList() { return this.rpc('sfx.list') }
  sfxRender(name, params = {}) { return this.rpc('sfx.render', { name, ...params }) }

  /* ---- album 面 ---- */
  albumStyles() { return this.rpc('album.styles') }
  albumQuick(params = {}) { return this.rpc('album.quick', params, { timeout: 600_000 }) }

  /* ---- mirror 面 ---- */
  mirrorStyles() { return this.rpc('mirror.styles') }
  mirrorMixers() { return this.rpc('mirror.mixers') }
  mirrorRemix(params = {}) { return this.rpc('mirror.remix', params, { timeout: 600_000 }) }

  /* ---- autowav 面 ---- */
  autowavGenerate(params = {}) { return this.rpc('autowav.generate', params, { timeout: 600_000 }) }
  autowavSpeak(text, params = {}) { return this.rpc('autowav.speak', { text, ...params }, { timeout: 120_000 }) }
}
