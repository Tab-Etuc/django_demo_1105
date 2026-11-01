import React, { useState } from "react";
import { motion } from "motion/react";
import {
  BookOpen,
  ArrowRight,
  UserRound,
  LockKeyhole,
  Eye,
  EyeOff,
  CircleAlert,
  LoaderCircle,
  CalendarDays,
  GraduationCap,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import ShapeGrid from "@/components/ShapeGrid";
import { spring } from "@animate-ui/react/utils/motion";

export function Login() {
  const data = document.getElementById("root").dataset;
  const [visible, setVisible] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  return (
    <main className="login-page">
      <div className="login-backdrop" aria-hidden="true">
        <ShapeGrid
          shape="hexagon"
          cellSize={58}
          lineWidth={0.85}
          direction="diagonal"
          speed={0.08}
          lineColor="#c9d6e8"
          hoverColor="#5a86bd"
          hoverFillColor="#d8e9fb"
          fillOpacity={0.15}
          tiltX={5}
          tiltY={-4}
          radius={2.3}
          trail={1}
          glow={0.05}
          twinkle={0}
          fade={0.4}
          clickCascade={false}
          opacity={0.28}
          dpr={1}
        />
      </div>
      <a href="/" className="login-brand">
        <GraduationCap size={28} />
        <span>
          大學選課系統<small>課程與修課規劃</small>
        </span>
      </a>
      <div className="login-layout">
        <motion.section className="login-intro" initial={{ opacity: 0, x: -18 }} animate={{ opacity: 1, x: 0 }} transition={{ duration: 0.65, ease: "easeOut" }}>
          <div className="login-symbol">
            <CalendarDays size={48} strokeWidth={1.4} />
          </div>
          <h1>
            本學期選課，
            <br />
            四年修課規劃。
          </h1>
          <div className="login-features">
            <span>
              <CalendarDays size={20} />
              本學期選課
            </span>
            <span>
              <GraduationCap size={22} />
              四年修課規劃
            </span>
          </div>
        </motion.section>
        <motion.section
          className="login-form-panel"
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={spring.pop}
        >
          <h2>登入選課系統</h2>
          <p>使用你的帳號繼續</p>
          <form method="post" onSubmit={() => setSubmitting(true)}>
            <input type="hidden" name="csrfmiddlewaretoken" value={data.csrf} />
            <input type="hidden" name="next" value={data.next || "/"} />
            {data.error && (
              <div className="login-error" role="alert">
                <CircleAlert size={20} />
                <span>帳號或密碼不正確，請重新輸入。</span>
              </div>
            )}
            <label htmlFor="id_username">使用者帳號</label>
            <div className="login-input">
              <UserRound size={20} />
              <input
                id="id_username"
                name="username"
                autoComplete="username"
                defaultValue={data.username || ""}
                required
                autoFocus
                placeholder="輸入帳號"
              />
            </div>
            <label htmlFor="id_password">密碼</label>
            <div className="login-input">
              <LockKeyhole size={20} />
              <input
                id="id_password"
                name="password"
                type={visible ? "text" : "password"}
                autoComplete="current-password"
                required
                placeholder="輸入密碼"
              />
              <button
                type="button"
                aria-label={visible ? "隱藏密碼" : "顯示密碼"}
                aria-pressed={visible}
                onClick={() => setVisible((v) => !v)}
              >
                {visible ? <EyeOff size={20} /> : <Eye size={20} />}
              </button>
            </div>
            <Button
              className="login-submit"
              type="submit"
              disabled={submitting}
            >
              {submitting ? (
                <>
                  <LoaderCircle size={20} className="spin" />
                  登入中
                </>
              ) : (
                <>
                  登入
                  <ArrowRight size={20} />
                </>
              )}
            </Button>
          </form>
          {data.guestEnabled === "true" && (
            <div className="guest-entry">
              <div className="guest-entry-copy">
                <span>示範體驗</span>
                <small>免註冊，使用遊客帳號</small>
              </div>
              <form method="post" action="/accounts/guest/">
                <input type="hidden" name="csrfmiddlewaretoken" value={data.csrf} />
                <input type="hidden" name="next" value={data.next || "/"} />
                <button className="guest-link" type="submit">
                  <UserRound size={17} />
                  遊客登入
                  <ArrowRight size={17} />
                </button>
              </form>
            </div>
          )}
          <div className="login-note">
            <LockKeyhole size={16} />
            僅供課堂示範使用
          </div>
        </motion.section>
      </div>
      <footer className="login-footer">大學選課系統 · 課堂示範</footer>
    </main>
  );
}
