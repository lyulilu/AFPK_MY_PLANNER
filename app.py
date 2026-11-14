"""MY PLANNER — mobile-friendly, local-first personal finance web app.
Start with: streamlit run app.py
This app is single-user/local by design, not a cloud banking integration.
"""
from __future__ import annotations

from datetime import date, datetime
import hashlib
import hmac
from html import escape
import os
import sqlite3

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from planner_core import (
    Scenario, as_man, backup_database, connection, csv_export, csv_import_preview,
    current_total, default_db_path, delete_item, financial_ratios, forecast,
    get_month_ledger, get_monthly_totals, get_settings, initialize,
    insert_transactions_batch, manwon, rows, set_settings, to_won,
    won, write_asset, write_budget, write_goal, write_transaction,
)

st.set_page_config(page_title="MY PLANNER | 나만의 재무관리", page_icon="💠",
                   layout="wide", initial_sidebar_state="expanded")

NAVY = "#071427"
CARD = "#112640"
CYAN = "#38BDF8"
MINT = "#63E2D3"
GOLD = "#FFC876"
MUTED = "#9CB1C9"
WHITE = "#EAF4FF"
ORANGE = "#F59E83"

st.markdown("""<style>
:root { color-scheme: dark; }
html, body, [data-testid="stAppViewContainer"], .stApp {background:#071427; color:#EAF4FF;}
[data-testid="stHeader"] {background:rgba(7,20,39,.88);}
[data-testid="stSidebar"] {background:linear-gradient(180deg,#071B32,#091429);border-right:1px solid #29415A;}
.block-container {max-width:1320px;padding-top:1.7rem;padding-bottom:3.5rem;}
[data-testid="stVerticalBlockBorderWrapper"] {background:#112640;border:1px solid #29425F!important;border-radius:18px!important;}
.stButton > button[kind="primary"], [data-testid="stFormSubmitButton"] button[kind="primary"] {
  background:linear-gradient(105deg,#087CA8,#1764A5);border:1px solid #3FADD4;color:white;
  border-radius:10px;min-height:2.8rem;font-weight:650;}
.stButton > button {border-radius:10px;}
[data-testid="stMetric"] {background:#112640;border:1px solid #2B4360;border-radius:15px;padding:1.05rem 1.1rem;}
[data-testid="stMetricLabel"] {color:#9EB7CF;}
[data-testid="stMetricValue"] {color:#F2FAFF;font-weight:760;}
[data-testid="stMetricDelta"] {font-weight:650;}
[data-testid="stDataFrame"] {border-radius:12px;overflow:hidden;}
[data-testid="stSelectbox"], [data-testid="stNumberInput"], [data-testid="stTextInput"] {border-radius:9px;}
.hero {background:linear-gradient(120deg,#102F50,#091A30 68%,#0B344B);border:1px solid #29516C;
       border-radius:22px;padding:24px 27px;margin-bottom:19px;position:relative;overflow:hidden;}
.hero:after {content:"";position:absolute;right:-30px;top:-78px;width:260px;height:260px;
             border:1px solid rgba(89,204,241,.13);border-radius:50%;pointer-events:none;}
.eyebrow {color:#65CDEB;font-size:.74rem;font-weight:780;letter-spacing:.17em;margin-bottom:9px;}
.hero h1 {color:#F0F8FF;font-size:2rem;font-weight:820;margin:0 0 6px;line-height:1.25;}
.hero p {color:#B5CCE0;font-size:.93rem;max-width:830px;margin:0;line-height:1.6;}
.brand {color:#EAF8FF;font-size:1.3rem;font-weight:800;letter-spacing:.035em;margin:4px 0 8px;}
.brand .dot {color:#49C9E8}
.mini {color:#8EA8C0;font-size:.82rem;line-height:1.55;}
.callout {border-left:3px solid #42BBD7;background:#0D2740;border-radius:4px 12px 12px 4px;
          padding:11px 15px;color:#CAE0EF;font-size:.87rem;margin:12px 0;line-height:1.6;}
.pill {display:inline-block;font-weight:670;font-size:.75rem;color:#B8EFFE;background:#163D59;
       border:1px solid #286C8B;border-radius:999px;padding:5px 11px;margin:6px 0 13px;}
.sci {color:#94B4CD;font-size:.79rem;line-height:1.75;}
div[data-testid="stMarkdownContainer"] h2,div[data-testid="stMarkdownContainer"] h3 {color:#EAF4FF;}
/* 기본 테마의 검은색 본문·메뉴·입력 라벨만 흰색으로 표시 */
[data-testid="stMarkdownContainer"]:not([data-testid="stAlert"] [data-testid="stMarkdownContainer"]) > p,
[data-testid="stMarkdownContainer"]:not([data-testid="stAlert"] [data-testid="stMarkdownContainer"]) > ul,
[data-testid="stMarkdownContainer"]:not([data-testid="stAlert"] [data-testid="stMarkdownContainer"]) > ol,
[data-testid="stWidgetLabel"] p,
[data-testid="stSidebar"] [role="radiogroup"] label p,
[data-testid="stExpander"] summary p,
[data-testid="stText"] {color:#FFFFFF;}
/* 기본 테마의 진회색 보조 설명만 밝은 회색으로 표시 */
[data-testid="stCaptionContainer"],
[data-testid="stCaptionContainer"] p,
[data-testid="InputInstructions"] {color:#D1D5DB;}
@media (max-width: 680px) {
 .block-container {padding:1.05rem .9rem 2.8rem;}
 .hero {padding:20px 17px;border-radius:15px;}
 .hero h1 {font-size:1.54rem;}
 .hero p {font-size:.83rem;}
 [data-testid="stMetric"] {padding:.72rem .79rem;}
 [data-testid="stMetricValue"] {font-size:1.35rem;}
 [data-testid="stHorizontalBlock"] {gap:.65rem;flex-wrap:wrap!important;}
 [data-testid="stColumn"], [data-testid="column"] {flex:1 1 100%!important;min-width:0!important;width:100%!important;}

/* 사이드바 열기/닫기 버튼 연하늘색 */
[data-testid="stSidebarCollapsedControl"] button,
[data-testid="stSidebarCollapseButton"] button,
[data-testid="stExpandSidebarButton"] button,
button[aria-label="Open sidebar"],
button[aria-label="Close sidebar"] {
    color: #87CEFA !important;
}

[data-testid="stSidebarCollapsedControl"] svg,
[data-testid="stSidebarCollapseButton"] svg,
[data-testid="stExpandSidebarButton"] svg,
button[aria-label="Open sidebar"] svg,
button[aria-label="Close sidebar"] svg {
    color: #87CEFA !important;
    stroke: #87CEFA !important;
}

[data-testid="stSidebarCollapsedControl"] svg path,
[data-testid="stSidebarCollapseButton"] svg path,
[data-testid="stExpandSidebarButton"] svg path {
    stroke: #87CEFA !important;
}

</style>""", unsafe_allow_html=True)


