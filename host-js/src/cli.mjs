#!/usr/bin/env node
/**
 * BloodMusic Cordis 宿主 —— 一次性 CLI（门禁 / 调试）。
 *
 * 用法：
 *   node src/cli.mjs --dump-config[=json]      打印实际启动后的插件树
 *   node src/cli.mjs --check                   门禁：启用条目全部 ACTIVE 且核心服务 ping 通
 *   node src/cli.mjs --list-services           列出服务面与自检状态
 *   node src/cli.mjs --call <方法> [json参数]   直接调一次服务面（如 --call sfx.list）
 *   node src/cli.mjs --trace                   打印 loader 装载/卸载日志
 *
 * --call 的方法表（点路径 → ctx 服务面）：
 *   ping · sfx.list · sfx.render · album.styles · album.quick
 *   mirror.styles · mirror.mixers · mirror.remix · autowav.generate · autowav.speak
 */

import { bootHost, stopHost, collectEntries } from './boot.mjs'

function parseArgv(argv) {
  const out = {}
  for (let i = 0; i < argv.length; i++) {
    const arg = argv[i]
    const [key, inline] = arg.includes('=')
      ? [arg.slice(0, arg.indexOf('=')), arg.slice(arg.indexOf('=') + 1)]
      : [arg, undefined]
    switch (key) {
      case '--dump-config': out.dump = inline ?? true; break
      case '--check': out.check = true; break
      case '--list-services': out.listServices = true; break
      case '--call': out.call = inline ?? argv[++i]; out.callParams = argv[++i]; break
      case '--trace': out.trace = true; break
      case '--help': case '-h': out.help = true; break
      default:
        if (arg.startsWith('-')) throw new Error(`无法识别的参数：${arg}`)
    }
  }
  return out
}

const HELP = `BloodMusic Cordis 宿主 CLI

  --dump-config[=json]   打印实际启动后的插件树
  --check                门禁：启用条目全部 ACTIVE + 核心服务 ping 通
  --list-services        列出服务面
  --call <方法> [json]   直接调服务面（ping / sfx.list / sfx.render / album.styles /
                         album.quick / mirror.styles / mirror.mixers / mirror.remix /
                         autowav.generate / autowav.speak）
  --trace                打印 loader 装载/卸载日志
`

/** --call 方法分发表：字符串点路径 → (ctx, params) => Promise */
const CALLS = {
  'ping': (ctx) => ctx.bloodmusic.ping(),
  'sfx.list': (ctx) => ctx['bloodmusic.sfx'].list(),
  'sfx.render': (ctx, p) => ctx['bloodmusic.sfx'].render(p.name, p),
  'album.styles': (ctx) => ctx['bloodmusic.album'].styles(),
  'album.quick': (ctx, p) => ctx['bloodmusic.album'].quick(p),
  'mirror.styles': (ctx) => ctx['bloodmusic.mirror'].styles(),
  'mirror.mixers': (ctx) => ctx['bloodmusic.mirror'].mixers(),
  'mirror.remix': (ctx, p) => ctx['bloodmusic.mirror'].remix(p),
  'autowav.generate': (ctx, p) => ctx['bloodmusic.autowav'].generate(p),
  'autowav.speak': (ctx, p) => ctx['bloodmusic.autowav'].speak(p.text, p),
}

async function main() {
  const args = parseArgv(process.argv.slice(2))
  if (args.help) {
    process.stdout.write(HELP)
    return 0
  }

  // --dump-config=json 要求 stdout 是干净 JSON：日志静默
  const silent = args.dump === 'json'
  const { ctx, loaderFiber } = await bootHost({ logLevel: silent ? 'silent' : 'info', trace: args.trace })
  const codes = []
  const fail = (msg) => { codes.push(1); process.stderr.write(`✗ ${msg}\n`) }

  try {
    /* ---------- --check 门禁 ---------- */
    if (args.check) {
      const entries = collectEntries(ctx.loader)
      let ok = true
      for (const e of entries) {
        if (e.disabled) continue
        if (e.state !== 'ACTIVE') {
          fail(`条目 ${e.id} 状态 ${e.state}（期望 ACTIVE）`)
          ok = false
        }
      }
      try {
        const pong = await ctx.bloodmusic.ping()
        process.stdout.write(`✓ 核心服务 ping 通（python ${pong.python}, pid ${pong.pid}）\n`)
      } catch (error) {
        fail(`核心服务 ping 失败：${error.message}`)
        ok = false
      }
      if (ok) process.stdout.write(`✓ ${entries.filter((e) => !e.disabled).length} 个启用条目全部 ACTIVE\n`)
    }

    /* ---------- --list-services ---------- */
    if (args.listServices) {
      const ready = []
      ctx.on('bloodmusic/capability-ready', ({ id, detail }) => ready.push({ id, detail }))
      await new Promise((resolve) => setTimeout(resolve, 1500)) // 等各自检回报
      process.stdout.write('服务面：\n')
      for (const name of ['bloodmusic', 'bloodmusic.sfx', 'bloodmusic.album', 'bloodmusic.mirror', 'bloodmusic.autowav']) {
        process.stdout.write(`  ${ctx[name] ? '●' : '○'} ${name}\n`)
      }
      for (const { id, detail } of ready) {
        process.stdout.write(`    [自检] ${id} ${JSON.stringify(detail)}\n`)
      }
    }

    /* ---------- --call ---------- */
    if (args.call) {
      const handler = CALLS[args.call]
      if (!handler) throw new Error(`未知方法：${args.call}（可用：${Object.keys(CALLS).join(' / ')}）`)
      const params = args.callParams ? JSON.parse(args.callParams) : {}
      const started = Date.now()
      const result = await handler(ctx, params)
      process.stdout.write(JSON.stringify({ ok: true, elapsed_ms: Date.now() - started, result }, null, 2) + '\n')
    }

    /* ---------- --dump-config（默认动作） ---------- */
    if (args.dump !== undefined || (!args.check && !args.listServices && !args.call)) {
      const entries = collectEntries(ctx.loader)
      if (args.dump === 'json') {
        process.stdout.write(JSON.stringify(entries, null, 2) + '\n')
      } else {
        process.stdout.write('插件树（实际启动后）：\n')
        for (const e of entries) {
          process.stdout.write(`  ${e.disabled ? '○' : '●'} ${e.id} [${e.state}] ${e.name}\n`)
        }
      }
    }
  } finally {
    await stopHost(ctx, loaderFiber) // Fiber 树回收 → Python 子进程被杀
  }
  return codes.length ? 1 : 0
}

main()
  .then((code) => process.exit(code))
  .catch((error) => {
    console.error(error)
    process.exit(1)
  })
