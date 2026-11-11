# 專案指引

## 環境

- Python 3.14.7（`.python-version` 固定修補版本）、Django 6.1.2、SQLite，使用 `uv` 管理 Python 相依套件。安裝與同步時需使用 `3.14.7`，不可只指定 `3.14`。
- React、Tailwind CSS 與 Vite；前端位於 `src/`，執行 `npm run build` 產生靜態檔。
- Django 路由：React 頁面在 `/`、`/plans/`，登入在 `/accounts/login/`，其他功能使用 `/api/`。
- 已移除舊版 HTML、Bootstrap、教師頁與管理後台；只維護現行 React 介面。

## 資料流與規則

- `courses/api.py`、`courses/plans.py` 提供 JSON API；`courses/selection.py` 處理加退選、換班、衝堂、名額與學分限制。
- `courses/models.py` 儲存課程、開課班別及多時段課表；`courses/academic.py` 儲存學籍、修課規劃與重修資料。
- 登入使用 Django Session，寫入 API 需 CSRF；學生資料與權限由後端驗證。
- `uv run python manage.py seed_demo` 建立示範資料；開發環境也可從登入頁點「遊客」自動初始化。
- 本機 SQLite 資料須保留；修改規劃不會直接變更已正式加選的紀錄。

## 驗證

```bash
uv run ruff check .
uv run ruff format --check .
uv run python manage.py test
uv run python manage.py makemigrations --check --dry-run
npm test
npm run build
```

修改核心邏輯需同步維護測試。優先從入口追查到輸出，保留最少必要實作。
