import { access, copyFile, mkdir } from 'node:fs/promises'
import { resolve } from 'node:path'

const root = resolve(import.meta.dirname, '..')
const dist = resolve(root, 'dist')

await mkdir(resolve(dist, 'server'), { recursive: true })
await copyFile(resolve(root, 'worker', 'index.js'), resolve(dist, 'server', 'index.js'))

try {
  await access(resolve(root, '.openai', 'hosting.json'))
  await mkdir(resolve(dist, '.openai'), { recursive: true })
  await copyFile(
    resolve(root, '.openai', 'hosting.json'),
    resolve(dist, '.openai', 'hosting.json'),
  )
} catch {
  // Local builds can run before a Sites project has been created.
}
