export const DAYS = ['一', '二', '三', '四', '五', '六', '日']
export const CATEGORY = {
  required: '系專業必修', general_base: '通識基礎', professional_elective: '專業選修',
  general_core: '通識核心', general_interest: '通識興趣', pe: '體育', other: '其他',
}
export async function request(path, options = {}) {
  const headers = { Accept: 'application/json', ...(options.body ? { 'Content-Type': 'application/json' } : {}), ...options.headers }
  if (options.method && options.method !== 'GET') {
    const csrf = document.cookie.split('; ').find((part) => part.startsWith('csrftoken='))?.split('=')[1]
    if (csrf) headers['X-CSRFToken'] = decodeURIComponent(csrf)
  }
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), 12000)
  try {
    const response = await fetch(path, { ...options, headers, credentials: 'same-origin', signal: controller.signal })
    const data = await response.json().catch(() => ({}))
    if (!response.ok) throw new Error(data.error || `連線失敗（${response.status}）`)
    return data
  } catch (error) {
    if (error.name === 'AbortError') throw new Error('載入逾時，請確認網路後重試。')
    throw error
  } finally { clearTimeout(timer) }
}

export function slotsText(offering) {
  return (offering?.slots || []).map((slot) => {
    const day = `週${DAYS[slot.day] || ''}`;
    return slot.periods?.length
      ? `${day} ${slot.periods[0]}–${slot.periods.at(-1)}節`
      : `${day} ${slot.start}–${slot.end}`;
  }).join('、');
}
export function periodsFor(slot, periods) {
  if (slot.periods?.length) return slot.periods
  const start = (periods || []).findIndex((p) => p.start === slot.start)
  const end = (periods || []).findIndex((p) => p.end === slot.end)
  return start < 0 || end < 0 ? [] : Array.from({ length: end - start + 1 }, (_, i) => start + i + 1)
}
export function teacherName(offering) { return offering?.teacher?.name || '教師資料待補' }
export function categoryLabel(course) { return CATEGORY[course?.category] || course?.category_label || '其他' }

export function switchIssues(offering, sourceId) {
  const otherConflicts = (offering.conflicts || []).filter(
    (conflict) => conflict.offering_id !== sourceId,
  )
  const restrictions = (offering.unavailable_reasons || []).filter(
    (reason) => !['本學期已選相同課程。', '與既有課表衝堂。', '課程已額滿。', '超過每學期 25 學分上限。'].includes(reason),
  )
  return [
    ...(offering.remaining <= 0 ? ['已額滿'] : []),
    ...restrictions,
    ...(otherConflicts.length
      ? ['與' + [...new Set(otherConflicts.map((item) => item.course))].join('、') + '衝堂']
      : []),
  ]
}
