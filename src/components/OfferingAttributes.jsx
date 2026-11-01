import React from "react";

export function OfferingAttributes({ course, offering }) {
  const program = course?.program_label || (course?.program_type === "two_year" ? "二技" : "四技");
  const values = [
    ["學制", program],
    ["系別", course?.department || "未設定"],
    ["年級", offering?.grade_label || (offering?.target_grade ? `${offering.target_grade} 年級` : "不限年級")],
    ["班級", offering?.class_label || "不分班"],
  ];
  return (
    <dl className="offering-attributes">
      {values.map(([label, value]) => (
        <div className="offering-attribute" key={label}>
          <dt>{label}</dt>
          <dd>{value}</dd>
        </div>
      ))}
    </dl>
  );
}
