
export enum LogLevel {
  DEBUG = 0,
  INFO = 1,
  WARN = 2,
  ERROR = 3,
  NONE = 4,
}

interface LoggerConfig {
  level: LogLevel
  prefix?: string
  timestamp?: boolean
}

class Logger {
  private config: LoggerConfig

  constructor(config: Partial<LoggerConfig> = {}) {
    this.config = {
      level: config.level ?? (import.meta.env.DEV ? LogLevel.DEBUG : LogLevel.INFO),
      prefix: config.prefix ?? '',
      timestamp: config.timestamp ?? true,
    }
  }

  private formatMessage(level: string, message: string, ...args: any[]): string {
    const parts: string[] = []
    
    if (this.config.timestamp) {
      parts.push(new Date().toISOString())
    }
    
    if (this.config.prefix) {
      parts.push(`[${this.config.prefix}]`)
    }
    
    parts.push(`[${level}]`)
    parts.push(message)
    
    return parts.join(' ')
  }

  debug(message: string, ...args: any[]): void {
    if (this.config.level <= LogLevel.DEBUG) {
      console.debug(this.formatMessage('DEBUG', message), ...args)
    }
  }

  info(message: string, ...args: any[]): void {
    if (this.config.level <= LogLevel.INFO) {
      console.info(this.formatMessage('INFO', message), ...args)
    }
  }

  warn(message: string, ...args: any[]): void {
    if (this.config.level <= LogLevel.WARN) {
      console.warn(this.formatMessage('WARN', message), ...args)
    }
  }

  error(message: string, ...args: any[]): void {
    if (this.config.level <= LogLevel.ERROR) {
      console.error(this.formatMessage('ERROR', message), ...args)
    }
  }

  group(label: string, fn: () => void): void {
    if (this.config.level <= LogLevel.DEBUG) {
      console.group(this.formatMessage('GROUP', label))
      fn()
      console.groupEnd()
    } else {
      fn()
    }
  }

  time<T>(label: string, fn: () => T): T {
    if (this.config.level <= LogLevel.DEBUG) {
      const start = performance.now()
      const result = fn()
      const duration = performance.now() - start
      this.debug(`${label} took ${duration.toFixed(2)}ms`)
      return result
    }
    return fn()
  }

  child(prefix: string): Logger {
    return new Logger({
      ...this.config,
      prefix: this.config.prefix ? `${this.config.prefix}:${prefix}` : prefix,
    })
  }

  setLevel(level: LogLevel): void {
    this.config.level = level
  }
}

export const logger = new Logger()
export const mapLogger = logger.child('Map')
export const routeLogger = logger.child('Route')
export const simLogger = logger.child('Simulation')

export { Logger }
