import { motion } from "motion/react";
import { spring } from "@animate-ui/react/utils/motion";
import React, { useState } from "react";
import { Plus, GripVertical } from "lucide-react";

export function PlanTerm({ term, busy, onDrop, onRemove, onFail, onRestore, onAdd, onOpen, dragEntry, onDragEntry, maxCredits, maxTerms = 8, failedTermsFor = () => 0, failedTerms = [] }) {
  const [over, setOver] = useState(false);
  const fall = term.term % 2 === 1;
  const grade = Math.ceil(term.term / 2);
  const year = ["一", "二", "三", "四"][grade - 1];

  const alreadyHere = dragEntry && term.courses.some(e => e.course.id === dragEntry.course.id && e.source !== "failed");
  const blocked = dragEntry && (dragEntry.locked || dragEntry.source === "failed" || failedTerms.some(t => term.term <= t));
  const projected = term.credits + (dragEntry && !alreadyHere ? dragEntry.course.credits : 0);
  return (
    <section
      className={`plan-term ${fall ? "fall-term" : "spring-term"} ${over && !blocked ? "drag-over" : ""} ${dragEntry && blocked ? "drop-blocked" : ""}`}
      onDragOver={(event) => {
        if (!blocked && event.dataTransfer.types.includes("application/json")) {
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
        onDragEntry(null);
        if (blocked) return;
        try {
          const entry = JSON.parse(event.dataTransfer.getData("application/json"));
          if (entry.course && entry.source !== "failed") onDrop(entry, term.term);
        } catch {}
      }}
    >
      <div className="term-head">
        <div>
          <strong>{year}年級{fall ? "上" : "下"}</strong>
          <small>第 {term.term} 學期</small>
        </div>
        <span className="term-credit">{term.credits}<small> 學分</small></span>
      </div>
      {dragEntry && <div className={`drop-projection ${blocked ? "blocked" : ""}`} role="status">
        {blocked ? "須排在未通過學期之後" : alreadyHere ? "目前所在學期" : `放入後 ${projected} 學分${projected > maxCredits ? ` · 超出 ${projected - maxCredits} 學分` : ""}`}
      </div>}
      <div className="term-course-list">
        {term.courses.map((entry, index) => (
          <motion.article
            layout="position"
            transition={spring.pop}
            className={`plan-course ${entry.locked ? "locked" : "movable"} ${entry.source === "failed" ? "failed-course" : ""}`}
            key={`${entry.course.id}-${entry.source}-${index}`}
            draggable={!entry.locked && entry.source !== "failed" && !busy}
            onDragEnd={() => {onDragEntry(null); setOver(false);}}
            onDragStart={(event) => {
              if (entry.locked || busy) return;
              onDragEntry(entry);
              event.dataTransfer.effectAllowed = "move";
              event.dataTransfer.setData("application/json", JSON.stringify(entry));
            }}
          >
            <span className={`plan-course-mark ${entry.source === "failed" ? "failed" : entry.course.category === "professional_elective" ? "elective" : "required"}`} />
            <div className="plan-course-copy">
              <span className="plan-course-code">{entry.course.code}</span>
              <button className="course-name-link" onClick={() => onOpen(entry)}>{entry.course.name}</button>
              <span className="plan-course-subline">
                {entry.source === "failed" ? "未通過 · 不計學分" :
                  entry.is_retake ? `重修規劃 · ${entry.course.credits} 學分` :
                  entry.officially_selected ? `已配課 · ${entry.course.credits} 學分` :
                  (entry.is_retake ? "重修 · " : "") + entry.course.credits + " 學分"}
              </span>
            </div>
            {!entry.locked && entry.source !== "failed" ? (
              <div className="plan-course-actions">
                <GripVertical size={13} className="drag-handle" aria-hidden="true" />
                <select
                  className="plan-term-select"
                  aria-label={`將${entry.course.name}移至學期`}
                  title="選擇移動的學期"
                  value={term.term}
                  disabled={busy}
                  onChange={(event) => onDrop(entry, Number(event.target.value))}
                >
                  {Array.from({ length: maxTerms }, (_, i) => i + 1)
                    .filter((value) => value > failedTermsFor(entry.course.id) || value === term.term)
                    .map((value) => <option key={value} value={value}>第 {value} 學期</option>)}
                </select>
                {term.term < 8 && (
                  <button type="button" className="icon-button plan-fail" disabled={busy}
                    title="標記未通過，重修卡可拖到較晚學期"
                    aria-label={`標記${entry.course.name}未通過並安排重修`}
                    onClick={() => onFail(entry, term.term)}>
                    標記未通過
                  </button>
                )}
                {!!entry.id && !entry.is_retake && !(
                  entry.course.recommended_term === term.term &&
                  ["required", "general_base", "pe"].includes(entry.course.category)
                ) && (
                  <button type="button" className="icon-button remove-plan" disabled={busy}
                    title={entry.course.recommended_term && ["required", "general_base", "pe"].includes(entry.course.category) ? "還原建議學期" : "從規劃移除"}
                    aria-label={`${entry.course.recommended_term && ["required", "general_base", "pe"].includes(entry.course.category) ? "還原建議學期：" : "移除規劃："}${entry.course.name}`}
                    onClick={() => onRemove(entry)}>
                    {entry.course.recommended_term && ["required", "general_base", "pe"].includes(entry.course.category) ? "還原建議學期" : "移除規劃"}
                  </button>
                )}
              </div>
            ) : entry.source === "failed" ? (
              <button type="button" className="restore-failed" disabled={busy || entry.can_restore === false} onClick={() => onRestore(entry, term.term)}>{entry.can_restore === false ? "請先取消較晚學期的未通過" : "取消未通過 · 移回此學期"}</button>
            ) : (
              <span className="plan-state">已完成／已選</span>
            )}
          </motion.article>
        ))}
        {!term.courses.length && <div className="term-empty">拖曳課程到這個學期</div>}
      </div>
      <button type="button" className="term-add" onClick={onAdd} disabled={busy}>
        <Plus size={14} /> 加入課程
      </button>
    </section>
  );
}
