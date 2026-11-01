import { previewConflicts } from "@/lib/preview";
import { FilterSelect } from "@/components/FilterSelect";
import React, {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { AnimatePresence, motion } from "motion/react";
import { Timetable } from "@/components/Timetable";
import { CourseDrawer } from "@/components/CourseDrawer";
import { PlanTerm } from "@/components/PlanTerm";
import { PlanLoadChart } from "@/components/PlanLoadChart";
import { SwitchClassDialog } from "@/components/SwitchClassDialog";
import { OfferingAttributes } from "@/components/OfferingAttributes";
import {
  DAYS,
  request,
  slotsText,
  teacherName,
  categoryLabel,
} from "@/lib/course-data";
import { Button } from "@/components/ui/button";
import {
  ArrowDownUp,
  PanelLeftClose,
  PanelLeftOpen,
  ArrowLeftRight,
  ArrowRight,
  BookOpen,
  CalendarDays,
  Check,
  CheckCircle2,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  CircleAlert,
  Clock3,
  GraduationCap,
  LayoutGrid,
  LoaderCircle,
  LockKeyhole,
  LogOut,
  Plus,
  Search,
  SlidersHorizontal,
  Sparkles,
  Trash2,
  UserRound,
  X,
} from "lucide-react";
function App() {
  const [user] = useState(
    document.getElementById("root")?.dataset.user || "同學",
  );
  const [page, setPage] = useState(
    location.pathname.startsWith("/plans") ? "plans" : "courses",
  );
  const [sidebarCollapsed, setSidebarCollapsed] = useState(() => {
    try { return localStorage.getItem("sidebar-collapsed") === "true"; } catch { return false; }
  });
  function toggleSidebar() {
    setSidebarCollapsed(value => {
      try { localStorage.setItem("sidebar-collapsed", String(!value)); } catch {}
      return !value;
    });
  }
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState("");
  const [profile, setProfile] = useState(null);
  const [courses, setCourses] = useState([]);
  const [periods, setPeriods] = useState([]);
  const [selected, setSelected] = useState([]);
  const [trial, setTrial] = useState([]);
  const [query, setQuery] = useState("");
  const [category, setCategory] = useState("all");
  const [day, setDay] = useState("all");
  const [credits, setCredits] = useState("all");
  const [programType, setProgramType] = useState("all");
  const [department, setDepartment] = useState("all");
  const [grade, setGrade] = useState("all");
  const [section, setSection] = useState("all");
  const [noConflictOnly, setNoConflictOnly] = useState(false);
  const [availableOnly, setAvailableOnly] = useState(false);
  const [drawer, setDrawer] = useState(null);
  const [notice, setNotice] = useState(null);
  const [plan, setPlan] = useState(null);
  const [planBusy, setPlanBusy] = useState(false);
  const [planPicker, setPlanPicker] = useState(null);
  const [dropTarget, setDropTarget] = useState(null);
  const [switchSource, setSwitchSource] = useState(null);
  const [planImpact, setPlanImpact] = useState(null);
  const [mobileTab, setMobileTab] = useState("list");
  const [busy, setBusy] = useState(false);
  const [planError, setPlanError] = useState("");
  const [preview, setPreview] = useState(null);
  const [generalArea, setGeneralArea] = useState("all");
  const [draggedPlan, setDraggedPlan] = useState(null);
  const [selectedTime, setSelectedTime] = useState(null);
  const mutationRef = useRef(false);
  const detailRequest = useRef(0);
  const refreshRequest = useRef(0);

  const refresh = useCallback(async () => {
    const requestId = ++refreshRequest.current;
    setLoading(true);
    setLoadError("");
    try {
      const [me, catalog, periodData] = await Promise.all([
        request("/api/me/"),
        request("/api/courses/"),
        request("/api/periods/"),
      ]);
      if (requestId !== refreshRequest.current) return;
      setProfile(me);
      setCourses(catalog.courses || []);
      setPeriods(periodData.periods || []);
      setSelected(me.enrollments || []);
      setTrial([]);
      setPlan(null);
      setPlanImpact(null);
    } catch (error) {
      if (requestId === refreshRequest.current) setLoadError(error.message);
    } finally {
      if (requestId === refreshRequest.current) setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);
  useEffect(() => {
    if (page === "plans" && !plan)
      request("/api/plan/")
        .then(setPlan)
        .catch((error) => setPlanError(error.message));
  }, [page, plan]);
  useEffect(() => {
    const shortcut = (event) => {
      if (
        event.key === "/" &&
        !["INPUT", "TEXTAREA", "SELECT"].includes(
          document.activeElement?.tagName,
        ) &&
        !drawer
      ) {
        event.preventDefault();
        setMobileTab("list");
        requestAnimationFrame(() =>
          document.querySelector(".search-box input")?.focus(),
        );
      }
    };
    addEventListener("keydown", shortcut);
    return () => removeEventListener("keydown", shortcut);
  }, [drawer]);
  useEffect(() => {
    if (!notice) return undefined;
    const timer = setTimeout(() => setNotice(null), 4200);
    return () => clearTimeout(timer);
  }, [notice]);
  useEffect(() => {
    const onPop = () =>
      setPage(location.pathname.startsWith("/plans") ? "plans" : "courses");
    addEventListener("popstate", onPop);
    return () => removeEventListener("popstate", onPop);
  }, []);

  const confirmedIds = useMemo(
    () => new Set(selected.map((entry) => entry.offering.id)),
    [selected],
  );
  const trialIds = useMemo(
    () => new Set(trial.map((item) => item.id)),
    [trial],
  );
  const confirmedCredits =
    profile?.credits?.confirmed ??
    selected.reduce((sum, item) => sum + item.course.credits, 0);
  const trialCredits = trial.reduce(
    (sum, item) => sum + item.course.credits,
    confirmedCredits,
  );
  const departments = useMemo(
    () => [...new Set(courses.map(({ course }) => course.department).filter(Boolean))].sort(),
    [courses],
  );
  const filtered = useMemo(
    () =>
      courses
        .flatMap(({ course, offerings }) => {
          const term = query.trim().toLocaleLowerCase();
          if (
            (category !== "all" &&
              (category === "general"
                ? !["general_base", "general_core", "general_interest"].includes(course.category)
                : course.category !== category)) ||
            (generalArea !== "all" && course.general_area !== generalArea) ||
            (programType !== "all" && course.program_type !== programType) ||
            (department !== "all" && course.department !== department) ||
            (credits !== "all" && String(course.credits) !== credits)
          ) return [];
          return offerings.filter((offering) =>
            (day === "all" || offering.slots.some((slot) => String(slot.day) === day)) &&
            (section === "all" ||
              (section === "unassigned"
                ? !offering.class_label
                : offering.class_label === section)) &&
            (grade === "all" || (offering.target_grade
              ? offering.target_grade === Number(grade)
              : offering.min_grade <= Number(grade) && offering.max_grade >= Number(grade))) &&
            (!availableOnly || (offering.can_select && offering.remaining > 0)) &&
            (!noConflictOnly || !offering.conflicts?.length) &&
            (!selectedTime || offering.slots.some((slot) =>
              slot.day === selectedTime.day &&
              slot.periods?.some((number) => number >= selectedTime.start && number <= selectedTime.end)
            )) &&
            (!term || `${course.name} ${course.code} ${course.department} ${teacherName(offering)}`
              .toLocaleLowerCase().includes(term))
          ).map((offering) => ({ course, offering, offerings }));
        })
        .sort((a, b) => {
          const order = (item) => item.offering.can_select && item.offering.remaining > 0
            ? 0 : confirmedIds.has(item.offering.id) ? 1 : 2;
          return order(a) - order(b);
        }),
    [courses, query, category, generalArea, programType, department, grade, section, day,
     credits, availableOnly, noConflictOnly, selectedTime, confirmedIds],
  );

  function navigate(next) {
    const path = next === "plans" ? "/plans/" : "/";
    history.pushState({}, "", path);
    setPage(next);
    setMobileTab(next === "plans" ? "list" : mobileTab);
    window.scrollTo({ top: 0, behavior: "smooth" });
  }
  async function openCourse(item, offering = item.offerings[0]) {
    const requestId = ++detailRequest.current;
    setDrawer({
      requestId,
      course: item.course,
      offerings: item.offerings,
      active: offering,
      loading: true,
      detail: null,
    });
    try {
      const detail = await request(`/api/courses/${item.course.id}/`);
      setDrawer((old) =>
        old && requestId === detailRequest.current
          ? { ...old, loading: false, detail }
          : old,
      );
    } catch (error) {
      setDrawer((old) =>
        old && requestId === detailRequest.current
          ? { ...old, loading: false, error: error.message }
          : old,
      );
    }
  }
  async function addTrial(offering, course) {
    if (!offering || mutationRef.current) return;
    if (confirmedIds.has(offering.id)) {
      setNotice({ text: "這個班別已正式選上。", type: "info" });
      return;
    }
    if (trialIds.has(offering.id)) return;
    mutationRef.current = true;
    setBusy(true);
    const next = [
      ...new Map(
        [...trial, { ...offering, course }].map((item) => [item.id, item]),
      ).values(),
    ];
    try {
      const result = await request("/api/preview/", {
        method: "POST",
        body: JSON.stringify({ offering_ids: next.map((item) => item.id) }),
      });
      if (!result.ok) {
        const conflict = result.errors?.[0];
        setNotice({
          type: "error",
          text: conflict?.reasons?.join("；") || "這個班別目前無法加入試排。",
        });
        return;
      }
      setTrial(next);
      setNotice({ type: "success", text: `已加入試排：${course.name}` });
    } catch (error) {
      setNotice({ type: "error", text: error.message });
    } finally {
      mutationRef.current = false;
      setBusy(false);
    }
  }
  async function confirmTrial() {
    if (!trial.length) return;
    setBusy(true);
    try {
      await request("/api/enrollments/", {
        method: "POST",
        body: JSON.stringify({ offering_ids: trial.map((item) => item.id) }),
      });
      setNotice({ type: "success", text: "加選成功，課表已更新。" });
      setDrawer(null);
      await refresh();
    } catch (error) {
      setNotice({ type: "error", text: error.message });
    } finally {
      setBusy(false);
    }
  }
  async function dropOffering(offeringId) {
    setBusy(true);
    try {
      await request("/api/enrollments/drop/", {
        method: "POST",
        body: JSON.stringify({ offering_id: offeringId }),
      });
      setNotice({ type: "success", text: "已退選，課表已更新。" });
      await refresh();
    } catch (error) {
      setNotice({ type: "error", text: error.message });
    } finally {
      setBusy(false);
    }
  }
  async function openSwitch(item, initialTargetId) {
    if (busy) return;
    setBusy(true);
    try {
      const [me, catalog] = await Promise.all([
        request("/api/me/"),
        request("/api/courses/"),
      ]);
      const record = (me.enrollments || []).find(
        (row) => row.offering.id === item.offering.id && !row.is_assigned,
      );
      const course = (catalog.courses || []).find(
        (row) => row.course.id === item.course.id,
      );
      setProfile(me);
      setSelected(me.enrollments || []);
      setCourses(catalog.courses || []);
      if (!record || !course) throw new Error("課程資料已更新，請重新開啟換班。");
      setSwitchSource({
        current: { course: record.course, offering: record.offering },
        offerings: course.offerings,
        initialTargetId,
      });
    } catch (error) {
      setNotice({ type: "error", text: error.message });
    } finally {
      setBusy(false);
    }
  }

  async function switchOffering(targetId) {
    if (!switchSource || busy) return;
    setBusy(true);
    try {
      await request("/api/enrollments/switch/", {
        method: "POST",
        body: JSON.stringify({
          from_offering_id: switchSource.current.offering.id,
          to_offering_id: targetId,
        }),
      });
      setSwitchSource(null);
      await refresh();
      setNotice({ type: "success", text: "換班完成，課表已更新。" });
    } catch (error) {
      throw error;
    } finally {
      setBusy(false);
    }
  }

  function recordPlanImpact(before, after, name, action, termNumbers) {
    const changes = [...new Set(termNumbers)].filter(Boolean).map((term) => ({
      term,
      before: before?.terms[term - 1]?.credits ?? 0,
      after: after.terms[term - 1]?.credits ?? 0,
    }));
    setPlanImpact({ name, action, changes });
  }

  async function savePlanMove(item, term) {
    if (item.locked || planBusy) return;
    const oldTerm = plan?.terms.find((entry) =>
      entry.courses.some((course) => course.course.id === item.course.id && course.source !== "failed")
    )?.term;
    if (oldTerm === term) return;
    setPlanBusy(true);
    try {
      const updated = await request(item.id ? `/api/plan/courses/${item.id}/` : "/api/plan/courses/", {
        method: item.id ? "PATCH" : "POST",
        body: JSON.stringify({
          version: plan.version, term,
          ...(!item.id && { course_id: item.course.id }),
        }),
      });
      recordPlanImpact(plan, updated, item.course.name, "已移動", [oldTerm, term]);
      setPlan(updated);
      setNotice({ type: "success", text: `已移至第 ${term} 學期` });
    } catch (error) {
      setNotice({ type: "error", text: error.message });
      setPlan(await request("/api/plan/").catch(() => plan));
    } finally {
      setPlanBusy(false);
    }
  }
  async function markPlanFailed(entry, term) {
    if (planBusy || term === 8) return;
    if (!window.confirm(`將「${entry.course.name}」標記為未通過？重修卡暫放第 ${term + 1} 學期，可再拖到大四等較晚學期。這只更新規劃，不代表該學期有開課，也不會更動正式選課。`)) return;
    setPlanBusy(true);
    try {
      const updated = await request("/api/plan/failed/", {
        method: "POST",
        body: JSON.stringify({
          course_id: entry.course.id, term, retake_term: term + 1, version: plan.version,
        }),
      });
      recordPlanImpact(plan, updated, entry.course.name, "已安排重修", [term, term + 1]);
      setPlan(updated);
      setNotice({ type: "info", text: `${entry.course.name}已標記未通過，可將重修卡拖到較晚學期。` });
    } catch (error) {
      setNotice({ type: "error", text: error.message });
      setPlan(await request("/api/plan/").catch(() => plan));
    } finally {
      setPlanBusy(false);
    }
  }
  async function restorePlanFailed(entry, term) {
    if (planBusy) return;
    setPlanBusy(true);
    try {
      const updated = await request("/api/plan/failed/restore/", {
        method: "DELETE",
        body: JSON.stringify({ course_id: entry.course.id, term, version: plan.version }),
      });
      setPlan(updated);
      setNotice({ type: "success", text: `已取消未通過，${entry.course.name}已回到第 ${term} 學期。` });
    } catch (error) {
      setNotice({ type: "error", text: error.message });
      setPlan(await request("/api/plan/").catch(() => plan));
    } finally { setPlanBusy(false); }
  }
  async function addPlanCourse(course, term) {
    setPlanBusy(true);
    try {
      const updated = await request("/api/plan/courses/", {
        method: "POST",
        body: JSON.stringify({
          version: plan.version,
          course_id: course.id,
          term,
        }),
      });
      recordPlanImpact(plan, updated, course.name, "已加入規劃", [term]);
      setPlan(updated);
      setPlanPicker(null);
      setNotice({ type: "success", text: `已排入第 ${term} 學期` });
    } catch (error) {
      setNotice({ type: "error", text: error.message });
    } finally {
      setPlanBusy(false);
    }
  }
  async function removePlanCourse(item) {
    setPlanBusy(true);
    try {
      const beforeTerm = plan.terms.find((term) => term.courses.some((entry) => entry.course.id === item.course.id && entry.source !== "failed"))?.term;
      const updated = await request(`/api/plan/courses/${item.id}/`, {
        method: "DELETE",
        body: JSON.stringify({ version: plan.version }),
      });
      const afterTerm = updated.terms.find((term) => term.courses.some((entry) => entry.course.id === item.course.id && entry.source !== "failed"))?.term;
      recordPlanImpact(plan, updated, item.course.name, "已更新規劃", [beforeTerm, afterTerm]);
      setPlan(updated);
    } catch (error) {
      setNotice({ type: "error", text: error.message });
    } finally {
      setPlanBusy(false);
    }
  }

  const enrollments = [
    ...selected.map((record) => ({
      course: record.course,
      offering: record.offering,
      fixed: record.is_assigned,
      source: "confirmed",
    })),
    ...trial.map((offering) => ({
      course: offering.course,
      offering,
      fixed: false,
      source: "trial",
    })),
  ];
  const conflicts = previewConflicts(preview?.offering, enrollments);
  function resetFilters() {
    setQuery(""); setCategory("all"); setGeneralArea("all"); setProgramType("all");
    setDepartment("all"); setGrade("all"); setSection("all"); setDay("all"); setCredits("all");
    setNoConflictOnly(false); setAvailableOnly(false); setSelectedTime(null);
  }
  function findGraduationCourses(nextCategory, area = "all") {
    resetFilters(); setCategory(nextCategory); setGeneralArea(area); setPreview(null);
    navigate("courses"); setMobileTab("list");
  }
  const filterTags = [
    [query, `搜尋：${query}`, () => setQuery("")],
    [category !== "all", category === "general" ? "所有通識" : categoryLabel({category}), () => {setCategory("all"); setGeneralArea("all");}],
    [generalArea !== "all", {civic:"公民", sustainability:"永續", aesthetics:"美學"}[generalArea], () => setGeneralArea("all")],
    [programType !== "all", programType === "four_year" ? "四技" : "二技", () => setProgramType("all")],
    [department !== "all", department, () => setDepartment("all")],
    [day !== "all", `週${DAYS[Number(day)]}`, () => setDay("all")],
    [credits !== "all", `${credits} 學分`, () => setCredits("all")],
    [grade !== "all", `${grade} 年級`, () => setGrade("all")],
    [section !== "all", section === "unassigned" ? "不分班" : section, () => setSection("all")],
    [noConflictOnly, "不衝堂", () => setNoConflictOnly(false)],
    [availableOnly, "可選課程", () => setAvailableOnly(false)],
  ].filter(([active]) => active);
  const maxCredits = profile?.credits?.maximum ?? 25;
  const minCredits = profile?.credits?.minimum ?? 16;

  return (
    <div className={`app-shell ${sidebarCollapsed ? "sidebar-collapsed" : ""}`}>
      <a className="skip-link" href="#main-content">
        跳至主要內容
      </a>
      <header className="topbar">
        <button className="icon-button sidebar-toggle" onClick={toggleSidebar}
          aria-label={sidebarCollapsed ? "展開導覽" : "收合導覽"} aria-expanded={!sidebarCollapsed} aria-controls="desktop-navigation"
          title={sidebarCollapsed ? "展開導覽" : "收合導覽"}>
          {sidebarCollapsed ? <PanelLeftOpen size={20} /> : <PanelLeftClose size={20} />}
        </button>
        <a
          className="brand"
          href="/"
          onClick={(e) => {
            e.preventDefault();
            navigate("courses");
          }}
          aria-label="大學選課系統首頁"
        >
          <span className="brand-mark">
            <GraduationCap size={25} />
          </span>
          <span>
            <strong>大學選課系統</strong>
          </span>
        </a>
        <nav id="desktop-navigation" className="main-nav" aria-label="主要導覽">
          <button
            className={page === "courses" ? "nav-link active" : "nav-link"}
            onClick={() => navigate("courses")} title="本學期選課" aria-label="本學期選課"
          >
            <CalendarDays size={16} />
            <span>本學期選課</span>
          </button>
          <button
            className={page === "plans" ? "nav-link active" : "nav-link"}
            onClick={() => navigate("plans")} title="修課規劃" aria-label="修課規劃"
          >
            <LayoutGrid size={16} />
            <span>{profile?.student?.program_type === "two_year" ? "二技修課規劃" : "四年修課規劃"}</span>
          </button>
        </nav>
        <div className="account">
          <span className="account-dot">{user.slice(0, 1)}</span>
          <span className="account-name">{user}</span>
          <form action="/accounts/logout/" method="post">
            <input
              type="hidden"
              name="csrfmiddlewaretoken"
              value={
                document.cookie
                  .split("; ")
                  .find((part) => part.startsWith("csrftoken="))
                  ?.split("=")[1] || ""
              }
            />
            <button
              className="logout"
              type="submit"
              aria-label="登出"
              title="登出"
            >
              <LogOut size={17} />
            </button>
          </form>
        </div>
      </header>
      <div className="rail-context">
        <GraduationCap size={20} />
        <strong>{profile?.student?.department || "資訊管理系"}</strong>
        <span>{profile?.student?.class_name || "—"}</span>
        <small>課程資料為作業示範</small>
      </div>

      {page === "courses" ? (
        <motion.main
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ type: "spring", stiffness: 320, damping: 30 }}
          id="main-content"
          className="workspace"
        >
          <section className="page-intro">
            <div>
              <h1>
                本學期選課{" "}
                <span className="title-context">
                  {profile?.semester || "—"} 學期 ·{" "}
                  {profile?.student?.class_name || "—"}
                </span>
              </h1>

            </div>
            <span className="demo-tag">
              <span className="seat-dot" />{" "}
              {loading ? "正在同步" : loadError ? "連線異常" : "課表已同步"}
            </span>
          </section>
          <section className="credit-strip" aria-label="本學期學分摘要">
            <div className="credit-item current">
              <span className="credit-icon">
                <CheckCircle2 size={18} />
              </span>
              <div>
                <small>已確認</small>
                <strong>
                  {loading || loadError ? "—" : confirmedCredits}
                  <em>學分</em>
                </strong>
              </div>
            </div>
            <span className="credit-divider" />
            <div className="credit-item pending">
              <span className="credit-icon">
                <ArrowDownUp size={18} />
              </span>
              <div>
                <small>試排後</small>
                <strong>
                  {loading || loadError ? "—" : trialCredits}
                  <em>學分</em>
                </strong>
              </div>
            </div>
            <div className="credit-guidance">
              <span>最低 <b>{minCredits}</b> · 最高 <b>{maxCredits}</b> 學分</span>
              {!loading && !loadError && <small className={trialCredits < minCredits || trialCredits > maxCredits ? "credit-warning" : "credit-ok"}>
                {trialCredits < minCredits ? `試排後還差 ${minCredits - trialCredits} 學分達最低門檻` : trialCredits > maxCredits ? `試排後超出上限 ${trialCredits - maxCredits} 學分` : trialCredits === maxCredits ? "試排後已達學分上限" : `試排後可再安排 ${maxCredits - trialCredits} 學分`}
              </small>}
            </div>
            <div className="credit-action">
              <span>
                {trial.length
                  ? `${trial.length} 門課程待確認`
                  : ""}
              </span>
              <Button
                className="button-primary"
                disabled={!trial.length || busy}
                onClick={confirmTrial}
              >
                {busy ? (
                  <LoaderCircle className="spin" size={16} />
                ) : (
                  <Check size={16} />
                )}
                確認加選{trial.length ? `（${trial.length}）` : ""}
              </Button>
            </div>
          </section>

          {loadError && (
            <div className="page-alert error">
              <CircleAlert size={18} />
              <span>{loadError}</span>
              <button className="text-button" onClick={refresh}>
                重新載入
              </button>
            </div>
          )}
          {loading ? (
            <div className="loading-state">
              <LoaderCircle className="spin" />
              正在載入課程與課表…
            </div>
          ) : (
            <div className={`course-layout mobile-${mobileTab}`}>
              <section className="panel catalog-panel">
                <div className="panel-title">
                  <div>
                    <h2>
                      <Search size={21} />
                      找課程{" "}
                      <span className="result-count">{filtered.length}</span>
                    </h2>
                  </div>
                  <button
                    className="icon-button mobile-close"
                    onClick={() => setMobileTab("schedule")}
                    aria-label="關閉課程清單"
                  >
                    <X size={18} />
                  </button>
                </div>
                <label className="search-box">
                  <Search size={17} />
                  <input
                    value={query}
                    onChange={(e) => setQuery(e.target.value)}
                    placeholder="課名、課號、教師或系別"
                    aria-label="搜尋課名、課號、教師或系別"
                  />
                  <kbd>/</kbd>
                </label>
                <div className="filter-row catalog-primary-filters">
                  <label className="select-wrap">
                    <SlidersHorizontal size={15} />
                    <FilterSelect aria-label="課程類別" value={category}
                      onChange={(e) => setCategory(e.target.value)}>
                      <option value="all">所有類別</option>
                      <option value="required">系專業必修</option>
                      <option value="professional_elective">專業選修</option>
                      <option value="general">所有通識</option>
                      <option value="general_core">通識核心</option>
                      <option value="general_interest">通識興趣</option>
                      <option value="general_base">通識基礎</option>
                      <option value="pe">體育</option>
                    </FilterSelect>

                  </label>
                  <label className="select-wrap">
                    <FilterSelect aria-label="學制篩選" value={programType}
                      onChange={(e) => setProgramType(e.target.value)}>
                      <option value="all">全部學制</option>
                      <option value="four_year">四技</option>
                      <option value="two_year">二技</option>
                    </FilterSelect>

                  </label>
                  <label className="select-wrap">
                    <FilterSelect aria-label="系別篩選" value={department}
                      onChange={(e) => setDepartment(e.target.value)}>
                      <option value="all">全部系別</option>
                      {departments.map((name) => (
                        <option value={name} key={name}>{name}</option>
                      ))}
                    </FilterSelect>

                  </label>
                </div>
                <div className="filter-row catalog-quick-filters">
                  <label className="toggle-filter">
                    <input type="checkbox" checked={availableOnly}
                      onChange={(e) => setAvailableOnly(e.target.checked)} />
                    <span>只看可選</span>
                  </label>
                  <label className="toggle-filter">
                    <input type="checkbox" checked={noConflictOnly}
                      onChange={(e) => setNoConflictOnly(e.target.checked)} />
                    <span>只看不衝堂</span>
                  </label>
                </div>
                <details className="advanced-filters">
                  <summary>
                    <SlidersHorizontal size={16} />
                    更多篩選
                    {[day, credits, grade, section].some((value) => value !== "all") ? " · 已套用" : ""}
                    <ChevronDown size={16} />
                  </summary>
                  <div className="filter-row secondary-filters">
                    <label>
                      <span>星期</span>
                      <FilterSelect
                        aria-label="星期篩選"
                        value={day}
                        onChange={(e) => setDay(e.target.value)}
                      >
                        <option value="all">不限</option>
                        {DAYS.map((d, i) => (
                          <option key={d} value={i}>
                            週{d}
                          </option>
                        ))}
                      </FilterSelect>
                    </label>
                    <label>
                      <span>學分</span>
                      <FilterSelect
                        aria-label="學分篩選"
                        value={credits}
                        onChange={(e) => setCredits(e.target.value)}
                      >
                        <option value="all">不限</option>
                        {[0, 1, 2, 3, 4].map((n) => (
                          <option key={n} value={n}>
                            {n} 學分
                          </option>
                        ))}
                      </FilterSelect>
                    </label>
                    <label>
                      <span>年級</span>
                      <FilterSelect aria-label="年級篩選" value={grade}
                        onChange={(e) => setGrade(e.target.value)}>
                        <option value="all">不限</option>
                        {[1, 2, 3, 4].map((n) => (
                          <option value={n} key={n}>{"一二三四"[n - 1]}年級</option>
                        ))}
                      </FilterSelect>
                    </label>
                    <label>
                      <span>班級</span>
                      <FilterSelect aria-label="班級篩選" value={section}
                        onChange={(e) => setSection(e.target.value)}>
                        <option value="all">全部班級</option>
                        <option value="甲班">甲班</option>
                        <option value="乙班">乙班</option>
                        <option value="unassigned">不分班</option>
                      </FilterSelect>
                    </label>
                  </div>
                </details>
                {filterTags.length > 0 && <div className="active-filters" aria-label="已套用篩選">
                  {filterTags.map(([, label, clear]) => <button key={label} onClick={clear} aria-label={`取消${label}篩選`}>{label}<X size={13}/></button>)}
                  <button onClick={resetFilters}>全部清除</button>
                </div>}
                {selectedTime && (
                  <div className="time-filter-chip">
                    <span><Clock3 size={14} /> 週{DAYS[selectedTime.day]}第 {selectedTime.start}{selectedTime.start !== selectedTime.end ? `–${selectedTime.end}` : ""} 節的課程</span>
                    <button type="button" onClick={() => setSelectedTime(null)}>清除 <X size={13} /></button>
                  </div>
                )}
                <div className="list-meta">
                  <span>找到 {filtered.length} 個開課班別</span>
                  {(query || generalArea !== "all" || selectedTime ||
                    category !== "all" ||
                    day !== "all" ||
                    credits !== "all" ||
                    programType !== "all" ||
                    department !== "all" ||
                    grade !== "all" ||
                    section !== "all" ||
                    noConflictOnly ||
                    availableOnly) && (
                    <button
                      className="text-button"
                      onClick={resetFilters}
                    >
                      清除篩選
                    </button>
                  )}
                </div>
                <div className="course-list" aria-live="polite">
                  {filtered.map((item) => (
                    <CourseCard
                      key={item.offering.id}
                      item={item}
                      selectedIds={confirmedIds}
                      onOpen={openCourse}
                      onAdd={addTrial}
                      onPreview={(pinned) => {
                        setPreview(current => !pinned && current?.pinned ? current : {...item, pinned});
                        if(pinned) {setMobileTab("schedule"); requestAnimationFrame(() => document.querySelector(".schedule-panel")?.scrollIntoView({block:"start", behavior:"smooth"}));}
                      }}
                      onPreviewEnd={() => setPreview(current => current?.pinned ? current : null)}
                      trialIds={trialIds}
                      busy={busy}
                    />
                  ))}
                  {!filtered.length && (
                    <div className="empty-state">
                      <Search size={22} />
                      <strong>沒有符合條件的課程</strong>
                      <span>試著調整篩選條件或搜尋其他關鍵字。</span>
                    </div>
                  )}
                </div>
              </section>

              <section className="panel schedule-panel">
                <div className="panel-title">
                  <div>
                    <h2>
                      <CalendarDays size={21} />
                      我的週課表
                    </h2>
                  </div>
                  <div className="schedule-legend">
                    <span>
                      <i className="legend-dot required" />
                      系統預排
                    </span>
                    <span>
                      <i className="legend-dot selected" />
                      已選上
                    </span>
                    {trial.length > 0 && (
                      <span>
                        <i className="legend-dot trial" />
                        試排中
                      </span>
                    )}
                  </div>
                </div>
                {preview && <div className="course-preview-banner" role="status">
                  <div><strong>預覽 · {preview.course.name}</strong><small>僅預覽，不加入試排</small>
                    {conflicts.map((c, i) => <span className="preview-conflict" key={i}>與{c.name}重疊：{c.text}</span>)}
                  </div><button className="icon-button" aria-label="結束課程預覽" onClick={() => setPreview(null)}><X size={18}/></button>
                </div>}
                <Timetable
                  preview={preview}
                  conflictIds={conflicts.map(c => c.id)}
                  enrollments={enrollments}
                  periods={periods}
                  selectedTime={selectedTime}
                  onSelectTime={(next) => {
                    setSelectedTime((current) =>
                      current?.day === next.day && current.start === next.start && current.end === next.end
                        ? null : next);
                    if (window.matchMedia("(max-width: 700px)").matches) setMobileTab("list");
                  }}
                  onDropCourse={addTrial}
                  onOpen={(item) =>
                    openCourse(
                      courses.find((c) => c.course.id === item.course.id) || {
                        course: item.course,
                        offerings: [item.offering],
                      },
                      item.offering,
                    )
                  }
                />
                <div className="schedule-foot">
                  <span><Clock3 size={13} /> 點空白節次找課，按住拖曳可選連續時段</span>
                  <span className="drag-hint">課程卡片亦可拖入課表試排</span>
                  <button
                    className="mobile-open-list"
                    onClick={() => setMobileTab("list")}
                  >
                    <Search size={15} />
                    瀏覽課程
                  </button>
                </div>
              </section>

              <aside className="panel selection-panel">
                <div className="panel-title">
                  <div>
                    <h2>選課摘要</h2>
                  </div>
                  <span className="selection-count">
                    {enrollments.length} 門
                  </span>
                </div>
                <div className="summary-total">
                  <div>
                    <span>試排後總學分</span>
                    <small>
                      本學期範圍 {minCredits}–{maxCredits} 學分
                    </small>
                  </div>
                  <strong>
                    {trialCredits}
                    <small>學分</small>
                  </strong>
                </div>
                {trialCredits > maxCredits && (
                  <div className="inline-warning">
                    <CircleAlert size={15} />
                    超過上限 {trialCredits - maxCredits} 學分，請調整試排課程。
                  </div>
                )}
                <div className="selection-list">
                  {enrollments.map((item) => (
                    <div
                      className={`selection-row ${item.source}`}
                      key={item.offering.id}
                    >
                      <div className="selection-marker">
                        {item.fixed ? (
                          <LockKeyhole size={13} />
                        ) : item.source === "trial" ? (
                          <ArrowDownUp size={13} />
                        ) : (
                          <Check size={14} />
                        )}
                      </div>
                      <div className="selection-info">
                        <button
                          className="course-name-link"
                          onClick={() =>
                            openCourse(
                              courses.find(
                                (c) => c.course.id === item.course.id,
                              ) || {
                                course: item.course,
                                offerings: [item.offering],
                              },
                              item.offering,
                            )
                          }
                        >
                          {item.course.name}
                        </button>
                        <span>
                          {item.offering.class_label || "不分班"}
                        </span>
                        <span>
                          {slotsText(item.offering)}
                        </span>
                      </div>
                      <b>
                        {item.course.credits} <small>學分</small>
                      </b>
                      {item.source === "confirmed" && !item.fixed &&
                        (courses.find((course) => course.course.id === item.course.id)?.offerings.length || 0) > 1 && (
                          <button
                            className="icon-button row-action switch-row"
                            type="button"
                            title="更換班別"
                            disabled={busy}
                            onClick={() => openSwitch(item)}
                            aria-label={"更換" + item.course.name + "班別"}
                          >
                            <ArrowLeftRight size={17} />
                          </button>
                        )}
                      {!item.fixed && (
                        <button
                          className="icon-button row-action"
                          disabled={busy}
                          onClick={() =>
                            item.source === "trial"
                              ? setTrial((old) =>
                                  old.filter((x) => x.id !== item.offering.id),
                                )
                              : setDropTarget(item)
                          }
                          aria-label={`${item.source === "trial" ? "移除試排" : "退選"}${item.course.name}`}
                        >
                          <Trash2 size={15} />
                        </button>
                      )}
                    </div>
                  ))}
                  {!enrollments.length && (
                    <div className="mini-empty">目前沒有已選課程</div>
                  )}
                </div>
                <div className="selection-actions">
                  {trial.length > 0 && (
                    <Button
                      className="button-primary"
                      disabled={busy || trialCredits > maxCredits}
                      onClick={confirmTrial}
                    >
                      {busy ? (
                        <LoaderCircle className="spin" size={16} />
                      ) : (
                        <Check size={16} />
                      )}
                      確認加選 <ArrowRight size={16} />
                    </Button>
                  )}

                </div>
              </aside>
            </div>
          )}
        </motion.main>
      ) : (
        <motion.main
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ type: "spring", stiffness: 320, damping: 30 }}
          id="main-content"
          className="workspace plans-workspace"
        >
          <section className="page-intro">
            <div>
              <h1>
                {profile?.student?.program_type === "two_year" ? "二技修課規劃" : "四年修課規劃"}{" "}
                <span className="title-context">
                  {profile?.student?.admission_year || 115} 學年度入學 ·{" "}
                  {profile?.student?.department || "資訊管理系"} ·{" "}
                  {profile?.student?.program_type === "two_year" ? "二技" : "四技"}
                </span>
              </h1>
              <p>檢視課程進度；可拖曳或透過課程卡片上的學期選單移動。</p>
            </div>
            <span className="demo-tag">依課程資料規劃</span>
          </section>
          {plan ? (
            <>
              <section className="graduation-strip">
                <div className="graduation-icon">
                  <GraduationCap size={21} />
                </div>
                <div className="graduation-copy">
                  <strong>畢業學分規劃</strong>
                  <span>
                    已修 {profile?.curriculum?.completed_credits ?? 0} · {plan.terms.length} 學期已排{" "}
                    {plan.total_planned_credits} · 已修與規劃合計{" "}{plan.graduation.covered_credits} · 畢業門檻{" "}
                    {plan.graduation.target}
                  </span>
                </div>
                <div className="graduation-progress">
                  <div className="meter-track">
                    <span
                      style={{
                        width: `${Math.min(100, (plan.graduation.covered_credits / plan.graduation.target) * 100)}%`,
                      }}
                    />
                  </div>
                  <strong>
                    {Math.round(
                      (plan.graduation.covered_credits / plan.graduation.target) *
                        100,
                    )}
                    <small>% 已安排</small>
                  </strong>
                </div>
                <button
                  className="button-secondary"
                  onClick={() =>
                    setPlanPicker(
                      Math.min(
                        plan.terms.length,
                        Math.max(
                          1,
                          ((profile?.student?.grade || 1) - 1) * 2 +
                            (profile?.semester?.endsWith("-2") ? 2 : 1),
                        ),
                      ),
                    )
                  }
                >
                  <Plus size={16} />
                  新增規劃
                </button>
              </section>
              <PlanLoadChart terms={plan.terms} maxCredits={maxCredits} impact={planImpact} />
              {plan.warnings?.some((item) => !item.required) && (
                <div className="page-alert warning">
                  <CircleAlert size={17} />
                  <span>
                    {plan.warnings.filter((item) => !item.required).map((item) => item.message).join(" ")}
                  </span>
                </div>
              )}
              <section className="four-year-map" aria-label="跨學期拖曳課程規劃">
                <div className="four-year-map-heading">
                  <span>拖曳課程至目標學期；標記未通過後，可將重修卡拖至較晚學期。</span>
                  <span>{plan.terms.reduce((sum, term) => sum + term.courses.filter((entry) => entry.source !== "failed").length, 0)} 門課程</span>
                </div>
                <div className={`four-year-columns ${plan.terms.length <= 4 ? "two-year" : ""}`}>
                  {Array.from({ length: Math.ceil(plan.terms.length / 2) }, (_, i) => i + 1).map((year) => {
                    const terms = plan.terms.slice((year - 1) * 2, year * 2);
                    return (
                      <div className="plan-year-column" key={year}>
                        <div className="plan-year-heading">
                          <h2>大{["一", "二", "三", "四"][year - 1]}</h2>
                          <span>{terms.reduce((sum, item) => sum + item.credits, 0)} 學分</span>
                        </div>
                        {terms.map((term) => (
                          <PlanTerm
                            key={term.term}
                            term={term}
                            busy={planBusy}
                            dragEntry={draggedPlan}
                            onDragEntry={setDraggedPlan}
                            maxCredits={maxCredits}
                            maxTerms={plan.terms.length}
                            failedTermsFor={(courseId) => Math.max(0, ...plan.terms.filter(t => t.courses.some(c => c.source === "failed" && c.course.id === courseId)).map(t => t.term))}
                            failedTerms={plan.terms.filter(t => t.courses.some(c => c.source === "failed" && c.course.id === draggedPlan?.course.id)).map(t => t.term)}
                            onDrop={savePlanMove}
                            onFail={markPlanFailed}
                            onRestore={restorePlanFailed}
                            onRemove={removePlanCourse}
                            onAdd={() => setPlanPicker(term.term)}
                            onOpen={(entry) => openCourse(
                              courses.find((item) => item.course.id === entry.course.id) ||
                                { course: entry.course, offerings: [] },
                            )}
                          />
                        ))}
                      </div>
                    );
                  })}
                </div>
              </section>
              <section className="plan-progress">
                <div>
                  <h2>畢業學分分類</h2>
                </div>
                <div className="progress-categories">
                  <ProgressCategory
                    onFind={() => findGraduationCourses("professional_elective")}
                    title="專業選修"
                    done={plan.graduation.professional_covered}
                    target={plan.graduation.professional_target}
                  />
                  {Object.entries(profile?.curriculum?.general_core || {}).map(
                    ([key, value]) => (
                      <ProgressCategory
                        key={key}
                        title={
                          {
                            civic: "通識核心・公民",
                            sustainability: "通識核心・永續",
                            aesthetics: "通識核心・美學",
                          }[key]
                        }
                        done={plan.graduation.general_core_covered?.[key] || 0}
                        onFind={() => findGraduationCourses("general_core", key)}
                        target={value.target}
                      />
                    ),
                  )}
                </div>
              </section>
              <section className="completed-courses">
                <div>
                  <h2>已完成課程</h2>
                  <p>以學生歷年修課紀錄計算，未提供的資料不會代填。</p>
                </div>
                {plan.completed_courses?.length ? (
                  <ul>
                    {plan.completed_courses.map(
                      ({ course, semester, status }) => (
                        <li key={course.id}>
                          <CheckCircle2 size={15} />
                          <span>{course.name}</span>
                          <small>
                            {semester || "學期未記錄"} ·{" "}
                            {status === "passed" ? "修課通過" : "學分抵免"}
                          </small>
                        </li>
                      ),
                    )}
                  </ul>
                ) : (
                  <div className="completed-empty">
                    目前尚無已完成課程紀錄。
                  </div>
                )}
              </section>
            </>
          ) : (
            <div className="loading-state">
              {planError ? (
                <>
                  <CircleAlert />
                  <p>{planError}</p>
                  <button
                    className="button-secondary"
                    onClick={() => {
                      setPlanError("");
                      request("/api/plan/")
                        .then(setPlan)
                        .catch((e) => setPlanError(e.message));
                    }}
                  >
                    重新載入規劃
                  </button>
                </>
              ) : (
                <>
                  <LoaderCircle className="spin" />
                  正在載入四年規劃…
                </>
              )}
            </div>
          )}
        </motion.main>
      )}

      <AnimatePresence>
        {drawer && (
          <CourseDrawer
            key={drawer.requestId}
            drawer={drawer}
            setDrawer={setDrawer}
            selectedIds={confirmedIds}
            selectedRecords={selected}
            onSwitch={(record, targetId) => {
              setDrawer(null);
              openSwitch({ course: record.course, offering: record.offering }, targetId);
            }}
            trialIds={trialIds}
            onAdd={addTrial}
            busy={busy}
            onRemove={(offering) => {
              const item = enrollments.find(
                (e) => e.offering.id === offering.id,
              );
              if (item?.source === "trial")
                setTrial((old) => old.filter((t) => t.id !== offering.id));
              else if (item && !item.fixed) {
                setDrawer(null);
                setDropTarget(item);
              }
            }}
            fixedIds={
              new Set(
                selected.filter((s) => s.is_assigned).map((s) => s.offering.id),
              )
            }
          />
        )}
      </AnimatePresence>
      <AnimatePresence>
        {notice && (
          <motion.div
            className={`toast ${notice.type || "info"}`}
            role="status"
            initial={{ opacity: 0, y: 12, x: "-50%" }}
            animate={{ opacity: 1, y: 0, x: "-50%" }}
            exit={{
              opacity: 0,
              y: 8,
              x: "-50%",
              transition: { duration: 0.15 },
            }}
          >
            <span>
              {notice.type === "success" ? (
                <CheckCircle2 size={17} />
              ) : notice.type === "error" ? (
                <CircleAlert size={17} />
              ) : (
                <Sparkles size={17} />
              )}
            </span>
            {notice.text}
            <button onClick={() => setNotice(null)} aria-label="關閉通知">
              <X size={15} />
            </button>
          </motion.div>
        )}
      </AnimatePresence>
      {planPicker && (
        <PlanPicker
          courses={(plan?.available_courses || []).map((course) => ({ course }))}
          term={planPicker}
          onClose={() => setPlanPicker(null)}
          busy={planBusy}
          onChoose={(course) => addPlanCourse(course, planPicker)}
        />
      )}
      {switchSource && (
        <SwitchClassDialog
          current={switchSource.current}
          offerings={switchSource.offerings}
          initialTargetId={switchSource.initialTargetId}
          trialCount={trial.length}
          busy={busy}
          onClose={() => setSwitchSource(null)}
          onConfirm={switchOffering}
        />
      )}
      {dropTarget && (
        <DropConfirm
          item={dropTarget}
          busy={busy}
          onCancel={() => setDropTarget(null)}
          onConfirm={async () => {
            const offeringId = dropTarget.offering.id;
            setDropTarget(null);
            await dropOffering(offeringId);
          }}
        />
      )}
      <footer className="footer-note">
        大學 · 資訊管理系 <span>課程與班別資料為作業示範內容</span>
      </footer>
      <nav
        className={`mobile-tabs ${page === "plans" ? "plans-tabs" : ""}`}
        aria-label="手機版頁籤"
      >
        {page === "plans" ? (
          <button onClick={() => navigate("courses")}>
            <CalendarDays size={18} />
            返回本學期選課
          </button>
        ) : (
          <>
            <button
              className={mobileTab === "list" ? "active" : ""}
              onClick={() => setMobileTab("list")}
            >
              <BookOpen size={18} />
              找課程
            </button>
            <button
              className={mobileTab === "schedule" ? "active" : ""}
              onClick={() => setMobileTab("schedule")}
            >
              <CalendarDays size={18} />
              我的課表
            </button>
            <button
              className={mobileTab === "selection" ? "active" : ""}
              onClick={() => setMobileTab("selection")}
            >
              <CheckCircle2 size={18} />
              選課摘要
            </button>
            <button onClick={() => navigate("plans")}>
              <GraduationCap size={18} />
              {profile?.student?.program_type === "two_year" ? "二技規劃" : "四年規劃"}
            </button>
          </>
        )}
      </nav>
    </div>
  );
}