def hero(kicker, title, description):
    st.markdown(f"""<div class="hero"><div class="eyebrow">{escape(kicker)}</div>
    <h1>{escape(title)}</h1><p>{escape(description)}</p></div>""", unsafe_allow_html=True)


def callout(text):
    st.markdown(f'<div class="callout">{escape(text)}</div>', unsafe_allow_html=True)


def pill(text):
    st.markdown(f'<div class="pill">{escape(text)}</div>', unsafe_allow_html=True)


def section(title, detail=None):
    st.subheader(title)
    if detail:
        st.caption(detail)


def dark_fig(fig, height=315):
    fig.update_layout(
        height=height,
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#C9DDEE", family="Arial"),
        margin=dict(l=15, r=15, t=18, b=25),
        legend=dict(orientation="h", yanchor="bottom", y=1.03, xanchor="left", x=0),
        hoverlabel=dict(bgcolor="#15334F",font_color="white"),
    )
    fig.update_xaxes(showgrid=False, zeroline=False, linecolor="#304D66")
    fig.update_yaxes(showgrid=True, gridcolor="#223B53", zeroline=False,
                     linecolor="#304D66", tickformat=",")
    return fig


def chart_forecast(base, custom=None, target_won=None):
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=[r["month"] for r in base.series],
        y=[r["assets_won"] / 10_000 for r in base.series],
        mode="lines", line=dict(color=CYAN, width=3),
        name="기본 경로", hovertemplate="%{x}개월 · %{y:,.0f}만 원<extra></extra>"))
    if custom is not None:
        fig.add_trace(go.Scatter(
            x=[r["month"] for r in custom.series],
            y=[r["assets_won"] / 10_000 for r in custom.series],
            mode="lines", line=dict(color=MINT, width=3, dash="solid"),
            name="변경 시나리오", hovertemplate="%{x}개월 · %{y:,.0f}만 원<extra></extra>"))
    if target_won is not None:
        fig.add_hline(y=target_won / 10_000, line_color="#FFC876", line_dash="dot",
                      annotation_text="목표 금액", annotation_position="top left",
                      annotation_font_color="#FFC876")
    fig.update_xaxes(title_text="경과 개월", dtick=max(6, int(max(r["month"] for r in base.series) / 6)))
    fig.update_yaxes(title_text="총 금융자산 (만 원)")
    st.plotly_chart(dark_fig(fig, 350), use_container_width=True, config={"displayModeBar": False})


def chart_pie(labels, values, colors=None):
    if not values or sum(values) <= 0:
        st.info("표시할 자산이 없습니다.")
        return
    fig = go.Figure(go.Pie(labels=labels, values=values, hole=.72,
        marker=dict(colors=colors or [CYAN,MINT,GOLD,ORANGE]),
        textinfo="percent", textfont=dict(size=13), sort=False,
        hovertemplate="%{label}: %{value:,.0f}원 (%{percent})<extra></extra>"))
    fig.update_layout(showlegend=True, legend=dict(orientation="h", y=-.08))
    st.plotly_chart(dark_fig(fig, 270), use_container_width=True, config={"displayModeBar": False})


def frame_show(frame, **kwargs):
    st.dataframe(frame, use_container_width=True, hide_index=True, **kwargs)


def authenticate():
    password = os.getenv("MY_PLANNER_PASSWORD", "").strip()
    if not password:
        return
    if st.session_state.get("authenticated", False):
        return
    hero("PRIVATE ACCESS", "MY PLANNER", "비밀번호가 설정된 개인 재무관리 공간입니다.")
    with st.form("login"):
        secret = st.text_input("접속 비밀번호", type="password")
        submitted = st.form_submit_button("로그인", type="primary", use_container_width=True)
    if submitted:
        if hmac.compare_digest(secret, password):
            st.session_state.authenticated = True
            st.rerun()
        else:
            st.error("비밀번호가 일치하지 않습니다.")
    st.stop()


def common_data():
    assets = rows("assets")
    budgets = rows("budgets")
    goals = rows("goals")
    settings = get_settings()
    return assets, budgets, goals, settings


def goal_select(goals, key):
    if not goals:
        st.warning("목표관리에서 목표를 먼저 만들어 주세요.")
        st.stop()
    goal_ids = [g["id"] for g in goals]
    selected_id = st.selectbox("분석할 목표", goal_ids,
        format_func=lambda gid: next(f'{g["name"]} · {g["months"]}개월' for g in goals if g["id"] == gid),
        key=key)
    return next(g for g in goals if g["id"] == selected_id)


