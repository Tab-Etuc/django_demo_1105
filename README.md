# 大學選課系統

使用 Python 3.14.7、Django 6.1.2、React、Tailwind CSS 與 SQLite 建立。

## 功能

- 課程搜尋與班別篩選、完整課綱、教師及上課時段。
- 週課表拖曳試排、衝堂與名額檢查、加選、退選、換班。
- 四年／二技修課規劃、跨學期拖曳、未通過與重修安排、畢業學分進度。
- Session 登入、CSRF 保護；選課規則與資料寫入由 Django API 驗證。

## 本機啟動（Windows 10／11）

**即使電腦完全沒裝 Python，或原本裝的是 Python 3.15，也可以照以下步驟啟動。** 專案預設使用 **Python 3.14.7 及 Django 6.1.2**（已釘選確切版本）。由 `uv` 管理專案專用的 Python 和套件，不必移除電腦上原有的 Python。

### 1. 安裝必要工具（每台電腦只要一次）

開啟 **PowerShell**，先安裝 uv（Python 環境管理工具）和 Node.js LTS（前端建置工具）：

```powershell
winget install --id astral-sh.uv -e
winget install --id OpenJS.NodeJS.LTS -e
```

若電腦沒有 `winget`，可改用 [uv 官方安裝指令](https://docs.astral.sh/uv/getting-started/installation/) 安裝 uv，並從 [Node.js 官網](https://nodejs.org/) 安裝 LTS 版：

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

**安裝完成後，關閉 PowerShell 並重新開啟**，確認指令可以使用：

```powershell
uv --version
node --version
npm.cmd --version
```

### 2. 開啟專案資料夾

如果已經下載專案，直接進入放置 `manage.py` 的資料夾；例如：

```powershell
cd D:\django_demo_1105
```

若還沒下載原始碼，可先安裝 Git（`winget install --id Git.Git -e`），重新開啟 PowerShell，再執行：

```powershell
git clone https://github.com/Tab-Etuc/django_demo_1105.git
cd .\django_demo_1105
```

### 3. 建立正確版本的 Python 環境

```powershell
uv python install 3.14.7
uv sync --python 3.14.7 --locked
uv run --locked python --version
uv run --locked python -m django --version
```

確認顯示 **Python 3.14.7** 和 **Django 6.1.2**。`.python-version` 已固定為 `3.14.7`，`pyproject.toml` 也限制 Python 必須為 `>=3.14.7,<3.15`。即使電腦原本裝有 Python 3.14.3 或 3.15，`uv sync` 也會將專案 `.venv` 切換成 3.14.7，不影響其他專案的 Python。

### 4. 安裝並建置前端

```powershell
npm.cmd ci
npm.cmd run build
```

### 5. 建立資料庫並啟動網站

```powershell
uv run --locked python manage.py migrate
uv run --locked python manage.py runserver 127.0.0.1:8000
```

開啟 **http://127.0.0.1:8000/**，在登入頁點「遊客」即可自動建立示範帳號及課程資料。也可手動執行 `uv run python manage.py seed_demo`。

### 常見問題

- **`uv`、`node` 或 `npm` 顯示「無法辨識」**：確認第一步已完成，關閉並重新開啟 PowerShell；仍無法執行則重新確認安裝與 PATH。
- **出現 `getfullargspec() got an unexpected keyword argument 'annotation_format'`，或 `Python 3.14.3 is incompatible`**：先在專案資料夾執行 `uv python install 3.14.7`，再執行 `uv sync --python 3.14.7 --locked`。已安裝的 3.14.3 無須移除。
- **uv 顯示找不到 Python 3.14.7 下載版本**：可能是 uv 過舊。若使用 winget 安裝，執行 `winget upgrade --id astral-sh.uv -e`；使用官方安裝腳本則執行 `uv self update`，重新開啟 PowerShell 後再試一次 `uv python install 3.14.7`。
- **PowerShell 顯示 `npm.ps1` 禁止執行指令碼**：使用上面的 `npm.cmd` 指令即可。
- **已有 `db.sqlite3`**：不要刪除；`migrate` 會保留既有的選課資料。

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