function CourseCard({ item, selectedIds, trialIds, busy, onOpen, onAdd, onPreview, onPreviewEnd }) {
  const { course, offering, offerings } = item;
  const selected = selectedIds.has(offering.id);
  const trial = trialIds.has(offering.id);
  return (
    <motion.article
      className="course-card"
      onMouseEnter={() => {if (window.matchMedia("(hover: hover)").matches) onPreview(false);}}
      onMouseLeave={onPreviewEnd}
      layout="position"
      transition={{ type: "spring", stiffness: 350, damping: 30 }}
    >
      <button
        className="course-card-main"
        draggable={offering.can_select && offering.remaining > 0 && !selected}
        onDragStart={(event) => event.dataTransfer.setData(
          "application/json",
          JSON.stringify({ offering, course }),
        )}
        onClick={() => onOpen(item, offering)}
        aria-label={`查看 ${course.name}，${teacherName(offering)}的課程詳情`}
      >
        <div className="course-card-top">
          <span className={`category-tag cat-${course.category}`}>
            {categoryLabel(course)}
          </span>
          <span className="course-credits">{course.credits} 學分</span>
        </div>
        <h3>{course.name}</h3>
        <div className="course-offering-facts">
          <span><UserRound size={15} /> <strong>{teacherName(offering)}</strong></span>
          <span><Clock3 size={15} /> {slotsText(offering)}</span>
        </div>
        <div className="course-card-submeta">
          {course.code}{offerings.length > 1 ? ` · 開課序號 ${offering.section}` : ""}
        </div>
        <OfferingAttributes course={course} offering={offering} />
        <span className="course-detail-hint">
          課程詳情 <ChevronRight size={16} />
        </span>
      </button>
      <div className="course-preview-action"><button onClick={() => onPreview(true)}><CalendarDays size={15}/> {offering.conflicts?.length ? "查看衝堂位置" : "預覽課表"}</button></div>
      <div className="course-card-bottom">
        <span className="seat-state">
          {selected ? <><Check size={13} /> 已選上</>
            : offering.remaining === 0 ? <><CircleAlert size={13} /> 目前額滿</>
              : offering.conflicts?.length ? <><CircleAlert size={13} /> 衝堂 · 剩餘 {offering.remaining} 名</>
                : <><span className="seat-dot" /> 剩餘 {offering.remaining} 名</>}
        </span>
        {selected ? (
          <span className="selected-label"><Check size={14} /> 已選上</span>
        ) : (
          <button className="quick-add" onClick={() => onAdd(offering, course)}
            disabled={busy || trial || !offering.can_select || offering.remaining <= 0}>
            {trial ? <Check size={14} /> : <Plus size={14} />}
            {trial ? "試排中" : "加入試排"}
          </button>
        )}
      </div>
    </motion.article>
  );
}