def dashboard(assets, budgets, goals, settings):
    hero("YOUR FINANCIAL OVERVIEW", "안녕하세요, MY PLANNER", "오늘의 재무상태부터 미래 목표까지 한눈에 확인하세요.")
    total = current_total(assets)
    ratios = financial_ratios(assets, budgets, settings)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("현재 금융자산", manwon(total))
    c2.metric("월 계획 지출", manwon(ratios["monthly_spend"]))
    c3.metric("연간 예상 잉여자금", manwon(ratios["annual_surplus"]))
    c4.metric("비상자금 보유기간", "—" if ratios["emergency_months"] is None else f'{ratios["emergency_months"]:.1f}개월')

    a, b = st.columns([1.12, .88], gap="large")
    with a:
        section("목표 자산의 성장", "현재 자산을 기준으로 계획된 저축액을 미래에 누적합니다.")
        if goals:
            primary = goals[0]
            base = forecast(assets,budgets,settings,primary["target_won"],
                Scenario(months=primary["months"],safe_return_pct=settings["safe_return_pct"],
                         risk_return_pct=settings["risk_return_pct"]))
            chart_forecast(base, target_won=primary["target_won"])
            delta_value = base.difference_won
            arrow = "▲" if delta_value >= 0 else "▼"
            arrow_color = "#00A36C" if delta_value >= 0 else "#FF6B6B"
            st.markdown(
                f"""
                <div style="background:#112640;border:1px solid #2B4360;
                            border-radius:15px;padding:1.05rem 1.1rem;">
                    <div style="color:#9EB7CF;font-size:0.875rem;">
                        「{escape(primary['name'])}」 예상 달성액
                    </div>
                    <div style="color:#F2FAFF;font-size:2rem;font-weight:760;">
                        {escape(manwon(base.final_won))}
                    </div>
                    <div style="margin-top:5px;font-size:0.875rem;">
                        <span style="color:{arrow_color};">{arrow}</span>
                        <span style="color:#000000;background:#DDF8ED;
                                     border-radius:5px;padding:2px 5px;">
                            목표 대비 {escape(manwon(delta_value))}
                        </span>
                    </div>
                </div>
                """,
                unsafe_allow_html=True
            )
            checkpoints = [m for m in range(12, primary["months"] + 1, 12)]
            if primary["months"] not in checkpoints:
                checkpoints.append(primary["months"])
            with st.expander("연차별 목표자산 경로 확인"):
                frame_show(pd.DataFrame([{
                    "시점": f"{m}개월 후",
                    "누적 예상 자산 (만 원)": round(as_man(base.series[m]["assets_won"]), 1),
                    "목표액 대비": f'{base.series[m]["assets_won"] / primary["target_won"] * 100:.1f}%',
                } for m in checkpoints]))
        else:
            st.info("목표를 등록하면 성장 전망을 확인할 수 있습니다.")
    with b:
        section("보유 자산 구성", "투자 위험과 인출 가능 자금을 구분합니다.")
        safe = sum(a["amount_won"] for a in assets if a["asset_type"] == "safe")
        risk = total - safe
        chart_pie(["안전자산", "투자자산"], [safe, risk])
        a1, a2 = st.columns(2)
        a1.metric("안전자산",manwon(safe))
        a2.metric("투자자산",manwon(risk))

    section("재무 건강 지표", "계획 금액 기반의 참고 지표입니다. 실제 지출은 가계부에서 별도 집계됩니다.")
    r1, r2, r3 = st.columns(3)
    r1.metric("지출 비율", "—" if ratios["budget_spend_ratio"] is None else f'{ratios["budget_spend_ratio"]*100:.1f}%')
    r2.metric("잉여자금 비율", "—" if ratios["saving_ratio"] is None else f'{ratios["saving_ratio"]*100:.1f}%')
    r3.metric("투자자산 비중", "—" if ratios["investment_ratio"] is None else f'{ratios["investment_ratio"]*100:.1f}%')
    if ratios["emergency_months"] is not None and ratios["emergency_months"] < 3:
        st.warning("비상자금이 계획 지출 3개월분에 미달합니다. 인출 가능한 안전자산을 확인하세요.")
    if goals and total > 0 and base.final_won < goals[0]["target_won"]:
        st.info("현재 계획에서는 목표금액이 부족할 수 있습니다. 시뮬레이션에서 추가저축액을 확인하세요.")
    # Three consecutive *completed* months below the regular saving plan.
    # The alert appears only when each month has at least one recorded entry.
    today = date.today()
    recent = []
    for shift in (3, 2, 1):
        y = today.year
        m = today.month - shift
        while m <= 0:
            y -= 1
            m += 12
        recent.append(get_month_ledger(y, m))
    if settings["monthly_saving"] > 0 and all(recent):
        core_saved = [sum(t["amount_won"] for t in month
                         if t["entry_type"] == "saving" and t["category"] == "정기저축")
                      for month in recent]
        if all(actual < settings["monthly_saving"] for actual in core_saved):
            st.warning("최근 3개 완료 월의 정기저축 기록이 모두 계획액보다 적습니다. 저축 이행률과 자산계획을 재점검하세요.")
    callout("처음 시작하면 편집 가능한 가상 예시값이 나타납니다. 거래내역은 비어 있으며, 자산 장부와 가계부는 자동으로 중복 합산되지 않습니다.")


