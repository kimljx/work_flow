export function sanitizeTableCell(value) {
  return String(value ?? '')
    .replace(/\t/g, ' ')
    .replace(/\r?\n/g, ' ')
}

export function encodeUtf16Le(text) {
  const buffer = new ArrayBuffer((text.length + 1) * 2)
  const view = new Uint16Array(buffer)
  view[0] = 0xfeff
  for (let index = 0; index < text.length; index += 1) {
    view[index + 1] = text.charCodeAt(index)
  }
  return buffer
}

export function formatExportTimestamp(date = new Date()) {
  const pad = (value) => String(value).padStart(2, '0')
  return `${date.getFullYear()}${pad(date.getMonth() + 1)}${pad(date.getDate())}${pad(date.getHours())}${pad(date.getMinutes())}`
}

export function downloadUtf16Table(filename, rows) {
  const content = rows
    .map((row) => row.map((cell) => sanitizeTableCell(cell)).join('\t'))
    .join('\r\n')
  const blob = new Blob([encodeUtf16Le(content)], { type: 'application/vnd.ms-excel;charset=utf-16le' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  link.click()
  URL.revokeObjectURL(url)
}
