| 學號 | 姓名 |
| --- | --- |
| 11446010 | 何宗儒 |
| 11446022 | 黃偉程 |
| 11446025 | 古少洋 |
| 11446027 | 金冠宏 |
| 11446037 | 羅少希 |


# 大學選課系統

使用 Python 3.14.3、Django 6.1.2、React、Tailwind CSS 與 SQLite 建立。

## 功能

- 課程搜尋與班別篩選、完整課綱、教師及上課時段。
- 週課表拖曳試排、衝堂與名額檢查、加選、退選、換班。
- 四年／二技修課規劃、跨學期拖曳、未通過與重修安排、畢業學分進度。
- Session 登入、CSRF 保護；選課規則與資料寫入由 Django API 驗證。


## 本機啟動（Windows 10／11）

**即使電腦完全沒裝 Python，或原本裝的是 Python 3.15，也可以照以下步驟啟動。** 專案預設使用 **Python 3.14.3 及 Django 6.1.2**（已釘選確切版本）。由 `uv` 管理專案專用的 Python 和套件，不必移除電腦上原有的 Python。

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
uv sync --python 3.14.3 --locked
uv run --locked python --version
uv run --locked python -m django --version
```

`uv sync` 會在需要時**自動下載 Python 3.14.3**，即使電腦完全沒有安裝 Python 也能使用。確認版本顯示 **Python 3.14.3** 和 **Django 6.1.2**。`.python-version` 固定使用 3.14.3，`pyproject.toml` 允許 `>=3.14.3,<3.15`。即使原本裝有 Python 3.15，也會為專案建立相容的 `.venv`，保留電腦上其他 Python 環境。

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