def ledger(assets, budgets, goals, settings):
    hero("DAILY MONEY JOURNAL", "가계부", "수입·지출·저축을 기록하고 월별 소비 예산을 관리하세요.")
    types = {"expense": "지출", "income": "수입", "saving": "저축"}
    section("새로운 거래 기록")
    entry_type = st.segmented_control("거래 유형", options=["expense", "income", "saving"],
                   format_func=lambda t: types[t], default="expense", key="new_entry_type")
    if entry_type is None:
        entry_type = "expense"
    if entry_type == "expense":
        choices = [b["name"] for b in budgets] + ["기타 지출"]
    elif entry_type == "income":
        choices = ["정기급여", "성과급·비정기소득", "기타 수입"]
    else:
        choices = ["정기저축", "추가저축", "기타 저축"]
    with st.form(f"new_entry_{entry_type}", clear_on_submit=True):
        c1,c2,c3 = st.columns([1,1,1])
        booked_on = c1.date_input("날짜", value=date.today())
        category = c2.selectbox("항목", choices)
        amount = c3.number_input("금액 (원)", min_value=1, value=20_000, step=1_000)
        memo = st.text_input("메모 (선택)", placeholder="예: 점심 식사")
        sent = st.form_submit_button("거래 저장", type="primary", use_container_width=True)
    if sent:
        write_transaction(booked_on, entry_type, category, int(amount), memo)
        st.success("거래를 저장했습니다.")
        st.rerun()

    today = date.today()
    filter_a, filter_b = st.columns(2)
    year = filter_a.selectbox("조회 연도", list(range(today.year+1, today.year-7,-1)),
                               index=1, key="ledger_year")
    month = filter_b.selectbox("조회 월", list(range(1,13)), index=today.month-1, key="ledger_month")
    current = get_month_ledger(year,month)
    income = sum(x["amount_won"] for x in current if x["entry_type"]=="income")
    expense = sum(x["amount_won"] for x in current if x["entry_type"]=="expense")
    savings = sum(x["amount_won"] for x in current if x["entry_type"]=="saving")
    c1,c2,c3,c4 = st.columns(4)
    c1.metric("기록된 수입",won(income))
    c2.metric("기록된 지출",won(expense))
    c3.metric("기록된 저축",won(savings))
    c4.metric("기록상 잔여",won(income-expense-savings))
    if income == 0 and current:
        st.caption("해당 월 수입이 아직 입력되지 않았을 수 있습니다. 잔여금은 입력된 내역 기준입니다.")

    section("월별 예산 vs 실제 지출")
    budget_data=[]
    for b in budgets:
        spent = sum(x["amount_won"] for x in current if x["entry_type"]=="expense" and x["category"]==b["name"])
        budget_data.append({"항목":b["name"],"분류":"고정" if b["expense_group"]=="fixed" else "선택",
                           "월 예산 (원)":b["limit_won"],"실제 지출 (원)":spent,"잔여 예산 (원)":b["limit_won"]-spent})
    if budget_data:
        frame_show(pd.DataFrame(budget_data), column_config={
            "월 예산 (원)":st.column_config.NumberColumn(format="%,d"),
            "실제 지출 (원)":st.column_config.NumberColumn(format="%,d"),
            "잔여 예산 (원)":st.column_config.NumberColumn(format="%,d")})
        if any(x["잔여 예산 (원)"] < 0 for x in budget_data):
            st.warning("일부 소비 항목에서 예산을 초과했습니다. 예산 항목 관리에서 계획을 조정할 수 있습니다.")
    uncategorized = sum(x["amount_won"] for x in current if x["entry_type"]=="expense" and x["category"] not in {b["name"] for b in budgets})
    if uncategorized:
        st.caption(f"예산 항목 외 기타 지출: {won(uncategorized)} (비교 표에는 포함되지 않음)")

    section("거래 내역")
    if current:
        tx_df = pd.DataFrame([{"ID":x["id"],"날짜":x["booked_on"],"유형":types[x["entry_type"]],
                               "항목":x["category"],"금액 (원)":x["amount_won"],"메모":x["memo"]} for x in current])
        frame_show(tx_df)
        with st.expander("선택한 거래 수정 / 삭제"):
            options = {x["id"]:f'{x["booked_on"]} · {types[x["entry_type"]]} · {x["category"]} · {won(x["amount_won"])}' for x in current}
            selected = st.selectbox("거래 선택",list(options),format_func=lambda i:options[i])
            item = next(x for x in current if x["id"]==selected)
            with st.form(f"tx_edit_{selected}"):
                c1,c2,c3 = st.columns(3)
                d = c1.date_input("날짜", date.fromisoformat(item["booked_on"]))
                t = c2.selectbox("유형",list(types),index=list(types).index(item["entry_type"]),format_func=lambda k:types[k])
                amt = c3.number_input("금액 (원)",min_value=1,value=item["amount_won"],step=1_000)
                cat = st.text_input("항목",value=item["category"])
                memo = st.text_input("메모",value=item["memo"])
                save = st.form_submit_button("수정 저장",type="primary")
            if save:
                try:
                    write_transaction(d,t,cat,amt,memo,item_id=selected)
                    st.rerun()
                except ValueError as exc:
                    st.error(str(exc))
            confirm = st.checkbox("선택한 거래 삭제 확인",key=f"tx_confirm_{selected}")
            if st.button("거래 삭제",disabled=not confirm,key=f"tx_delete_{selected}"):
                delete_item("transactions",selected)
                st.rerun()
    else:
        st.info("선택한 월에 기록된 거래가 없습니다. 위에서 첫 거래를 추가해 보세요.")

    section("월별 가계부 흐름")
    monthly = get_monthly_totals()
    if monthly:
        frame = pd.DataFrame(monthly)
        fig = go.Figure()
        for field,color,label in [("income",CYAN,"수입"),("expense",ORANGE,"지출"),("saving",MINT,"저축")]:
            fig.add_trace(go.Bar(x=frame["month"],y=frame[field]/10_000,
                      name=label,marker_color=color))
        fig.update_layout(barmode="group")
        fig.update_yaxes(title_text="만 원")
        st.plotly_chart(dark_fig(fig,290),use_container_width=True,config={"displayModeBar":False})

    with st.expander("CSV 내보내기 / 불러오기"):
        st.download_button("전체 거래 CSV 다운로드",csv_export(rows("transactions")),
            file_name="my_planner_transactions.csv",mime="text/csv",use_container_width=True)
        uploaded = st.file_uploader("CSV 거래내역 업로드",type=["csv"], key="ledger_import")
        if uploaded:
            try:
                pending = csv_import_preview(uploaded.getvalue())
                st.caption(f"검증 완료: {len(pending)}건. 아래 확인 버튼을 누르면 기존 내역에 추가됩니다.")
                st.dataframe(pd.DataFrame(pending[:15],columns=["날짜","유형","항목","금액(원)","메모"]),hide_index=True)
                sure = st.checkbox("중복 거래가 생길 수 있음을 확인했습니다.",key="csv_confirm")
                if st.button("CSV 거래 추가",disabled=not sure):
                    insert_transactions_batch(pending)
                    st.success(f"{len(pending)}건을 추가했습니다.")
                    st.rerun()
            except (UnicodeDecodeError, ValueError) as exc:
                st.error(f"파일 검증 실패: {exc}")
    callout("가계부의 '저축'은 지출이 아닌 별도 이행 기록입니다. 자동이체나 자산 이동이 자산 장부에 자동 반영되지는 않으므로, 보유 자산 평가액은 자산관리에서 갱신해 주세요.")


