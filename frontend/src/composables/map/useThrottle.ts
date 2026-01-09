/**
 * Throttle utility for performance optimization
 */

export function useThrottle() {
  const throttle = <T extends (...args: any[]) => any>(
    func: T,
    limitMs: number
  ): ((...args: Parameters<T>) => void) => {
    let lastRun = 0
    
    return (...args: Parameters<T>) => {
      const now = Date.now()
      if (now - lastRun >= limitMs) {
        lastRun = now
        func(...args)
      }
    }
  }

  return { throttle }
}
