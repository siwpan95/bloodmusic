/**
 * 把 cordis 的日志接到进程 stdout/stderr 上。
 *
 * 借鉴记账：实现照搬 players-unified/host/src/logging.mjs（MIT，本机兄弟项目）。
 * 为什么必须有：cordis 的 ctx.logger 默认**没有 exporter**，loader 的失败路径
 * （插件 import 失败、apply 抛异常）几乎全走 ctx.logger.error —— 不接日志就是
 * 「条目静默不生效」。error/warn 走 stderr，其余走 stdout，保持 --dump-config 可管道。
 */

import { Logger } from 'cordis'

const LEVELS = { error: 0, warn: 1, info: 2, debug: 3 }

/**
 * @param {Context} ctx
 * @param {{level?: 'error'|'warn'|'info'|'debug'|'silent', color?: boolean}} options
 *   level='silent' 时不接 exporter（测试用它挡掉正常噪音，只留断言输出）。
 */
export function attachConsoleLogger(ctx, { level = 'info', color = false } = {}) {
  if (level === 'silent') return null
  const exporter = {
    colors: color ? undefined : false,
    maxLength: 400,
    levels: { ...LEVELS, [level]: 3 },
    export(message) {
      const line = Logger.format(exporter, message)
      const stream = message.level <= LEVELS.warn ? process.stderr : process.stdout
      stream.write(line + '\n')
    },
  }
  return ctx.logger.exporter(exporter)
}
