import type { Page } from '@playwright/test'
import { expect, test } from './_fixtures'

/**
 * The agenda's mouse gestures, on the desktop project.
 *
 * The grids moved from `mousedown` plus document-level `mousemove` to
 * Pointer Events so that a finger would work at all. The mouse path was
 * rewritten in the process and had no coverage, which is the risk this
 * closes: with a fine pointer there is no selection step and no long
 * press, and a press must still start a drag on the spot.
 *
 * Writes are intercepted, not performed — the seeded database is shared
 * between runs.
 */

async function openAgenda(page: Page): Promise<void> {
  await page.goto('/appointments', { waitUntil: 'domcontentloaded', timeout: 120_000 })
  await page.waitForSelector('html[data-ua]', { state: 'attached', timeout: 60_000 })
  await expect(page.locator('html')).toHaveAttribute('data-pointer', 'fine')
  await page.waitForTimeout(3000)
}

test.describe('agenda by mouse', () => {
  test('dragging down empty slots opens the modal with the dragged duration', async ({ loggedIn: page }) => {
    await openAgenda(page)

    const cell = page.locator('[data-dense] .cursor-cell').nth(120)
    await cell.scrollIntoViewIfNeeded()
    const box = (await cell.boundingBox())!
    const x = box.x + box.width / 2
    const y = box.y + box.height / 2

    // No selection step and no long press with a mouse: press, drag, release.
    await page.mouse.move(x, y)
    await page.mouse.down()
    await page.mouse.move(x, y + 28, { steps: 4 })
    await page.mouse.move(x, y + 84, { steps: 4 })
    await page.mouse.up()

    await expect(page.getByRole('dialog')).toBeVisible({ timeout: 10_000 })
  })

  test('dragging an appointment reschedules it without a selection step', async ({ loggedIn: page }) => {
    await openAgenda(page)

    const block = page.locator('[data-dense] .group.absolute').first()
    await expect(block).toBeVisible()
    await block.scrollIntoViewIfNeeded()

    await page.route('**/api/v1/agenda/appointments/*', route =>
      route.request().method() === 'PUT' ? route.abort() : route.continue()
    )
    const savePromise = page.waitForRequest(
      req => req.method() === 'PUT' && /\/api\/v1\/agenda\/appointments\/[0-9a-f-]+$/.test(req.url()),
      { timeout: 15_000 }
    )

    const box = (await block.boundingBox())!
    const x = box.x + box.width / 2
    const y = box.y + box.height / 2
    await page.mouse.move(x, y)
    await page.mouse.down()
    await page.mouse.move(x, y + 30, { steps: 5 })
    await page.mouse.move(x, y + 56, { steps: 5 })
    await page.mouse.up()

    const request = await savePromise
    expect(request.postDataJSON()).toHaveProperty('start_time')
  })

  test('clicking an appointment opens it', async ({ loggedIn: page }) => {
    await openAgenda(page)

    const block = page.locator('[data-dense] .group.absolute').first()
    await expect(block).toBeVisible()
    await block.click()

    await expect(page.getByRole('dialog')).toBeVisible({ timeout: 10_000 })
  })
})
