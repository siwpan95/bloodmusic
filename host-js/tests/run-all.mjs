#!/usr/bin/env node
/**
 * BloodMusic Cordis 宿主 —— 端到端验收套件。
 *
 * 覆盖（全部实跑，不是静态检查）：
 *   1.  声明式装载：cordis.json 5 条目全部 ACTIVE
 *   2.  核心服务 ping（python 版本 / 仓库根）
 *   3.  四个服务面已 provide（bloodmusic.sfx / album / mirror / autowav）
 *   4.  sfx：预设清单 + 渲染 explosion → WAV RIFF 头校验
 *   5.  album：风格清单 + quick 单曲（lofi, bars=4, seed=42）→ WAV 存在
 *   6.  mirror：风格/混音师清单 + remix（bars=4, seed=42）→ song_final.wav 存在
 *   7.  autowav：generate（4s, seed=42）+ speak（SAPI 念白）→ WAV 存在
 *   8.  事件面：渲染期间收到 bloodmusic/progress 的 start/done
 *   9.  inject 响应式实证：禁用核心服务条目 → 依赖插件全部离开 ACTIVE；
 *       重新启用 → 依赖插件自动恢复 ACTIVE 且新 Python 子进程 ping 通
 *   10. Fiber 回收实证：stopHost 后 Python 子进程不存在（无孤儿进程）
 *
 * 用法：node tests/run-all.mjs [--only=<关键词>]
 */

import fs from 'node:fs'
import { bootHost, stopHost, collectEntries } from '../src/boot.mjs'

const only = process.argv.find((a) => a.startsWith('--only='))?.slice(7)

/* ---------- 断言工具 ---------- */
function assert(cond, msg) {
  if (!cond) throw new Error(msg)
}
function assertWav(file, msg) {
  assert(file && fs.existsSync(file), `${msg}：文件不存在 ${file}`)
  const fd = fs.openSync(file, 'r')
  const head = Buffer.alloc(12)
  fs.readSync(fd, head, 0, 12, 0)
  fs.closeSync(fd)
  assert(head.subarray(0, 4).toString() === 'RIFF' && head.subarray(8, 12).toString() === 'WAVE',
    `${msg}：不是合法 RIFF/WAVE（${file}）`)
  assert(fs.statSync(file).size > 1000, `${msg}：文件过小（${fs.statSync(file).size}B）`)
}
function pidAlive(pid) {
  try { process.kill(pid, 0); return true } catch { return false }
}
const sleep = (ms) => new Promise((r) => setTimeout(r, ms))

/* ---------- 测试表 ---------- */
const tests = []
const test = (name, fn) => tests.push({ name, fn })

let ctx, loaderFiber

test('01 声明式装载：5 条目全部 ACTIVE', async () => {
  const entries = collectEntries(ctx.loader)
  assert(entries.length === 5, `条目数 ${entries.length} ≠ 5`)
  const bad = entries.filter((e) => e.state !== 'ACTIVE')
  assert(!bad.length, `非 ACTIVE 条目：${bad.map((e) => `${e.id}[${e.state}]`).join(', ')}`)
})

test('02 核心服务 ping', async () => {
  const pong = await ctx.bloodmusic.ping()
  assert(pong.pong === true, 'pong ≠ true')
  assert(pong.python, '缺 python 版本')
  assert(/audio-generation$/.test(pong.repo), `repo 异常：${pong.repo}`)
})

test('03 四个服务面已 provide', async () => {
  for (const name of ['bloodmusic.sfx', 'bloodmusic.album', 'bloodmusic.mirror', 'bloodmusic.autowav']) {
    assert(ctx[name], `服务面缺失：${name}`)
  }
})

test('04 sfx：清单 + 渲染 WAV 校验', async () => {
  const { presets, count } = await ctx['bloodmusic.sfx'].list()
  assert(count >= 40, `预设数 ${count} < 40`)
  assert(presets.includes('explosion'), '清单缺 explosion')
  const r = await ctx['bloodmusic.sfx'].render('explosion')
  assertWav(r.wav, 'sfx.render')
  assert(r.duration_sec > 0.1, `时长异常：${r.duration_sec}`)
})

test('05 album：风格清单 + quick 单曲', async () => {
  const { styles } = await ctx['bloodmusic.album'].styles()
  assert(styles.length >= 10, `专辑风格数 ${styles.length} < 10`)
  const r = await ctx['bloodmusic.album'].quick({ style: 'lofi', bars: 4, seed: 42 })
  assert(r.style === 'lofi', `风格回显异常：${r.style}`)
  assertWav(r.wav, 'album.quick')
})

