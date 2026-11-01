import test from "node:test";
import assert from "node:assert/strict";
import { switchIssues } from "./course-data.js";

const choice = {
  remaining: 4,
  conflicts: [{ offering_id: 1, course: "目前班別" }],
  unavailable_reasons: [
    "本學期已選相同課程。",
    "與既有課表衝堂。",
    "超過每學期 25 學分上限。",
  ],
};

test("換班會排除原班造成的重複選課與衝堂訊息", () => {
  assert.deepEqual(switchIssues(choice, 1), []);
});

test("換班前顯示真正與其他課程衝堂的原因", () => {
  assert.deepEqual(switchIssues({
    ...choice,
    conflicts: [...choice.conflicts, { offering_id: 3, course: "大學國文" }],
  }, 1), ["與大學國文衝堂"]);
});

test("已額滿的班別不可換", () => {
  assert.deepEqual(switchIssues({ ...choice, remaining: 0 }, 1), ["已額滿"]);
});

test("保留學制與班級資格限制", () => {
  assert.deepEqual(switchIssues({
    ...choice,
    unavailable_reasons: ["此班別限原班學生。"],
  }, 1), ["此班別限原班學生。"]);
});
