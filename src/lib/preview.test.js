import test from "node:test";
import assert from "node:assert/strict";
import { previewConflicts } from "./preview.js";
import { slotsText } from "./course-data.js";

const record = (id, slot) => ({
  offering: { id, slots: [slot] },
  course: { name: "既有課程" },
});

test("同一節次內，實際時間沒有重疊就不顯示衝堂", () => {
  const existing = record(1, { day: 0, start: "09:10", end: "09:25", periods: [2] });
  const candidate = { id: 2, slots: [{ day: 0, start: "09:30", end: "10:00", periods: [2] }] };
  assert.deepEqual(previewConflicts(candidate, [existing]), []);
});

test("不同節次標記仍依真實時間檢查衝堂", () => {
  const existing = record(1, { day: 0, start: "09:05", end: "09:20", periods: [1, 2] });
  const candidate = { id: 2, slots: [{ day: 0, start: "09:15", end: "09:45", periods: [2] }] };
  assert.deepEqual(previewConflicts(candidate, [existing]), [{
    id: 1, name: "既有課程", text: "週一 09:15–09:20",
  }]);
});

test("午休等非標準節次也能檢查衝堂及顯示時間", () => {
  const existing = record(1, { day: 5, start: "12:05", end: "12:55", periods: [] });
  const candidate = { id: 2, slots: [{ day: 5, start: "12:20", end: "13:10", periods: [] }] };
  assert.equal(previewConflicts(candidate, [existing]).length, 1);
  assert.equal(slotsText(existing.offering), "週六 12:05–12:55");
});

test("碰到課程結束的瞬間不算衝堂", () => {
  const existing = record(1, { day: 0, start: "09:00", end: "10:00", periods: [1, 2] });
  const candidate = { id: 2, slots: [{ day: 0, start: "10:00", end: "11:00", periods: [3] }] };
  assert.deepEqual(previewConflicts(candidate, [existing]), []);
});

test("標準節次仍維持原本的文字格式", () => {
  const offering = { slots: [{ day: 1, start: "08:10", end: "10:00", periods: [1, 2] }] };
  assert.equal(slotsText(offering), "週二 1–2節");
});
