import { describe, expect, it } from 'vitest'
import { compact, money, pct, signedMoney } from './format'

describe('format', () => {
  it('formats currency and missing values as N/A', () => {
    expect(money(1234.5)).toBe('$1,234.50')
    expect(money(null)).toBe('N/A')
    expect(money(Number.NaN)).toBe('N/A')
  })
  it('signs money and percentages', () => {
    expect(signedMoney(-12.3)).toBe('−$12.30')
    expect(signedMoney(5)).toBe('+$5.00')
    expect(pct(1.2345)).toBe('+1.23%')
    expect(pct(-0.5, 1)).toBe('−0.5%')
    expect(pct(undefined)).toBe('N/A')
  })
  it('compacts large numbers', () => {
    expect(compact(3.45e12, '$')).toBe('$3.45T')
    expect(compact(52_500_000)).toBe('52.50M')
    expect(compact(950)).toBe('950')
  })
})
