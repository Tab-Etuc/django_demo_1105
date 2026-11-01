import React, { useRef, useState } from "react";
import { AnimatePresence, motion } from "motion/react";
import { spring } from "@animate-ui/react/utils/motion";
import { LockKeyhole, ArrowDownUp, Check } from "lucide-react";
import { DAYS, periodsFor, slotsText } from "@/lib/course-data";

export function Timetable({ enrollments, periods, onDropCourse, onOpen, selectedTime, onSelectTime, preview, conflictIds = [] }) {
  const [over, setOver] = useState(false);
  const [dragRange, setDragRange] = useState(null);
  const dragRef = useRef(null);
  const times = periods.length ? periods : [];
  const dayCount = Math.max(5, ...(preview ? [...enrollments, preview] : enrollments).flatMap((e) => e.offering.slots.map((s) => s.day + 1)));

  function beginSelection(event, day, period) {
    if (event.pointerType === "mouse" && event.button !== 0) return;
    event.preventDefault();
    const range = { day, start: period, end: period };
    dragRef.current = range;
    setDragRange(range);
    event.currentTarget.closest(".timetable").setPointerCapture(event.pointerId);
  }

  function trackSelection(event) {
    if (!dragRef.current) return;
    const hit = document.elementFromPoint(event.clientX, event.clientY)?.closest(".period-cell");
    if (!hit || Number(hit.dataset.day) !== dragRef.current.day) return;
    const period = Number(hit.dataset.period);
    const range = {
      day: dragRef.current.day,
      start: Math.min(dragRef.current.start, period),
      end: Math.max(dragRef.current.start, period),
    };
    dragRef.current.range = range;
    if (range.start !== dragRange?.start || range.end !== dragRange?.end) setDragRange(range);
  }

  function finishSelection() {
    if (dragRef.current) {
      onSelectTime(dragRef.current.range || dragRange || dragRef.current);
      dragRef.current = null;
      setDragRange(null);
    }
  }

  function cancelSelection() {
    dragRef.current = null;
    setDragRange(null);
  }

  return (
    <div
      className={`timetable-wrap ${over ? "drag-over" : ""}`}
      onDragOver={(event) => {
        if (event.dataTransfer.types.includes("application/json")) {
          event.preventDefault();
          setOver(true);
        }
      }}
      onDragLeave={(event) => {
        if (!event.currentTarget.contains(event.relatedTarget)) setOver(false);
      }}
      onDrop={(event) => {
        event.preventDefault();
        setOver(false);
        try {
          const { offering, course } = JSON.parse(event.dataTransfer.getData("application/json"));
          if (offering && course) onDropCourse(offering, course);
        } catch {}
      }}
    >
      <div className="timetable" aria-label="每週上課時間表"
        onPointerMove={trackSelection}
        onPointerUp={finishSelection}
        onPointerCancel={cancelSelection}
        style={{
          gridTemplateColumns: `38px repeat(${dayCount}, minmax(0, 1fr))`,
          gridTemplateRows: `32px repeat(${times.length}, 48px)`,
        }}
      >
        <div className="time-head">節次</div>
        {DAYS.slice(0, dayCount).map((day, index) => (
          <div key={day} className="day-head" style={{ gridColumn: index + 2, gridRow: 1 }}>
            週{day}
          </div>
        ))}
        {times.map((period, index) => (
          <React.Fragment key={period.number}>
            <div className="period-label" style={{ gridColumn: 1, gridRow: index + 2 }}>
              <strong>{period.number}</strong>
              <small>{period.start?.slice(0, 5)}</small>
            </div>
            {DAYS.slice(0, dayCount).map((day, dayIndex) => {
              const selected = selectedTime?.day === dayIndex &&
                period.number >= selectedTime.start && period.number <= selectedTime.end;
              const dragging = dragRange?.day === dayIndex &&
                period.number >= dragRange.start && period.number <= dragRange.end;
              return (
                <button
                  type="button"
                  key={day}
                  className={`period-cell ${selected ? "time-active" : ""} ${dragging ? "time-dragging" : ""}`}
                  data-day={dayIndex}
                  data-period={period.number}
                  style={{ gridColumn: dayIndex + 2, gridRow: index + 2 }}
                  aria-label={`篩選週${day}第${period.number}節上課的課程`}
                  aria-pressed={Boolean(selected)}
                  title={`點選或拖曳篩選週${day}第${period.number}節`}
                  onPointerDown={(event) => beginSelection(event, dayIndex, period.number)}
                  onClick={(event) => {
                    if (event.detail === 0) onSelectTime({ day: dayIndex, start: period.number, end: period.number });
                  }}
                />
              );
            })}
          </React.Fragment>
        ))}
        {preview && !enrollments.some(e => e.offering.id === preview.offering.id) && preview.offering.slots.map((slot, i) => {
          const numbers = periodsFor(slot, times);
          const first = times.findIndex(p => p.number === numbers[0]);
          return first < 0 ? null : <div key={`preview-${i}`} className={`timetable-preview-block ${enrollments.some(e => e.offering.id !== preview.offering.id && e.offering.slots.some(s => s.day === slot.day && s.periods?.some(n => numbers.includes(n)))) ? "overlapping-preview" : ""}`} style={{gridColumn: slot.day + 2, gridRow: `${first + 2} / span ${numbers.length}`}}><span>預覽</span><strong>{preview.course.name}</strong></div>;
        })}
        <AnimatePresence initial={false}>
          {enrollments.flatMap((item) =>
            (item.offering.slots || []).map((slot, index) => {
              const numbers = periodsFor(slot, times);
              const first = times.findIndex((p) => p.number === numbers[0]);
              if (first < 0) return null;
              return (
                <motion.button
                  layout="position"
                  key={`${item.offering.id}-${index}`}
                  className={`timetable-block ${conflictIds.includes(item.offering.id) ? "conflict-highlight" : ""} ${item.fixed ? "required-block" : item.source === "trial" ? "trial-block" : "enrolled-block"}`}
                  style={{ gridColumn: slot.day + 2, gridRow: `${first + 2} / span ${numbers.length}` }}
                  initial={{ opacity: 0, scale: 0.97 }}
                  animate={{ opacity: 1, scale: 1 }}
                  exit={{ opacity: 0, transition: { duration: 0.15 } }}
                  transition={spring.pop}
                  whileTap={{ scale: 0.97 }}
                  onClick={() => onOpen(item)}
                  aria-label={`查看 ${item.course.name} ${slotsText(item.offering)}課程詳情`}
                >
                  <span className="block-type" title={item.fixed ? "系統預排" : item.source === "trial" ? "試排中" : "已選上"}>
                    {item.fixed ? <LockKeyhole size={15} /> : item.source === "trial" ?
                      <ArrowDownUp size={15} /> : <Check size={15} />}
                    {item.source === "trial" ? "試排中" : null}
                  </span>
                  <strong>{item.course.name}</strong>
                </motion.button>
              );
            }),
          )}
        </AnimatePresence>
      </div>
    </div>
  );
}
