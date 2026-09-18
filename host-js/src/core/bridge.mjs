/**
 * JSON-RPC stdio 桥 —— Node 宿主 ↔ Python 引擎（bloodmusic）子进程。
 *
 * 协议：行分隔 JSON-RPC 2.0（host-js/python/rpc_server.py 实现）。
 * 生命周期纪律：桥不自己决定生死 —— start/stop 由调用方（BloodmusicService）
 * 挂进 cordis Fiber 的副作用回收链，插件卸载即杀子进程，不留孤儿。
 *
 * 借鉴记账：进程外插件宿主 + 服务面形态借鉴 pluginplayer/host-js（MIT，本仓兄弟项目），
 * 此处协议换成 stdio 行分隔 JSON-RPC（无端口、随进程生灭）。
 */

import { spawn } from 'node:child_process'
import { EventEmitter } from 'node:events'
import readline from 'node:readline'

export class JsonRpcBridge extends EventEmitter {
  /**
   * @param {{ python: string, script: string, cwd: string, env?: object }} options
   */
  constructor(options) {
    super()
    this.options = options
    this.child = null
    this.nextId = 1
    /** @type {Map<number, { resolve, reject, method, timer }>} */
    this.pending = new Map()
    this.stopped = false
  }

  get pid() {
    return this.child?.pid ?? null
  }

  start() {
    if (this.child) throw new Error('bridge 已启动')
    const { python, script, cwd, env } = this.options
    // -u：关掉 stdout 缓冲 —— 协议对时延敏感，且进度通知要即时到达
    this.child = spawn(python, ['-u', script], {
      cwd,
      env: { ...process.env, ...env },
      stdio: ['pipe', 'pipe', 'pipe'],
    })
    this.stopped = false

    const rl = readline.createInterface({ input: this.child.stdout })
    rl.on('line', (line) => this._onLine(line))
    this.child.stderr.on('data', (chunk) => {
      // Python 侧日志（含被拐走的库 print）原样上抛，由宿主日志系统接管
      this.emit('stderr', chunk.toString().trimEnd())
    })
    this.child.on('error', (error) => this._onDeath(error))
    this.child.on('exit', (code, signal) => this._onDeath(
      new Error(`python 子进程退出 code=${code} signal=${signal}`),
    ))
    return this
  }

  _onLine(line) {
    line = line.trim()
    if (!line) return
    let msg
    try {
      msg = JSON.parse(line)
    } catch {
      this.emit('protocol-error', line)
      return
    }
    if (msg.id == null) {
      // 通知（progress 等）
      this.emit('notify', msg.method, msg.params ?? {})
      return
    }
    const slot = this.pending.get(msg.id)
    if (!slot) return // 迟到响应（请求已超时/进程重启过）
    this.pending.delete(msg.id)
    clearTimeout(slot.timer)
    if (msg.error) {
      const error = new Error(msg.error.message)
      error.code = msg.error.code
      error.rpcMethod = slot.method
      slot.reject(error)
    } else {
      slot.resolve(msg.result)
    }
  }

  _onDeath(error) {
    // 进程死了：所有在途请求全部失败，等 inject 语义驱动上层恢复
    for (const slot of this.pending.values()) {
      clearTimeout(slot.timer)
      slot.reject(error)
    }
    this.pending.clear()
    this.child = null
    if (!this.stopped) this.emit('exit', error)
  }

  /**
   * @param {string} method
   * @param {object} [params]
   * @param {{ timeout?: number }} [opts] 默认 120s（专辑/长渲染场景），ping 类调用方自缩短
   */
  request(method, params = {}, { timeout = 120_000 } = {}) {
    if (!this.child) return Promise.reject(new Error('python 子进程未运行'))
    const id = this.nextId++
    const payload = JSON.stringify({ jsonrpc: '2.0', id, method, params })
    return new Promise((resolve, reject) => {
      const timer = setTimeout(() => {
        this.pending.delete(id)
        reject(new Error(`RPC 超时（${timeout}ms）：${method}`))
      }, timeout)
      this.pending.set(id, { resolve, reject, method, timer })
      this.child.stdin.write(payload + '\n')
    })
  }

  async stop({ graceMs = 800 } = {}) {
    this.stopped = true
    const child = this.child
    if (!child) return
    try {
      child.stdin.write(JSON.stringify({ jsonrpc: '2.0', method: 'exit' }) + '\n')
      child.stdin.end()
    } catch { /* 已死则忽略 */ }
    const exited = await new Promise((resolve) => {
      const timer = setTimeout(() => resolve(false), graceMs)
      child.once('exit', () => { clearTimeout(timer); resolve(true) })
    })
    if (!exited) child.kill('SIGKILL')
    this.child = null
  }
}
