#!/usr/bin/env node
/**
 * BloodMusic Cordis 宿主 —— 常驻入口。
 *
 * 启动后保持进程存活，打印已装载条目与可用服务面；SIGINT/SIGTERM 时
 * ctx.stop() —— Fiber 树逆序回收，Python 子进程随之被杀。
 *
 * 用法：
 *   node src/index.mjs [--trace]
 */

import { bootHost, collectEntries } from './boot.mjs'

const trace = process.argv.includes('--trace')

async function main() {
  const { ctx, loaderFiber } = await bootHost({ trace })

  const pong = await ctx.bloodmusic.ping()
  const entries = collectEntries(ctx.loader)

  process.stdout.write('BloodMusic Cordis 宿主已启动\n')
  process.stdout.write(`  python: ${pong.python} (pid ${pong.pid})\n`)
  process.stdout.write(`  repo:   ${pong.repo}\n`)
  process.stdout.write('  条目:\n')
  for (const e of entries) {
    process.stdout.write(`    ${e.disabled ? '○' : '●'} ${e.id} [${e.state}] ${e.name}\n`)
  }
  process.stdout.write('  服务面: ctx.bloodmusic / bloodmusic.sfx / bloodmusic.album / bloodmusic.mirror / bloodmusic.autowav\n')
  process.stdout.write('  事件:   bloodmusic/progress · bloodmusic/exit · bloodmusic/capability-ready\n')

  ctx.on('bloodmusic/capability-ready', ({ id, detail }) => {
    process.stdout.write(`  [ready] ${id} ${JSON.stringify(detail)}\n`)
  })

  const shutdown = async (signal) => {
    process.stdout.write(`\n收到 ${signal}，回收 Fiber 树……\n`)
    await stopHost(ctx, loaderFiber)
    process.exit(0)
  }
  process.on('SIGINT', () => shutdown('SIGINT'))
  process.on('SIGTERM', () => shutdown('SIGTERM'))
}

main().catch((error) => {
  console.error('宿主启动失败：', error)
  process.exit(1)
})
