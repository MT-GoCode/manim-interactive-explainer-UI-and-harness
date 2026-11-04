import { readFileSync } from 'fs'
import { join } from 'path'
import { expect, firstLesson, fixture, test } from './app'

test('a checkmark marks the whole row, keeps the current cell and survives a relaunch', async ({
  launch
}, info) => {
  const b = fixture(info.outputDir)
  const app = await launch([b])
  const page = await firstLesson(app)
  const row = page.locator('.cell').nth(1)
  const other = page.locator('.cell').nth(2)
  const slug = (await row.getAttribute('data-slug'))!
  const color = () => row.evaluate((e) => getComputedStyle(e).backgroundColor)
  const before = await color()
  await expect(page.locator('.cell').nth(0)).toHaveClass(/current/)
  await row.locator('.understood-box').click({ force: true })
  await expect(row).toHaveClass(/understood/)
  expect(await color()).not.toBe(before)
  await expect(other).not.toHaveClass(/understood/)
  await expect(page.locator('.cell').nth(0)).toHaveClass(/current/)
  expect(JSON.parse(readFileSync(join(b, 'understood.json'), 'utf8')).cells).toEqual([slug])
  await app.close()

  const again = await firstLesson(await launch([b]))
  const box = again.locator('.cell').nth(1).locator('.understood-box')
  await expect(box).toBeChecked()
  await box.click({ force: true })
  await expect(again.locator('.cell').nth(1)).not.toHaveClass(/understood/)
  expect(JSON.parse(readFileSync(join(b, 'understood.json'), 'utf8')).cells).toEqual([])
})
