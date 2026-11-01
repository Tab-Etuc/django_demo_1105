import { DAYS } from './course-data.js';

export function previewConflicts(offering, enrollments) {
  if (!offering) return [];
  return enrollments.filter(e => e.offering.id !== offering.id).flatMap(e =>
    (offering.slots || []).flatMap(a => (e.offering.slots || []).flatMap(b => {
      const start = a.start > b.start ? a.start : b.start;
      const end = a.end < b.end ? a.end : b.end;
      return a.day === b.day && start < end
        ? [{ id: e.offering.id, name: e.course.name, text: `週${DAYS[a.day]} ${start}–${end}` }]
        : [];
    })));
}
