# 大學選課系統

使用 Python 3.14、Django 6.1、React、Tailwind CSS 與 SQLite 建立。

## 功能

- 課程搜尋與班別篩選、完整課綱、教師及上課時段。
- 週課表拖曳試排、衝堂與名額檢查、加選、退選、換班。
- 四年／二技修課規劃、跨學期拖曳、未通過與重修安排、畢業學分進度。
- Session 登入、CSRF 保護；選課規則與資料寫入由 Django API 驗證。

## 本機啟動

```bash
uv sync
npm ci
npm run build
uv run python manage.py migrate
uv run python manage.py runserver 127.0.0.1:8000
```

開啟 http://127.0.0.1:8000/ 。登入頁的「遊客」可自動建立示範帳號及課程資料，也可手動執行 `uv run python manage.py seed_demo`。

## 入口

- `/`：React 選課與週課表
- `/plans/`：React 修課規劃
- `/accounts/login/`：React 登入
- `/api/`：JSON API；`/api/timetable/?semester=115-1` 可查詢指定學期課表

前端位於 `src/`，後端 API 位於 `courses/api.py`、`courses/plans.py`，選課規則位於 `courses/selection.py`。修改前端後執行 `npm run build`。

## 測試

```bash
uv run python manage.py test
uv run python manage.py check
uv run python manage.py makemigrations --check --dry-run
uv run ruff check .
uv run ruff format --check .
npm test
npm run build
```

本機 `db.sqlite3` 不納入 Git；新環境執行遷移後即可產生示範資料。正式部署需設定 `DJANGO_DEBUG=0`、`DJANGO_SECRET_KEY` 與 `DJANGO_ALLOWED_HOSTS`。
