// Preloaded into main with `electron -r`: error boxes are recorded instead of shown,
// so a test can see startup errors that fire before it can evaluate anything.
const { dialog } = require('electron')
globalThis.errorBoxes = []
dialog.showErrorBox = (title, message) => globalThis.errorBoxes.push({ title, message })
