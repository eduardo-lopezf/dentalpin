/**
 * How the clinic's home layout reorders and hides widgets (ADR 0043).
 */
import { describe, expect, it } from 'vitest'
import { arrangeEntries } from '../app/composables/useHomeLayout'

const entries = [{ id: 'a.x.one' }, { id: 'a.x.two' }, { id: 'b.x.three' }]
const ids = (list: { id: string }[]) => list.map(e => e.id)

describe('arrangeEntries', () => {
  it('leaves the default order alone without a layout', () => {
    expect(ids(arrangeEntries(entries, null))).toEqual(['a.x.one', 'a.x.two', 'b.x.three'])
  })

  it('drops what is hidden', () => {
    expect(ids(arrangeEntries(entries, { hidden: ['a.x.two'], order: [] })))
      .toEqual(['a.x.one', 'b.x.three'])
  })

  it('follows the stored order', () => {
    const layout = { hidden: [], order: ['b.x.three', 'a.x.one', 'a.x.two'] }
    expect(ids(arrangeEntries(entries, layout))).toEqual(['b.x.three', 'a.x.one', 'a.x.two'])
  })

  it('shows a widget the layout does not know, after the ordered ones', () => {
    // A newly enabled App's widget appears instead of staying invisible.
    const layout = { hidden: [], order: ['a.x.two', 'a.x.one'] }
    expect(ids(arrangeEntries(entries, layout))).toEqual(['a.x.two', 'a.x.one', 'b.x.three'])
  })

  it('ignores ids that no longer exist', () => {
    const layout = { hidden: ['gone.x.old'], order: ['gone.x.old', 'b.x.three'] }
    expect(ids(arrangeEntries(entries, layout))).toEqual(['b.x.three', 'a.x.one', 'a.x.two'])
  })
})
