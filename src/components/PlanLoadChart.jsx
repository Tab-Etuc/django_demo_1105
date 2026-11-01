import React from "react";

const YEARS = ["一", "二", "三", "四"];
export const termName = (term) => "大" + YEARS[Math.floor((term - 1) / 2)] + (term % 2 ? "上" : "下");

export function PlanLoadChart({ terms, maxCredits, impact }) {
  const top = Math.max(maxCredits, ...terms.map((term) => term.credits), 1);

  return (
    <section className="plan-load" aria-labelledby="plan-load-title">
      <div className="plan-load-head">
        <h2 id="plan-load-title">各學期學分分布</h2>
        <span>單學期上限 {maxCredits} 學分</span>
      </div>
      <div className="plan-load-bars" role="list" style={{ gridTemplateColumns: `repeat(${terms.length}, minmax(0, 1fr))` }}>
        {terms.map((term) => (
          <div className={"plan-load-item" + (term.credits > maxCredits ? " overloaded" : "") +
            (impact?.changes.some((change) => change.term === term.term) ? " changed" : "")}
            role="listitem" key={term.term} aria-label={termName(term.term) + "：" + term.credits + " 學分"}>
            <strong>{term.credits}</strong>
            <div className="plan-load-track">
              <div style={{ height: (term.credits / top) * 100 + "%" }} />
            </div>
            <span>{termName(term.term).slice(1)}</span>
          </div>
        ))}
      </div>
      {impact && (
        <div className="plan-impact" role="status" aria-live="polite">
          <span className="plan-impact-title">{impact.name} · {impact.action}</span>
          <div>
            {impact.changes.filter((change) => change.before !== change.after).map((change) => (
              <span key={change.term}>
                {termName(change.term)} {change.before} → {change.after} 學分
              </span>
            ))}
          </div>
        </div>
      )}
    </section>
  );
}
