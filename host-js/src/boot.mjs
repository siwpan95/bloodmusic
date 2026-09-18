/**
 * 宿主启动共用模块（index.mjs / cli.mjs / tests 三方共用，避免启动路径漂移）。
 *
 * 装载模式对齐 cordis 官方 bin.js / players-unified：
 *   1. new Context()（服务容器）
 *   2. ctx.plugin(Loader) 挂上声明式加载能力（ctx.loader）
 *   3. 读 cordis.json，逐条 ctx.loader.create(entry)，await ctx.loader.await()
 * 装载顺序由 inject 依赖拓扑决定，与 entries 声明顺序无关。
 */

import { readFile } from 'node:fs/promises'
import path from 'node:path'
import { pathToFileURL, fileURLToPath } from 'node:url'
import { Context } from 'cordis'
import Loader from '@cordisjs/plugin-loader'
import { attachConsoleLogger } from './logging.mjs'

export const HOST_DIR = fileURLToPath(new URL('..', import.meta.url))

/** 去掉 $note 等合成期元数据键（只进文档，不进 loader） */
function stripMeta(entry) {
  const clean = {}
  for (const [key, value] of Object.entries(entry)) {
    if (!key.startsWith('$')) clean[key] = value
  }
  return clean
}

export async function readConfig(hostDir = HOST_DIR) {
  const file = path.join(hostDir, 'cordis.json')
  return JSON.parse(await readFile(file, 'utf8'))
}

/**
 * 启动宿主。
 * @param {{ hostDir?: string, logLevel?: string, trace?: boolean }} options
 * @returns {Promise<{ ctx: Context, config: object, entries: object[] }>}
 */
export async function bootHost({ hostDir = HOST_DIR, logLevel = 'info', trace = false } = {}) {
  const config = await readConfig(hostDir)

  const ctx = new Context()
  ctx.baseUrl = pathToFileURL(path.join(hostDir, 'cordis.json')).href
  attachConsoleLogger(ctx, { level: trace ? 'debug' : logLevel, color: !process.env.NO_COLOR })
  const loaderFiber = await ctx.plugin(Loader, { baseUrl: ctx.baseUrl })
  if (trace) ctx.loader.enableLogs = true

  for (const entry of config.entries) await ctx.loader.create(stripMeta(entry))
  await ctx.loader.await()
  return { ctx, config, entries: config.entries, loaderFiber }
}

/**
 * 关闭宿主。cordis rc.10 没有 ctx.stop()，根 fiber 的 dispose 语义是「重启」而非关停
 * （见 packages/core/src/fiber.ts：root 分支 `this.dispose = () => this.restart()`）。
 * 正确姿势 = 逆序串行 dispose 顶层条目（Fiber 副作用逆序回收 → Python 子进程被杀），
 * 再 dispose Loader 自身。串行 await 保证清理顺序确定（players-unified 实测结论）。
 */
export async function stopHost(ctx, loaderFiber) {
  const entries = Object.values(ctx.loader?.store ?? {}).reverse()
  for (const entry of entries) {
    try {
      await entry.fiber?.dispose()
    } catch (error) {
      ctx.logger?.warn?.(`条目 ${entry.id} 卸载异常：${error.message}`)
    }
  }
  await loaderFiber?.dispose()
}

/**
 * 收集条目树状态（--dump-config / --check 共用）。
 * 状态码：0 PENDING / 1 LOADING / 2 ACTIVE / 3 FAILED / 4 DISPOSED / 5 UNLOADING
 */
export const FIBER_STATES = ['PENDING', 'LOADING', 'ACTIVE', 'FAILED', 'DISPOSED', 'UNLOADING']

export function collectEntries(loader) {
  const out = []
  const walk = (tree) => {
    for (const entry of Object.values(tree.store)) {
      out.push({
        id: entry.id,
        name: entry.options.name,
        disabled: entry.disabled,
        state: entry.fiber ? FIBER_STATES[entry.fiber.state] : 'NOT_LOADED',
      })
      if (entry.subtree) walk(entry.subtree)
    }
  }
  walk(loader)
  return out
}