def assets_page(assets, budgets, goals, settings):
    hero("ASSET PORTFOLIO", "자산관리", "계좌별 자산 규모, 투자 위험, 만기 및 유동성을 직접 관리하세요.")
    total=current_total(assets)
    safe=sum(a["amount_won"] for a in assets if a["asset_type"]=="safe")
    emergency=sum(a["amount_won"] for a in assets if a["asset_type"]=="safe" and a["is_liquid"])
    x,y,z=st.columns(3)
    x.metric("총 금융자산",manwon(total))
    y.metric("안전자산 비중","—" if total==0 else f"{safe/total*100:.1f}%")
    z.metric("즉시 인출 가능 안전자산",manwon(emergency))
    if assets:
        frame_show(pd.DataFrame([{
            "ID":a["id"],"자산명":a["name"],"종류":"안전자산" if a["asset_type"]=="safe" else "투자자산",
            "목적":{"emergency":"비상예비","goal":"목표자금","long":"장기투자","other":"기타"}[a["purpose"]],
            "현재 평가액 (원)":a["amount_won"],"즉시 인출 가능한 안전자산":bool(a["is_liquid"] and a["asset_type"]=="safe"),
            "만기":a["maturity_date"] or "—"} for a in assets]))

    st.subheader("자산 추가")
    purpose_map={"emergency":"비상예비자금","goal":"목표자금","long":"장기투자자금","other":"기타"}
    with st.form("asset_add",clear_on_submit=True):
        a,b=st.columns(2)
        name=a.text_input("자산명",placeholder="예: 국민은행 예금")
        amount=b.number_input("현재 평가액 (만 원)",min_value=0.0,value=0.0,step=10.0,format="%.1f")
        a,b=st.columns(2)
        kind=a.selectbox("자산 유형",["safe","risk"],format_func=lambda k:{"safe":"안전자산","risk":"투자자산"}[k])
        purpose=b.selectbox("자산의 목적",list(purpose_map),format_func=lambda k:purpose_map[k])
        liquid=st.checkbox("즉시 인출 가능한 안전자산으로 분류 (비상자금 계산에 포함)")
        c,d=st.columns(2)
        maturity=c.text_input("만기일 (선택, YYYY-MM-DD)")
        notes=d.text_input("메모 (선택)")
        sent=st.form_submit_button("자산 추가",type="primary",use_container_width=True)
    if sent:
        try:
            if maturity:
                date.fromisoformat(maturity)
            write_asset(name,kind,purpose,to_won(amount),liquid,maturity,notes)
            st.rerun()
        except ValueError as exc:
            st.error(f"입력 오류: {exc}")

    if assets:
        with st.expander("기존 자산 수정 / 삭제"):
            choices={a["id"]:f'{a["name"]} ({manwon(a["amount_won"])})' for a in assets}
            selected=st.selectbox("수정할 자산",list(choices),format_func=lambda i:choices[i])
            item=next(a for a in assets if a["id"]==selected)
            with st.form(f"asset_edit_{selected}"):
                a,b=st.columns(2)
                name=a.text_input("자산명",item["name"])
                amount=b.number_input("평가액 (만 원)",min_value=0.0,value=as_man(item["amount_won"]),step=10.0,format="%.2f")
                a,b=st.columns(2)
                kind=a.selectbox("자산 유형",["safe","risk"],index=["safe","risk"].index(item["asset_type"]),format_func=lambda k:{"safe":"안전자산","risk":"투자자산"}[k])
                purpose=b.selectbox("목적",list(purpose_map),index=list(purpose_map).index(item["purpose"]),format_func=lambda k:purpose_map[k])
                liquid=st.checkbox("즉시 인출 가능한 안전자산",value=bool(item["is_liquid"]))
                maturity=st.text_input("만기일 (선택)",item["maturity_date"] or "")
                notes=st.text_input("메모",item["notes"])
                save=st.form_submit_button("수정 저장",type="primary")
            if save:
                try:
                    if maturity:
                        date.fromisoformat(maturity)
                    write_asset(name,kind,purpose,to_won(amount),liquid,maturity,notes,item_id=selected)
                    st.rerun()
                except ValueError as exc:
                    st.error(str(exc))
            confirm=st.checkbox("삭제를 확인했습니다.",key=f"asset_del_check_{selected}")
            if st.button("자산 삭제",disabled=not confirm,key=f"asset_del_{selected}"):
                delete_item("assets",selected)
                st.rerun()
    callout("초기 예시의 안전자산 3,500만 원 중 비상예비자금 1,000만 원만 인출 가능 자금으로 설정했습니다. 나머지 세부 상품 잔액과 만기일은 사용자가 직접 확인하여 수정해야 합니다.")