test('06 mirror：清单 + remix', async () => {
  const { styles } = await ctx['bloodmusic.mirror'].styles()
  const { mixers } = await ctx['bloodmusic.mirror'].mixers()
  assert(styles.length >= 60, `镜像风格数 ${styles.length} < 60`)
  assert(mixers.length >= 20, `混音师数 ${mixers.length} < 20`)
  const { results } = await ctx['bloodmusic.mirror'].remix({ count: 1, bars: 4, seed: 42, style: 'lofi' })
  assert(results.length === 1, `remix 结果数 ${results.length} ≠ 1`)
  assertWav(results[0].song_path, 'mirror.remix')
})

test('07 autowav：generate + speak', async () => {
  const g = await ctx['bloodmusic.autowav'].generate({ duration: 4, seed: 42 })
  assertWav(g.wav, 'autowav.generate')
  const s = await ctx['bloodmusic.autowav'].speak('血音宿主验收', {})
  assertWav(s.wav, 'autowav.speak')
})

test('08 事件面：progress start/done', async () => {
  const events = []
  const dispose = ctx.on('bloodmusic/progress', (p) => events.push(p))
  await ctx['bloodmusic.sfx'].render('blip_select')
  // 'done' 通知在响应行之后发出（python 侧 finally），等它到达再断言
  const deadline = Date.now() + 3000
  while (!events.some((e) => e.phase === 'done') && Date.now() < deadline) await sleep(50)
  dispose()
  const phases = events.map((e) => e.phase)
  assert(phases.includes('start') && phases.includes('done'),
    `progress 事件不全：${JSON.stringify(events)}`)
})

test('09 inject 响应式：禁用核心服务 → 依赖插件卸载；恢复 → 自动重载', async () => {
  const dependents = ['sfx', 'album', 'mirror', 'autowav']
  const stateOf = (id) => collectEntries(ctx.loader).find((e) => e.id === id)?.state

  await ctx.loader.update('bloodmusic', { disabled: true })
  await ctx.loader.await()
  await sleep(300)
  for (const id of dependents) {
    assert(stateOf(id) !== 'ACTIVE', `禁用核心后 ${id} 仍为 ACTIVE（inject 语义未生效）`)
  }
  assert(ctx.bloodmusic === undefined || ctx.bloodmusic.ready === false,
    '核心服务禁用后仍可访问')

  await ctx.loader.update('bloodmusic', { disabled: false })
  await ctx.loader.await()
  await sleep(500)
  for (const id of dependents) {
    assert(stateOf(id) === 'ACTIVE', `恢复后 ${id} 未回到 ACTIVE：${stateOf(id)}`)
  }
  const pong = await ctx.bloodmusic.ping()
  assert(pong.pong === true, '恢复后 ping 失败')
})

test('10 Fiber 回收：stopHost 后无孤儿 Python 进程', async () => {
  const pid = ctx.bloodmusic.bridge?.pid
  assert(pid, '拿不到 python 子进程 pid')
  assert(pidAlive(pid), `python 子进程 ${pid} 本应在运行`)
  await stopHost(ctx, loaderFiber)
  await sleep(300)
  assert(!pidAlive(pid), `stopHost 后 python 子进程 ${pid} 仍存活（Fiber 回收失效）`)
})

/* ---------- 运行器 ---------- */
async function main() {
  const started = Date.now()
  const booted = await bootHost({ logLevel: 'silent' })
  ctx = booted.ctx
  loaderFiber = booted.loaderFiber

  let pass = 0, fail = 0
  const selected = only ? tests.filter((t) => t.name.includes(only)) : tests
  for (const { name, fn } of selected) {
    const t0 = Date.now()
    try {
      await fn()
      pass++
      process.stdout.write(`✓ ${name}  (${Date.now() - t0}ms)\n`)
    } catch (error) {
      fail++
      process.stdout.write(`✗ ${name}\n    ${error.message}\n`)
    }
  }

  // 套件非正常中断也兜一层：尽量不留孤儿进程
  try { await stopHost(ctx, loaderFiber) } catch { /* 已停则忽略 */ }

  process.stdout.write(`\n${pass} 通过 / ${fail} 失败 / 共 ${selected.length} 项（${Date.now() - started}ms）\n`)
  process.exit(fail ? 1 : 0)
}

main().catch(async (error) => {
  console.error('套件运行失败：', error)
  try { if (ctx) await stopHost(ctx, loaderFiber) } catch { /* ignore */ }
  process.exit(1)
})