function ProgressCategory({ title, done, target, onFind }) {
  const percent = Math.min(100, Math.round(((done || 0) / target) * 100));
  return (
    <div className="progress-category">
      <div>
        <span>{title}</span>
        <strong>
          {done || 0}
          <small> / {target} 學分</small>
        </strong>
      </div>
      <div className="meter-track">
        <span style={{ width: `${percent}%` }} />
      </div>
      <small>
        {percent >= 100
          ? "已達規劃學分"
          : `尚差 ${Math.max(0, target - (done || 0))} 學分`}
      </small>
      {percent < 100 && onFind && <button className="graduation-find" onClick={onFind}>找符合課程 <ArrowRight size={14}/></button>}
    </div>
  );
}

function useModalFocus(onClose) {
  const ref = useRef(null);
  useEffect(() => {
    const previous = document.activeElement;
    const oldOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    ref.current
      ?.querySelector("button:not(:disabled), input:not(:disabled)")
      ?.focus();
    const handleKey = (event) => {
      if (event.key === "Escape") {
        event.preventDefault();
        onClose();
        return;
      }
      if (event.key !== "Tab" || !ref.current) return;
      const focusable = [
        ...ref.current.querySelectorAll(
          'button:not(:disabled), a[href], input:not(:disabled), select:not(:disabled), [tabindex="0"]',
        ),
      ];
      if (!focusable.length) return;
      if (event.shiftKey && document.activeElement === focusable[0]) {
        event.preventDefault();
        focusable.at(-1).focus();
      } else if (
        !event.shiftKey &&
        document.activeElement === focusable.at(-1)
      ) {
        event.preventDefault();
        focusable[0].focus();
      }
    };
    document.addEventListener("keydown", handleKey);
    return () => {
      document.body.style.overflow = oldOverflow;
      document.removeEventListener("keydown", handleKey);
      previous?.focus?.();
    };
  }, [onClose]);
  return ref;
}