def budgets_page(assets,budgets,goals,settings):
    hero("SPENDING PLAN", "예산관리", "내 소비의 우선순위에 맞춰 월별 소비 한도를 만들고 조정하세요.")
    fixed=sum(b["limit_won"] for b in budgets if b["expense_group"]=="fixed")
    variable=sum(b["limit_won"] for b in budgets if b["expense_group"]=="variable")
    p,q,r=st.columns(3)
    p.metric("월 고정소비 계획",manwon(fixed))
    q.metric("월 선택소비 계획",manwon(variable))
    r.metric("월 합계",manwon(fixed+variable))
    section("항목별 월 예산")
    if budgets:
        frame_show(pd.DataFrame([{"ID":b["id"],"예산 항목":b["name"],
                                  "분류":"고정 소비" if b["expense_group"]=="fixed" else "선택 소비",
                                  "월 예산 (원)":b["limit_won"]} for b in budgets]))
    with st.form("budget_add", clear_on_submit=True):
        a,b,c=st.columns(3)
        name=a.text_input("항목명",placeholder="예: 카페 · 디저트")
        group=b.selectbox("분류",["variable","fixed"],format_func=lambda k:{"fixed":"고정 소비","variable":"선택 소비"}[k])
        limit=c.number_input("월 예산 (만 원)",min_value=0.0,value=0.0,step=1.0,format="%.1f")
        sent=st.form_submit_button("예산 항목 추가",type="primary")
    if sent:
        try:
            write_budget(name,group,to_won(limit))
            st.rerun()
        except (ValueError,sqlite3.IntegrityError) as exc:
            st.error(f"등록 실패: {exc}")
    if budgets:
        with st.expander("예산 수정 / 삭제"):
            choices={b["id"]:b["name"] for b in budgets}
            selected=st.selectbox("대상 예산",list(choices),format_func=lambda i:choices[i])
            item=next(b for b in budgets if b["id"]==selected)
            with st.form(f"budget_edit_{selected}"):
                name=st.text_input("예산 항목",item["name"])
                a,b=st.columns(2)
                kind=a.selectbox("분류",["fixed","variable"],index=["fixed","variable"].index(item["expense_group"]),format_func=lambda k:{"fixed":"고정 소비","variable":"선택 소비"}[k])
                amount=b.number_input("월 예산 (만 원)",min_value=0.0,value=as_man(item["limit_won"]),step=1.0,format="%.2f")
                save=st.form_submit_button("수정 저장",type="primary")
            if save:
                try:
                    write_budget(name,kind,to_won(amount),item_id=selected)
                    st.rerun()
                except (ValueError,sqlite3.IntegrityError) as exc:
                    st.error(str(exc))
            sure=st.checkbox("삭제 확인",key=f"budget_sure_{selected}")
            if st.button("예산 항목 삭제",disabled=not sure,key=f"budget_del_{selected}"):
                delete_item("budgets",selected)
                st.rerun()
    callout("예산 항목을 수정하면 대시보드의 월 지출 및 시뮬레이션 현금흐름 가정도 즉시 바뀝니다. 이전에 작성한 거래의 항목명은 자동 변경되지 않습니다.")


def goals_page(assets,budgets,goals,settings):
    hero("GOALS & MILESTONES", "목표관리", "결혼·주거·여행·비상자금 등 나만의 재무 목표를 설정하세요.")
    if goals:
        frame_show(pd.DataFrame([{"ID":g["id"],"목표":g["name"],"목표액 (원)":g["target_won"],
                                  "기간 (개월)":g["months"],"우선순위":g["priority"]} for g in goals]))
        section("목표별 달성 전망", "다른 목표끼리 자산을 중복 배정하지 않도록, 아래 전망은 각각 독립적인 비교 참고치입니다.")
        for g in goals:
            result=forecast(assets,budgets,settings,g["target_won"],
                            Scenario(months=g["months"],safe_return_pct=settings["safe_return_pct"],risk_return_pct=settings["risk_return_pct"]))
            with st.container(border=True):
                st.markdown(f'**{escape(g["name"])}** · {g["months"]}개월 후')
                c1,c2,c3=st.columns(3)
                c1.metric("목표",manwon(g["target_won"]))
                c2.metric("예상 금융자산",manwon(result.final_won))
                c3.metric("차이",manwon(result.difference_won))
                pct=max(0,min(1,result.final_won/g["target_won"]))
                st.progress(pct, text=f"목표 대비 예상 자산 {result.final_won/g['target_won']*100:.1f}%")
    section("새 목표 추가")
    with st.form("goal_add",clear_on_submit=True):
        a,b=st.columns(2)
        name=a.text_input("목표명",placeholder="예: 5년 뒤 전세자금")
        target=b.number_input("목표 금액 (만 원)",min_value=1.0,value=1000.0,step=100.0)
        c,d=st.columns(2)
        months=c.number_input("목표까지 남은 개월 수",min_value=1,max_value=360,value=36,step=1)
        priority=d.number_input("우선순위 (1이 가장 높음)",min_value=1,max_value=99,value=2,step=1)
        notes=st.text_input("메모 (선택)")
        sent=st.form_submit_button("목표 추가",type="primary")
    if sent:
        try:
            write_goal(name,to_won(target),months,priority,notes)
            st.rerun()
        except ValueError as exc:
            st.error(str(exc))
    if goals:
        with st.expander("기존 목표 수정 / 삭제"):
            choices={g["id"]:g["name"] for g in goals}
            selected=st.selectbox("목표 선택",list(choices),format_func=lambda i:choices[i])
            item=next(g for g in goals if g["id"]==selected)
            with st.form(f"goal_edit_{selected}"):
                a,b=st.columns(2)
                name=a.text_input("목표명",item["name"])
                target=b.number_input("목표액 (만 원)",min_value=1.0,value=as_man(item["target_won"]),step=100.0)
                c,d=st.columns(2)
                months=c.number_input("남은 기간 (개월)",min_value=1,max_value=360,value=item["months"])
                priority=d.number_input("우선순위",min_value=1,max_value=99,value=item["priority"])
                notes=st.text_input("메모",item["notes"])
                save=st.form_submit_button("수정 저장",type="primary")
            if save:
                try:
                    write_goal(name,to_won(target),months,priority,notes,item_id=selected)
                    st.rerun()
                except ValueError as exc:
                    st.error(str(exc))
            sure=st.checkbox("삭제 확인",key=f"goal_sure_{selected}")
            if st.button("목표 삭제",disabled=not sure,key=f"goal_del_{selected}"):
                delete_item("goals",selected)
                st.rerun()
    callout("목표마다 별도 자금을 자동 배정하지는 않습니다. 2개 이상의 목표를 동시에 달성하는 통합 자금계획은 각 목표에 같은 자산을 중복 계산하지 않도록 별도로 점검해야 합니다.")


