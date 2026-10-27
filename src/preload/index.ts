import { contextBridge, ipcRenderer } from 'electron'
import { CH, type Api, type Command } from '../shared/ipc'

const api: Api = {
  init: () => ipcRenderer.invoke(CH.init),
  at: (slug) => ipcRenderer.send(CH.at, slug),
  save: (slug, base, text) => ipcRenderer.invoke(CH.save, slug, base, text),
  openLink: (slug, cell) => ipcRenderer.send(CH.openLink, slug, cell),
  comment: (cell, base, span, text) => ipcRenderer.send(CH.comment, cell, base, span, text),
  resolve: (id) => ipcRenderer.send(CH.resolve, id),
  ping: () => ipcRenderer.send(CH.ping),
  onCommand: (fn) => ipcRenderer.on(CH.command, (_e, c: Command) => fn(c))
}

contextBridge.exposeInMainWorld('api', api)