function PlanPicker({ courses, term, onClose, onChoose, busy }) {
  const dialogRef = useModalFocus(onClose);
  const [query, setQuery] = useState("");
  const options = courses.filter(
    (item) =>
      !["required", "general_base", "pe"].includes(item.course.category) &&
      `${item.course.name}${item.course.code}`
        .toLocaleLowerCase()
        .includes(query.toLocaleLowerCase()),
  );
  return (
    <div
      className="modal-backdrop"
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <motion.div
        ref={dialogRef}
        className="plan-picker"
        role="dialog"
        aria-modal="true"
        aria-label="新增規劃課程"
        initial={{ opacity: 0, y: 10, scale: 0.98 }}
        animate={{ opacity: 1, y: 0, scale: 1 }}
      >
        <div className="picker-head">
          <div>
            <h2>加入第 {term} 學期</h2>
          </div>
          <button className="icon-button" onClick={onClose} aria-label="關閉">
            <X size={19} />
          </button>
        </div>
        <label className="search-box">
          <Search size={17} />
          <input
            autoFocus
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            aria-label="搜尋規劃課程"
            placeholder="搜尋課程名稱或課號"
          />
        </label>
        <div className="picker-list">
          {options.map(({ course }) => (
            <button
              className="picker-course"
              key={course.id}
              disabled={busy}
              onClick={() => onChoose(course)}
            >
              <span>
                <strong>{course.name}</strong>
                <small>
                  {course.code} · {categoryLabel(course)}
                </small>
              </span>
              <span>
                {course.credits} 學分 <Plus size={15} />
              </span>
            </button>
          ))}
          {!options.length && (
            <div className="empty-state">目前沒有可加入規劃的課程。</div>
          )}
        </div>
      </motion.div>
    </div>
  );
}

function DropConfirm({ item, busy, onCancel, onConfirm }) {
  const dialogRef = useModalFocus(onCancel);
  return (
    <div
      className="modal-backdrop"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) onCancel();
      }}
    >
      <motion.section
        ref={dialogRef}
        className="drop-confirm"
        role="dialog"
        aria-modal="true"
        aria-labelledby="drop-confirm-title"
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
      >
        <div className="drop-confirm-mark">
          <Trash2 size={19} />
        </div>
        <h2 id="drop-confirm-title">確認退選課程</h2>
        <p>
          要退選「{item.course.name}」嗎？退選後本學期學分與課表會立即更新。
        </p>
        <div className="drop-confirm-actions">
          <button
            className="button-secondary"
            onClick={onCancel}
            disabled={busy}
          >
            保留課程
          </button>
          <Button className="button-danger" onClick={onConfirm} disabled={busy}>
            {busy ? (
              <LoaderCircle className="spin" size={15} />
            ) : (
              <Trash2 size={15} />
            )}
            確認退選
          </Button>
        </div>
      </motion.section>
    </div>
  );
}

export default App;