def simulator(assets,budgets,goals,settings):
    hero("WHAT-IF LAB", "자산 변동 시뮬레이션", "소득 감소, 소비 증가, 투자 손실, 목표 시점 변경을 조합해 미래를 계산하세요.")
    goal=goal_select(goals,"sim_selected_goal")
    base=forecast(assets,budgets,settings,goal["target_won"],Scenario(
         months=goal["months"],safe_return_pct=settings["safe_return_pct"],risk_return_pct=settings["risk_return_pct"]))
    with st.expander("시뮬레이션 조건 수정",expanded=True):
        a,b=st.columns(2)
        months=a.number_input("목표까지 기간 (개월)",min_value=1,max_value=360,value=goal["months"],step=1)
        salary_drop=b.slider("월 정기급여 감소율 (%)",min_value=0,max_value=100,value=0,step=5)
        a,b=st.columns(2)
        bonus_drop=a.slider("비정기소득 및 연간 추가저축 감소율 (%)",0,100,0,5)
        consumption=b.slider("선택 소비 증감률 (%)",-100,200,0,5)
        a,b=st.columns(2)
        loss=a.slider("현재 투자자산 1회성 손실률 (%)",0,100,0,5)
        extra_expense=b.number_input("추가 월 지출 (만 원)",min_value=0.0,value=0.0,step=5.0)
        a,b=st.columns(2)
        safe_rate=a.number_input("안전자산 연 수익률 (%)",min_value=-50.0,max_value=50.0,value=float(settings["safe_return_pct"]),step=.5,format="%.1f")
        risk_rate=b.number_input("투자자산 연 수익률 (%)",min_value=-80.0,max_value=80.0,value=float(settings["risk_return_pct"]),step=1.0,format="%.1f")
        change=st.number_input("현재 자산 1회성 변동 (만 원, +/-)",min_value=-100_000.0,max_value=100_000.0,value=0.0,step=100.0)
    scenario=Scenario(
        months=int(months),salary_drop_pct=salary_drop,bonus_drop_pct=bonus_drop,
        discretionary_growth_pct=consumption,investment_loss_pct=loss,
        safe_return_pct=safe_rate,risk_return_pct=risk_rate,
        asset_change_won=to_won(change),extra_monthly_expense_won=to_won(extra_expense))
    result=forecast(assets,budgets,settings,goal["target_won"],scenario)
    good=result.difference_won>=0
    pill("목표 달성 예상" if good else "목표 부족 예상")
    c1,c2,c3,c4=st.columns(4)
    c1.metric("변경 후 예상 금융자산",manwon(result.final_won))
    c2.metric("목표 대비 차이",manwon(result.difference_won))
    c3.metric("회복에 필요한 추가 월저축",manwon(result.required_extra_monthly_won,1))
    c4.metric("실행 가능 월 정기저축",manwon(result.actual_monthly_saving_won,1))
    if result.required_extra_monthly_won > 0:
        st.warning("추가 월저축액은 변경된 가정에서 목표 부족분을 메우는 단순 계산치입니다. 현재 현금흐름으로 실행 가능한지는 별도 확인이 필요합니다.")
    chart_forecast(base,result,target_won=goal["target_won"])
    section("현금흐름을 반영한 실행 가능성")
    z1,z2,z3=st.columns(3)
    z1.metric("변경된 월 소비",manwon(result.monthly_expenses_won,1))
    z2.metric("연간 비정기 추가저축",manwon(result.actual_annual_extra_won,1))
    z3.metric("연간 계획 외 여유금",manwon(result.annual_free_cash_won,1))
    if result.cash_deficit_annual_won:
        st.error(f"수입보다 지출이 연간 {manwon(result.cash_deficit_annual_won)} 많아, 초과분이 보유 자산에서 차감됩니다.")
    if result.actual_monthly_saving_won+1 < settings["monthly_saving"]:
        st.warning("정기급여에서 지출을 차감한 돈이 목표 월저축액보다 작아, 시뮬레이션이 실제 월저축액을 줄였습니다.")
    with st.expander("대표 위험 시나리오 비교"):
        candidates=[
            ("기본",Scenario(months=goal["months"],safe_return_pct=settings["safe_return_pct"],risk_return_pct=settings["risk_return_pct"])),
            ("A · 성과급 미지급",Scenario(months=goal["months"],bonus_drop_pct=100,safe_return_pct=settings["safe_return_pct"],risk_return_pct=settings["risk_return_pct"])),
            ("B · 선택소비 20% 증가",Scenario(months=goal["months"],discretionary_growth_pct=20,safe_return_pct=settings["safe_return_pct"],risk_return_pct=settings["risk_return_pct"])),
            ("C · 투자자산 20% 손실",Scenario(months=goal["months"],investment_loss_pct=20,safe_return_pct=settings["safe_return_pct"],risk_return_pct=settings["risk_return_pct"])),
            ("D · 목표기간 12개월 단축",Scenario(months=max(1,goal["months"]-12),safe_return_pct=settings["safe_return_pct"],risk_return_pct=settings["risk_return_pct"])),
        ]
        results=[]
        for label,case in candidates:
            sim=forecast(assets,budgets,settings,goal["target_won"],case)
            results.append({"시나리오":label,"기간 (개월)":case.months,"예상 자산 (만 원)":round(as_man(sim.final_won),1),
                            "목표 차이 (만 원)":round(as_man(sim.difference_won),1)})
        frame_show(pd.DataFrame(results))
        st.caption("시나리오 비교는 현재 수정된 자산·예산·저축계획을 기준으로 다시 계산됩니다. 최초 예시값과 다를 수 있습니다.")
    callout("계산 구조: 현재 안전·투자자산 + 실행 가능한 월저축액 + 매년 말 추가저축 + 가정 수익/손실 − 현금흐름 적자. 투자손실은 시작 시 한 번만 적용하고, 가계부 거래를 자산에 자동 더하지 않습니다. 이자·세금·수수료·물가·금융상품별 조건은 별도 반영하지 않습니다.")


