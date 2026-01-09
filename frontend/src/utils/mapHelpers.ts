
import { CAR_SIMULATION, ROUTE_COLORS } from '@/types/constants'
import { memoize } from './performance'

const _generateCarSVG = (bearing: number): string => {
  const size = CAR_SIMULATION.CAR_SIZE
  const center = CAR_SIMULATION.CAR_ANCHOR
  const color = ROUTE_COLORS.CAR
  
  return `<svg width="${size}" height="${size}" viewBox="0 0 ${size} ${size}" xmlns="http://www.w3.org/2000/svg">
    <g transform="rotate(${bearing} ${center} ${center})">
      <path d="M${center} 8 L36 22 L30 22 L${center} 16 L18 22 L12 22 Z" fill="rgba(255,152,0,0.3)" stroke="none"/>
      <path d="M${center} 10 L33 20 L28 20 L${center} 16 L20 20 L15 20 Z" fill="${color}" stroke="#fff" stroke-width="2" stroke-linejoin="round"/>
      <path d="M${center} 12 L30 19 L27 19 L${center} 16.5 L21 19 L18 19 Z" fill="#FFB74D" opacity="0.8"/>
    </g>
  </svg>`
}

export const generateCarSVG = memoize(_generateCarSVG, 360)

const _hexToRgba = (hex: string, alpha: number = 1): string => {
  // Handle #RGB format
  if (hex.length === 4) {
    hex = '#' + hex[1] + hex[1] + hex[2] + hex[2] + hex[3] + hex[3]
  }

  const r = parseInt(hex.slice(1, 3), 16)
  const g = parseInt(hex.slice(3, 5), 16)
  const b = parseInt(hex.slice(5, 7), 16)

  return `rgba(${r}, ${g}, ${b}, ${alpha})`
}

export const hexToRgba = memoize(_hexToRgba, 50)
