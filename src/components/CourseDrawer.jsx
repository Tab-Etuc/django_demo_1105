import React, { useRef, useState, useEffect } from "react";
import {
  Sheet,
  SheetContent,
  SheetTitle,
  SheetDescription,
} from "@/components/ui/sheet";
import { Button } from "@/components/ui/button";
import {
  BookOpen,
  X,
  CircleAlert,
  LoaderCircle,
  CheckCircle2,
  Trash2,
  Plus,
  ArrowLeftRight,
} from "lucide-react";
import { slotsText, teacherName, categoryLabel, switchIssues } from "@/lib/course-data";
import { OfferingAttributes } from "@/components/OfferingAttributes";

export function CourseDrawer({
  drawer,
  setDrawer,
  selectedIds,
  selectedRecords,
  trialIds,
  onAdd,
  onSwitch,
  onRemove,
  fixedIds,
  busy,
}) {
  const origin = useRef(document.activeElement);
  const [open, setOpen] = useState(true);
  const closeTimer = useRef(null);
  useEffect(() => () => clearTimeout(closeTimer.current), []);
  const close = () => {
    setOpen(false);
    closeTimer.current = setTimeout(() => {
      setDrawer((current) => current?.requestId === drawer.requestId ? null : current);
    }, 220);
  };
  const sections = drawer.detail?.offerings || drawer.offerings;
  const active = sections.find((offering) => offering.id === drawer.active?.id) || sections[0];
  const detailOffering =
    drawer.detail?.offerings?.find((o) => o.id === active?.id) || active;
  const syllabus = detailOffering?.syllabus || {};
  const currentRecord = selectedRecords?.find((record) => record.course.id === drawer.course.id && !record.is_assigned);
  const otherSection = currentRecord && active?.id !== currentRecord.offering.id;
  return (
    <Sheet
      open={open}
      onOpenChange={(value) => {
        if (!value) close();
      }}
    >
      <SheetContent
        onCloseAutoFocus={(event) => {
          event.preventDefault();
          origin.current?.focus?.();
        }}
        className="course-drawer"
        showCloseButton={false}
        aria-describedby="course-description"
      >
        <div className="drawer-head">
          <div>
            <span className={`category-tag cat-${drawer.course.category}`}>
              {categoryLabel(drawer.course)}
            </span>
            <span className="course-credits">{drawer.course.credits} 學分</span>
          </div>
          <button
            className="icon-button"
            onClick={close}
            aria-label="關閉課程詳情"
          >
            <X size={20} />
          </button>
        </div>
        <div className="drawer-scroll">
          <SheetTitle>{drawer.course.name}</SheetTitle>
          <p className="drawer-course-code">
            {drawer.course.code} <span>·</span>{" "}
            {active?.semester || "尚無本學期班別"}
          </p>
          <SheetDescription
            id="course-description"
            className="drawer-description"
          >
            {drawer.course.description || "課程簡介尚未提供。"}
          </SheetDescription>
          {sections.length > 1 && <section className="drawer-section">
            <div className="section-heading">
              <h3>其他開課班別</h3>
              <span>{sections.length} 個班別</span>
            </div>
            <div className="section-options">
              {sections.map((offering) => (
                <button
                  className={`section-option ${active?.id === offering.id ? "active" : ""}`}
                  key={offering.id}
                  onClick={() =>
                    setDrawer((old) => ({ ...old, active: offering }))
                  }
                >
                  <span className="section-pill">{offering.class_label || `開課 ${offering.section}`}</span>
                  <span>
                    <strong>{teacherName(offering)}</strong>
                    <small>{slotsText(offering)}</small>
                  </span>
                  <span
                    className={`option-state ${selectedIds.has(offering.id) ? "selected" :
                      currentRecord && offering.id !== currentRecord.offering.id
                        ? (switchIssues(offering, currentRecord.offering.id).length ? "unavailable" : "available")
                        : offering.conflicts?.length ? "conflict" : offering.can_select ? "available" : "unavailable"}`}
                  >
                    {selectedIds.has(offering.id)
                      ? "已正式選上"
                      : currentRecord && offering.id !== currentRecord.offering.id
                        ? (switchIssues(offering, currentRecord.offering.id)[0] || "可換班")
                        : offering.conflicts?.length
                          ? "時段衝突"
                        : !offering.remaining
                          ? "額滿"
                          : offering.can_select
                            ? "可選"
                            : "無法加選"}
                  </span>
                </button>
              ))}
            </div>
          </section>}
          {detailOffering?.conflicts?.length > 0 && !otherSection &&
            !selectedIds.has(detailOffering.id) && (
              <div className="drawer-conflict">
                <CircleAlert size={17} />
                <span>
                  這個班別與{" "}
                  {detailOffering.conflicts
                    .map((item) => item.course || "已選課程")
                    .join("、")}{" "}
                  時段重疊。
                </span>
              </div>
            )}
          {detailOffering && !otherSection &&
            !selectedIds.has(detailOffering.id) &&
            !detailOffering.can_select &&
            !detailOffering.conflicts?.length && (
              <div className="drawer-conflict">
                <CircleAlert size={17} />
                <span>
                  {detailOffering.unavailable_reasons?.join("；") ||
                    "此班別目前無法加選。"}
                </span>
              </div>
            )}
          <section className="drawer-section detail-facts">
            <h3>開課資訊</h3>
            <OfferingAttributes course={drawer.course} offering={detailOffering} />
            <div>
              <span>授課教師</span>
              <strong>{teacherName(detailOffering)}</strong>
            </div>
            <div>
              <span>上課時間</span>
              <strong>{slotsText(detailOffering)}</strong>
            </div>
            <div>
              <span>上課教室</span>
              <strong>
                {detailOffering?.slots
                  ?.map((s) => s.room)
                  .filter(Boolean)
                  .join("、") || "依班別安排"}
              </strong>
            </div>
            <div>
              <span>剩餘名額</span>
              <strong>
                {detailOffering?.remaining ?? "—"} /{" "}
                {detailOffering?.capacity ?? "—"}
              </strong>
            </div>
          </section>
          <section className="drawer-section syllabus">
            <div className="section-heading">
              <h3>
                <BookOpen size={16} />
                課程大綱
              </h3>
              {drawer.loading && <LoaderCircle size={15} className="spin" />}
            </div>
            {drawer.error ? (
              <p className="muted-copy">{drawer.error}</p>
            ) : syllabus.is_demo ? (
              <span className="sample-tag">示範內容</span>
            ) : null}
            {syllabus.summary || drawer.course.description ? (
              <p className="muted-copy">
                {syllabus.summary || drawer.course.description}
              </p>
            ) : (
              <p className="muted-copy">尚未提供授課大綱。</p>
            )}
            {syllabus.objectives?.length > 0 && (
              <>
                <h4>學習目標</h4>
                <ul>
                  {syllabus.objectives.map((objective) => (
                    <li key={objective}>{objective}</li>
                  ))}
                </ul>
              </>
            )}
            {syllabus.weeks?.length > 0 && (
              <>
                <h4>教學進度</h4>
                <ol className="week-list">
                  {syllabus.weeks.map((week, i) => (
                    <li key={`${i}-${week}`}>
                      <span>第 {i + 1} 週</span>
                      {week}
                    </li>
                  ))}
                </ol>
              </>
            )}
            {syllabus.evaluation && (
              <>
                <h4>成績評量</h4>
                <div className="evaluation-list">
                  {Object.entries(syllabus.evaluation).map(([name, value]) => (
                    <span key={name}>
                      {name}
                      <b>{value}%</b>
                    </span>
                  ))}
                </div>
              </>
            )}
            {syllabus.materials && (
              <>
                <h4>教材</h4>
                <p className="muted-copy">{syllabus.materials}</p>
              </>
            )}
          </section>
        </div>
        <div className="drawer-footer">
          {selectedIds.has(active?.id) ? (
            <div className="drawer-enrolled">
              <span className="drawer-confirmed">
                <CheckCircle2 size={17} />
                {fixedIds.has(active?.id) ? "系統預排必修" : "已正式選上"}
              </span>
              {!fixedIds.has(active?.id) && (
                <div className="drawer-enrolled-actions">
                  {currentRecord && sections.length > 1 && (
                    <Button
                      variant="outline"
                      disabled={busy}
                      onClick={() => onSwitch(currentRecord)}
                    >
                      <ArrowLeftRight size={16} />
                      換班
                    </Button>
                  )}
                  <Button
                    variant="outline"
                    disabled={busy}
                    onClick={() => onRemove(active)}
                  >
                    退選課程
                  </Button>
                </div>
              )}
            </div>
          ) : otherSection ? (
            <button
              className="button-primary full-width"
              type="button"
              disabled={busy || !active?.remaining}
              onClick={() => onSwitch(currentRecord, active.id)}
            >
              <ArrowLeftRight size={17} /> 更換至此班別
            </button>
          ) : trialIds.has(active?.id) ? (
            <Button
              variant="outline"
              className="button-secondary full-width"
              disabled={busy}
              onClick={() => onRemove(active)}
            >
              <Trash2 size={16} />
              移除試排
            </Button>
          ) : (
            <button
              className="button-primary full-width"
              disabled={busy || !active?.can_select || !active?.remaining}
              onClick={() => onAdd(active, drawer.course)}
            >
              <Plus size={17} />
              加入試排 <span>{drawer.course.credits} 學分</span>
            </button>
          )}
          <span className="drawer-footnote">
            {otherSection ? "換班前會重新檢查名額與衝堂" : "加選前會再次檢查名額、衝堂與學分上限"}
          </span>
        </div>
      </SheetContent>
    </Sheet>
  );
}