def settings_page(assets,budgets,goals,settings):
    hero("PLAN CONFIGURATION", "기본 재무계획", "미래 재무 전망에 적용되는 소득, 저축액, 수익률을 편집하세요.")
    with st.form("settings_update"):
        a,b=st.columns(2)
        income=a.number_input("월 정기급여 (만 원)",min_value=0.0,value=as_man(settings["monthly_income"]),step=10.0,format="%.2f")
        irregular=b.number_input("연간 비정기소득 (만 원)",min_value=0.0,value=as_man(settings["annual_irregular_income"]),step=10.0,format="%.2f")
        a,b=st.columns(2)
        monthly=a.number_input("월 정기저축 계획 (만 원)",min_value=0.0,value=as_man(settings["monthly_saving"]),step=10.0,format="%.2f")
        extra=b.number_input("연간 추가저축 계획 (만 원)",min_value=0.0,value=as_man(settings["annual_extra_saving"]),step=10.0,format="%.2f")
        a,b=st.columns(2)
        safe=a.number_input("기본 안전자산 연 수익률 (%)",min_value=-50.0,max_value=50.0,value=float(settings["safe_return_pct"]),step=.5,format="%.1f")
        risk=b.number_input("기본 투자자산 연 수익률 (%)",min_value=-80.0,max_value=80.0,value=float(settings["risk_return_pct"]),step=1.0,format="%.1f")
        save=st.form_submit_button("계획 저장",type="primary",use_container_width=True)
    if save:
        set_settings({"monthly_income":to_won(income),"annual_irregular_income":to_won(irregular),
                      "monthly_saving":to_won(monthly),"annual_extra_saving":to_won(extra),
                      "safe_return_pct":safe,"risk_return_pct":risk})
        st.success("재무계획이 저장됐습니다.")
        st.rerun()
    st.markdown("**예산 계산 안내**")
    st.info("고정소비와 선택소비는 ‘예산관리’에서 편집합니다. 시뮬레이션의 월 지출은 항목별 월 예산을 합산해 계산합니다.")
    section("데이터 백업", "데이터는 실행 중인 컴퓨터/서버의 SQLite 파일에 저장됩니다.")
    st.download_button("전체 데이터베이스 백업 (.db)",data=backup_database(),
        file_name=f"my_planner_backup_{date.today().isoformat()}.db",
        mime="application/octet-stream",use_container_width=True)
    st.caption("복원할 때는 앱을 종료한 뒤 data/my_planner.db 파일을 백업 .db 파일로 교체하세요. 복원 전에 원본을 별도 보관하세요.")
    with st.expander("개인정보·사용 제한 및 데이터 경로"):
        st.code(str(default_db_path()))
        st.markdown("""- 로그인 기능은 `MY_PLANNER_PASSWORD` 환경변수를 설정했을 때만 작동합니다.
- **단일 사용자 로컬 앱**입니다. 여러 사람이 같은 주소에 접속하면 같은 재무정보가 보일 수 있습니다.
- 정식 공개 서비스에는 사용자별 로그인, 암호화, 서버 측 권한 분리, HTTPS 및 백업 정책이 추가로 필요합니다.
- 실제 금융계좌와 자동 연동되지 않습니다. 개인정보가 포함된 DB를 공개 저장소에 올리지 마세요.""")


def main():
    initialize()
    authenticate()
    with st.sidebar:
        st.markdown('<div class="brand">✦ MY <span class="dot">PLANNER</span></div>',unsafe_allow_html=True)
        st.markdown('<div class="mini">나의 소비와 미래를 연결하는<br>스마트 재무관리 공간</div>',unsafe_allow_html=True)
        st.divider()
        navigation={
            "대시보드":"📊", "가계부":"🧾", "자산관리":"💎",
            "예산관리":"🎛️", "목표관리":"🎯", "시뮬레이션":"📈", "기본 설정":"⚙️",
        }
        tab=st.radio("메뉴",list(navigation),format_func=lambda k:f'{navigation[k]}  {k}',label_visibility="collapsed")
        st.divider()
        st.caption("MY PLANNER · 개인용 로컬 버전")
        st.caption("금융정보는 사용자가 직접 입력하며, 계산 결과는 참고용입니다.")
        if os.getenv("MY_PLANNER_PASSWORD", "").strip() and st.button("로그아웃"):
            st.session_state.authenticated=False
            st.rerun()
    assets,budgets,goals,settings=common_data()
    try:
        if tab=="대시보드": dashboard(assets,budgets,goals,settings)
        elif tab=="가계부": ledger(assets,budgets,goals,settings)
        elif tab=="자산관리": assets_page(assets,budgets,goals,settings)
        elif tab=="예산관리": budgets_page(assets,budgets,goals,settings)
        elif tab=="목표관리": goals_page(assets,budgets,goals,settings)
        elif tab=="시뮬레이션": simulator(assets,budgets,goals,settings)
        else: settings_page(assets,budgets,goals,settings)
    except (sqlite3.DatabaseError, ValueError) as exc:
        st.error(f"처리할 수 없는 입력 또는 데이터베이스 오류: {exc}")


if __name__=="__main__":
    main()
