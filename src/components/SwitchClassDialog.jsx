import React, { useState } from "react";
import { ArrowLeftRight, Check, CircleAlert, Clock3, LoaderCircle, Users, X } from "lucide-react";
import { Sheet, SheetContent, SheetDescription, SheetTitle } from "@/components/ui/sheet";
import { Button } from "@/components/ui/button";
import { slotsText, teacherName, switchIssues } from "@/lib/course-data";

export function SwitchClassDialog({ current, offerings, initialTargetId, trialCount, busy, onClose, onConfirm }) {
  const alternatives = offerings.filter((item) => item.id !== current.offering.id);
  const [targetId, setTargetId] = useState(
    initialTargetId || alternatives.find((item) => !switchIssues(item, current.offering.id).length)?.id || alternatives[0]?.id,
  );
  const [error, setError] = useState("");
  const target = alternatives.find((item) => item.id === targetId);
  const issues = target ? switchIssues(target, current.offering.id) : ["目前沒有其他班別"];

  async function confirm() {
    if (!target || issues.length || busy) return;
    setError("");
    try {
      await onConfirm(target.id);
    } catch (problem) {
      setError(problem.message || "換班失敗，原班別已保留。");
    }
  }

  return (
    <Sheet open onOpenChange={(isOpen) => { if (!isOpen && !busy) onClose(); }}>
      <SheetContent className="course-drawer switch-drawer" showCloseButton={false} aria-describedby="switch-description">
        <div className="drawer-head">
          <div className="switch-heading-mark"><ArrowLeftRight size={20} /> 更換班別</div>
          <button className="icon-button" type="button" disabled={busy} onClick={onClose} aria-label="關閉換班">
            <X size={20} />
          </button>
        </div>
        <div className="switch-scroll">
          <SheetTitle>{current.course.name}</SheetTitle>
          <SheetDescription id="switch-description">
            比較同一門課的上課時間與名額，確認後才會更換原班別。
          </SheetDescription>

          <section className="switch-current">
            <span className="switch-section-label">目前已選</span>
            <strong>{current.offering.class_label || `開課 ${current.offering.section}`}</strong>
            <span>{teacherName(current.offering)}</span>
            <span className="switch-time"><Clock3 size={15} />{slotsText(current.offering)}</span>
          </section>

          <section className="switch-choices" aria-label="其他開課班別">
            <h3>其他班別</h3>
            {alternatives.map((offering) => {
              const problems = switchIssues(offering, current.offering.id);
              const active = targetId === offering.id;
              return (
                <button
                  key={offering.id}
                  type="button"
                  className={"switch-choice" + (active ? " active" : "")}
                  disabled={busy}
                  aria-pressed={active}
                  onClick={() => { setTargetId(offering.id); setError(""); }}
                >
                  <span className="switch-choice-top">
                    <strong>{offering.class_label || `開課 ${offering.section}`}</strong>
                    <span className={"switch-availability" + (problems.length ? " unavailable" : "")}>
                      {problems.length ? problems[0] : "剩餘 " + offering.remaining + " 名"}
                    </span>
                  </span>
                  <span className="switch-teacher">{teacherName(offering)}</span>
                  <span className="switch-time"><Clock3 size={14} />{slotsText(offering)}</span>
                  {active && <Check size={17} className="switch-choice-check" aria-hidden="true" />}
                </button>
              );
            })}
            {!alternatives.length && <p className="switch-empty">本學期沒有其他開課班別。</p>}
          </section>

          {target && (
            <section className="switch-review">
              <h3>換班確認</h3>
              <div className="switch-review-row">
                <span>原班別</span>
                <strong>{slotsText(current.offering)}</strong>
              </div>
              <div className="switch-review-row">
                <span>新班別</span>
                <strong>{slotsText(target)}</strong>
              </div>
              <div className="switch-review-row">
                <span>學分</span>
                <strong>{current.course.credits} 學分（不變）</strong>
              </div>
            </section>
          )}
          {issues.length > 0 && target && (
            <div className="switch-message" role="status">
              <CircleAlert size={16} />
              <span>{issues.join("；")}</span>
            </div>
          )}
          {trialCount > 0 && (
            <div className="switch-message">
              <Users size={16} />
              <span>目前有 {trialCount} 門尚未確認的試排；換班完成後會清空試排。</span>
            </div>
          )}
          {error && (
            <div className="switch-message error" role="alert">
              <CircleAlert size={16} />
              <span>{error} 原班別保留。</span>
            </div>
          )}
        </div>
        <div className="switch-actions">
          <button type="button" className="button-secondary" onClick={onClose} disabled={busy}>取消</button>
          <Button className="button-primary" type="button" onClick={confirm}
            disabled={busy || !target || issues.length > 0}>
            {busy ? <LoaderCircle size={16} className="spin" /> : <ArrowLeftRight size={16} />}
            確認換班
          </Button>
        </div>
      </SheetContent>
    </Sheet>
  );
}
