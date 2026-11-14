"""MY PLANNER: auditable, deterministic calculations and local SQLite persistence.
All persisted and computed monetary amounts are Korean won (integer KRW).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path
from contextlib import contextmanager
import csv
import io
import os
import sqlite3
import tempfile
from typing import Optional


DEFAULTS = {
    "monthly_income": 2_900_000,    # 290 만 원
    "annual_irregular_income": 5_200_000,  # 520 만 원
    "monthly_saving": 1_000_000,  # 100 만 원
    "annual_extra_saving": 1_000_000,  # 100 만 원
    "safe_return_pct": 0.0,
    "risk_return_pct": 0.0,
}


def won(value) -> str:
    return f"{int(round(float(value))):,}원"


def manwon(value, decimals=0) -> str:
    value = float(value) / 10_000
    if decimals:
        return f"{value:,.{decimals}f}만 원"
    if abs(value - round(value)) > 0.001:
        return f"{value:,.1f}만 원"
    return f"{value:,.0f}만 원"


def to_won(man) -> int:
    return int(round(float(man) * 10_000))


def as_man(won_amount) -> float:
    return round(float(won_amount) / 10_000, 2)


def default_db_path():
    return Path(os.getenv("MY_PLANNER_DB", str(Path(__file__).parent / "data" / "my_planner.db"))).expanduser()


@contextmanager
def connection(db_path=None):
    path = Path(db_path) if db_path else default_db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(path), timeout=30)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA busy_timeout = 30000")
    db.execute("PRAGMA foreign_keys = ON")
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def initialize(db_path=None):
    with connection(db_path) as db:
        db.executescript("""
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS assets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            asset_type TEXT NOT NULL CHECK(asset_type IN ('safe','risk')),
            purpose TEXT NOT NULL CHECK(purpose IN ('emergency','goal','long','other')),
            amount_won INTEGER NOT NULL CHECK(amount_won >= 0),
            is_liquid INTEGER NOT NULL DEFAULT 0 CHECK(is_liquid IN (0,1)),
            maturity_date TEXT,
            notes TEXT NOT NULL DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS budgets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            expense_group TEXT NOT NULL CHECK(expense_group IN ('fixed','variable')),
            limit_won INTEGER NOT NULL CHECK(limit_won >= 0)
        );
        CREATE TABLE IF NOT EXISTS goals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            target_won INTEGER NOT NULL CHECK(target_won > 0),
            months INTEGER NOT NULL CHECK(months BETWEEN 1 AND 360),
            priority INTEGER NOT NULL DEFAULT 1,
            notes TEXT NOT NULL DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            booked_on TEXT NOT NULL,
            entry_type TEXT NOT NULL CHECK(entry_type IN ('income','expense','saving')),
            category TEXT NOT NULL,
            amount_won INTEGER NOT NULL CHECK(amount_won > 0),
            memo TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS idx_tx_date ON transactions(booked_on);
        """)
        was_initialized = db.execute("SELECT 1 FROM settings WHERE key='__initialized__'").fetchone() is not None
        for key, value in DEFAULTS.items():
            db.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?,?)", (key, str(value)))
        if not was_initialized and db.execute("SELECT COUNT(*) FROM assets").fetchone()[0] == 0:
            db.executemany("""INSERT INTO assets
                (name,asset_type,purpose,amount_won,is_liquid,notes)
                VALUES(?,?,?,?,?,?)""", [
                ("비상예비자금", "safe", "emergency", 10_000_000, 1, "초기 예시: 즉시 인출 가능 자금"),
                ("예금·목표 저축자금", "safe", "goal", 25_000_000, 0, "초기 예시: 상품별 세부 잔액은 직접 수정"),
                ("ETF·배당주", "risk", "long", 15_000_000, 0, "초기 예시: 투자자산 평가액"),
            ])
        if not was_initialized and db.execute("SELECT COUNT(*) FROM budgets").fetchone()[0] == 0:
            db.executemany("INSERT INTO budgets(name,expense_group,limit_won) VALUES(?,?,?)", [
                ("고정 소비", "fixed", 770_000),
                ("선택 소비", "variable", 870_000),
            ])
        if not was_initialized and db.execute("SELECT COUNT(*) FROM goals").fetchone()[0] == 0:
            db.execute("INSERT INTO goals(name,target_won,months,priority,notes) VALUES(?,?,?,?,?)",
                       ("결혼 및 주거 독립", 100_000_000, 48, 1, "보고서 기준 예시 목표"))
        db.execute("INSERT OR IGNORE INTO settings(key,value) VALUES('__initialized__','1')")


def get_settings(db_path=None):
    with connection(db_path) as db:
        stored = {row["key"]: row["value"] for row in db.execute("SELECT key,value FROM settings")}
    result = {}
    for key, default in DEFAULTS.items():
        try:
            result[key] = float(stored.get(key, default)) if isinstance(default, float) else int(float(stored.get(key, default)))
        except (ValueError, TypeError):
            result[key] = default
    return result


def set_settings(settings: dict, db_path=None):
    with connection(db_path) as db:
        for key, value in settings.items():
            if key not in DEFAULTS:
                raise ValueError(f"알 수 없는 설정: {key}")
            if key.endswith("pct"):
                if not (-100 <= float(value) <= 100):
                    raise ValueError("수익률은 -100~100%여야 합니다.")
            elif float(value) < 0:
                raise ValueError("입력 금액은 음수가 될 수 없습니다.")
            db.execute("INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                       (key, str(value)))


def rows(table: str, db_path=None):
    if table not in {"assets", "budgets", "goals", "transactions"}:
        raise ValueError("허용되지 않은 테이블")
    order = {"assets": "id", "budgets": "id", "goals": "priority,id", "transactions": "booked_on DESC,id DESC"}[table]
    with connection(db_path) as db:
        return [dict(row) for row in db.execute(f"SELECT * FROM {table} ORDER BY {order}")]


def write_asset(name, asset_type, purpose, amount_won, is_liquid=False, maturity_date=None,
                notes="", item_id=None, db_path=None):
    if not name.strip() or amount_won < 0:
        raise ValueError("자산명과 0 이상 금액이 필요합니다.")
    if asset_type not in ("safe", "risk") or purpose not in ("emergency", "goal", "long", "other"):
        raise ValueError("잘못된 자산 분류")
    args = (name.strip(), asset_type, purpose, int(amount_won), int(bool(is_liquid)), maturity_date or None, notes.strip())
    with connection(db_path) as db:
        if item_id:
            db.execute("""UPDATE assets SET name=?,asset_type=?,purpose=?,amount_won=?,is_liquid=?,
                   maturity_date=?,notes=? WHERE id=?""", (*args, int(item_id)))
        else:
            db.execute("""INSERT INTO assets(name,asset_type,purpose,amount_won,is_liquid,maturity_date,notes)
                VALUES(?,?,?,?,?,?,?)""", args)


def write_budget(name, expense_group, limit_won, item_id=None, db_path=None):
    if not name.strip() or limit_won < 0 or expense_group not in ("fixed", "variable"):
        raise ValueError("예산 항목을 확인해 주세요.")
    with connection(db_path) as db:
        if item_id:
            db.execute("UPDATE budgets SET name=?,expense_group=?,limit_won=? WHERE id=?",
                       (name.strip(), expense_group, int(limit_won), int(item_id)))
        else:
            db.execute("INSERT INTO budgets(name,expense_group,limit_won) VALUES(?,?,?)",
                       (name.strip(), expense_group, int(limit_won)))


def write_goal(name, target_won, months, priority=1, notes="", item_id=None, db_path=None):
    if not name.strip() or target_won <= 0 or not 1 <= months <= 360:
        raise ValueError("목표명, 목표액, 기간을 확인해 주세요.")
    args = (name.strip(), int(target_won), int(months), int(priority), notes.strip())
    with connection(db_path) as db:
        if item_id:
            db.execute("UPDATE goals SET name=?,target_won=?,months=?,priority=?,notes=? WHERE id=?",
                       (*args, int(item_id)))
        else:
            db.execute("INSERT INTO goals(name,target_won,months,priority,notes) VALUES(?,?,?,?,?)", args)


def write_transaction(booked_on, entry_type, category, amount_won, memo="", item_id=None, db_path=None):
    if isinstance(booked_on, date):
        booked_on = booked_on.isoformat()
    date.fromisoformat(str(booked_on))
    if entry_type not in ("income", "expense", "saving") or not category.strip() or amount_won <= 0:
        raise ValueError("수입/지출/저축, 분류, 금액을 확인해 주세요.")
    args = (str(booked_on), entry_type, category.strip(), int(amount_won), memo.strip())
    with connection(db_path) as db:
        if item_id:
            db.execute("UPDATE transactions SET booked_on=?,entry_type=?,category=?,amount_won=?,memo=? WHERE id=?",
                       (*args, int(item_id)))
        else:
            db.execute("INSERT INTO transactions(booked_on,entry_type,category,amount_won,memo) VALUES(?,?,?,?,?)", args)


def delete_item(table, item_id, db_path=None):
    if table not in ("assets", "budgets", "goals", "transactions"):
        raise ValueError("삭제할 수 없는 테이블")
    with connection(db_path) as db:
        db.execute(f"DELETE FROM {table} WHERE id=?", (int(item_id),))


def get_month_ledger(year, month, db_path=None):
    prefix = f"{int(year):04d}-{int(month):02d}"
    with connection(db_path) as db:
        return [dict(row) for row in db.execute(
            "SELECT * FROM transactions WHERE substr(booked_on,1,7)=? ORDER BY booked_on DESC,id DESC", (prefix,))]


def get_monthly_totals(db_path=None):
    with connection(db_path) as db:
        return [dict(row) for row in db.execute("""SELECT substr(booked_on,1,7) AS month,
           SUM(CASE WHEN entry_type='income' THEN amount_won ELSE 0 END) AS income,
           SUM(CASE WHEN entry_type='expense' THEN amount_won ELSE 0 END) AS expense,
           SUM(CASE WHEN entry_type='saving' THEN amount_won ELSE 0 END) AS saving
           FROM transactions GROUP BY substr(booked_on,1,7) ORDER BY month""")]


def backup_database(db_path=None):
    path = Path(db_path) if db_path else default_db_path()
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        tmp = Path(f.name)
    try:
        src = sqlite3.connect(str(path), timeout=30)
        dst = sqlite3.connect(str(tmp))
        try:
            src.backup(dst)
        finally:
            dst.close()
            src.close()
        return tmp.read_bytes()
    finally:
        tmp.unlink(missing_ok=True)


def csv_export(transactions):
    buffer = io.StringIO()
    fields = ["booked_on", "entry_type", "category", "amount_won", "memo"]
    writer = csv.DictWriter(buffer, fieldnames=fields)
    writer.writeheader()
    for r in transactions:
        # Prevent formula execution if opened with a spreadsheet program.
        safe = {key: str(r.get(key, "")) for key in fields}
        for key in ("category", "memo"):
            if safe[key].lstrip().startswith(("=", "+", "-", "@", "\t", "\r")):
                safe[key] = "'" + safe[key]
        writer.writerow(safe)
    return buffer.getvalue().encode("utf-8-sig")


def csv_import_preview(data: bytes):
    text = data.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))
    required = {"booked_on", "entry_type", "category", "amount_won"}
    if not required.issubset(set(reader.fieldnames or [])):
        raise ValueError("CSV 필수 열: booked_on, entry_type, category, amount_won")
    validated = []
    for i, row in enumerate(reader, start=2):
        try:
            booked = date.fromisoformat(row["booked_on"])
            entry_type = row["entry_type"].strip()
            category = row["category"].strip()
            amount = int(row["amount_won"])
            if entry_type not in ("income", "expense", "saving") or amount <= 0 or not category:
                raise ValueError("유형/금액/분류 오류")
            validated.append((booked.isoformat(), entry_type, category, amount, (row.get("memo") or "").strip()))
        except (ValueError, TypeError) as exc:
            raise ValueError(f"CSV {i}행 오류: {exc}") from exc
    return validated


def insert_transactions_batch(entries, db_path=None):
    if not entries:
        return
    with connection(db_path) as db:
        db.executemany("INSERT INTO transactions(booked_on,entry_type,category,amount_won,memo) VALUES(?,?,?,?,?)", entries)


@dataclass(frozen=True)
class Scenario:
    months: int = 48
    salary_drop_pct: float = 0
    bonus_drop_pct: float = 0
    discretionary_growth_pct: float = 0
    investment_loss_pct: float = 0
    safe_return_pct: float = 0
    risk_return_pct: float = 0
    asset_change_won: int = 0
    extra_monthly_expense_won: int = 0


@dataclass
class Forecast:
    final_won: float
    difference_won: float
    required_extra_monthly_won: float
    actual_monthly_saving_won: float
    actual_annual_extra_won: float
    monthly_expenses_won: float
    annual_income_won: float
    annual_free_cash_won: float
    emergency_months: float
    cash_deficit_annual_won: float
    series: list[dict]


def forecast(assets: list[dict], budgets: list[dict], settings: dict,
             target_won: int, scenario: Scenario) -> Forecast:
    """Deterministic forecast with cashflow-constrained saving and optional returns.

    - Investment shock happens once at t=0, only on *existing* risky assets.
    - Monthly savings are funded by post-expense *regular* salary, not bonus.
    - Year-end extra savings rely on available irregular income and overall surplus.
    - Spending increases first absorb unallocated cash, then reduce contributions.
    - Existing assets are snapshots; ledger savings never auto-add to these balances.
    - When annual income can't cover expenses, the deficit depletes assets.
    - Yearly irregular income is assumed available to smooth annual cash deficits;
      actual intra-year liquidity risk may be greater than this simple model.
    - Returns are geometric monthly compounding; no taxes, fees, inflation, or FX.
    - Unallocated positive surplus is intentionally *not* counted as invested assets.
    """
    if scenario.months < 1 or scenario.months > 360:
        raise ValueError("기간은 1~360개월로 설정해 주세요.")
    for value in (scenario.salary_drop_pct, scenario.bonus_drop_pct, scenario.investment_loss_pct):
        if not 0 <= value <= 100:
            raise ValueError("감소율과 손실률은 0~100%여야 합니다.")
    if scenario.discretionary_growth_pct < -100 or scenario.discretionary_growth_pct > 500:
        raise ValueError("선택소비 증감률은 -100~500%여야 합니다.")
    if scenario.safe_return_pct <= -100 or scenario.risk_return_pct <= -100:
        raise ValueError("수익률은 -100% 초과여야 합니다.")
    if target_won <= 0:
        raise ValueError("목표액은 0보다 커야 합니다.")

    safe = sum(float(a["amount_won"]) for a in assets if a["asset_type"] == "safe")
    risk_before = sum(float(a["amount_won"]) for a in assets if a["asset_type"] == "risk")
    risk = risk_before * (1 - scenario.investment_loss_pct / 100)
    debt = 0.0

    def withdraw(amount):
        nonlocal safe, risk, debt
        taken_from_safe = min(max(safe, 0), amount)
        safe -= taken_from_safe
        remaining = amount - taken_from_safe
        taken_from_risk = min(max(risk, 0), remaining)
        risk -= taken_from_risk
        debt += remaining - taken_from_risk

    if scenario.asset_change_won >= 0:
        safe += scenario.asset_change_won
    else:
        withdraw(-scenario.asset_change_won)

    fixed = sum(float(b["limit_won"]) for b in budgets if b["expense_group"] == "fixed")
    variable = sum(float(b["limit_won"]) for b in budgets if b["expense_group"] == "variable")
    expense_month = max(0, fixed + variable * (1 + scenario.discretionary_growth_pct / 100)
                        + scenario.extra_monthly_expense_won)
    regular_salary_month = float(settings["monthly_income"]) * (1 - scenario.salary_drop_pct / 100)
    annual_irregular = float(settings["annual_irregular_income"]) * (1 - scenario.bonus_drop_pct / 100)
    annual_income = regular_salary_month * 12 + annual_irregular
    annual_expense = expense_month * 12
    annual_capacity = annual_income - annual_expense

    # Regular salary, after expenses, is the maximum *reliable* monthly deposit.
    core_saving = min(max(0, float(settings["monthly_saving"])), max(0, regular_salary_month - expense_month))
    bonus_plan = max(0, float(settings["annual_extra_saving"])) * (1 - scenario.bonus_drop_pct / 100)
    annual_extra = min(bonus_plan, max(0, annual_capacity - 12 * core_saving))
    annual_deficit = max(0, -annual_capacity)
    deficit_month = annual_deficit / 12

    safe_growth = (1 + scenario.safe_return_pct / 100) ** (1 / 12)
    risk_growth = (1 + scenario.risk_return_pct / 100) ** (1 / 12)
    total0 = safe + risk - debt
    series = [{"month": 0, "assets_won": round(total0, 2), "safe_won": round(safe, 2),
               "risk_won": round(risk, 2), "debt_won": round(debt, 2)}]
    for month in range(1, scenario.months + 1):
        safe *= safe_growth
        risk *= risk_growth
        safe += core_saving
        if month % 12 == 0:
            safe += annual_extra
        if deficit_month:
            withdraw(deficit_month)
        series.append({"month": month, "assets_won": round(safe + risk - debt, 2),
                       "safe_won": round(safe, 2), "risk_won": round(risk, 2),
                       "debt_won": round(debt, 2)})

    final = safe + risk - debt
    diff = final - target_won
    # If monthly contributions are allocated to safe assets with returns, calculate
    # required extra fixed monthly savings by the annuity accumulation factor.
    monthly_factor = safe_growth
    if abs(monthly_factor - 1) < 1e-10:
        annuity_factor = scenario.months
    else:
        annuity_factor = (monthly_factor ** scenario.months - 1) / (monthly_factor - 1)
    top_up = max(0, -diff) / max(annuity_factor, 1e-10)

    liquid_cash = sum(float(a["amount_won"]) for a in assets
                      if a["asset_type"] == "safe" and int(a.get("is_liquid", 0)) == 1)
    emergency = liquid_cash / expense_month if expense_month > 0 else float('inf')
    return Forecast(final_won=final, difference_won=diff,
        required_extra_monthly_won=top_up, actual_monthly_saving_won=core_saving,
        actual_annual_extra_won=annual_extra, monthly_expenses_won=expense_month,
        annual_income_won=annual_income, annual_free_cash_won=annual_capacity - (core_saving * 12 + annual_extra),
        emergency_months=emergency, cash_deficit_annual_won=annual_deficit, series=series)


def current_total(assets):
    return sum(int(a["amount_won"]) for a in assets)


def financial_ratios(assets, budgets, settings):
    monthly_spend = sum(b["limit_won"] for b in budgets)
    annual_income = settings["monthly_income"] * 12 + settings["annual_irregular_income"]
    annual_spend = monthly_spend * 12
    total = current_total(assets)
    invested = sum(a["amount_won"] for a in assets if a["asset_type"] == "risk")
    liquid = sum(a["amount_won"] for a in assets if a["asset_type"] == "safe" and a["is_liquid"])
    return {
        "monthly_spend": monthly_spend,
        "annual_income": annual_income,
        "annual_spend": annual_spend,
        "annual_surplus": annual_income - annual_spend,
        "budget_spend_ratio": monthly_spend / (annual_income / 12) if annual_income else None,
        "saving_ratio": (annual_income - annual_spend) / annual_income if annual_income else None,
        "investment_ratio": invested / total if total else None,
        "emergency_months": liquid / monthly_spend if monthly_spend else None,
    }
