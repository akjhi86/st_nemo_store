import streamlit as st
import pandas as pd
import sqlite3
import os
import re
import json
import plotly.express as px
import plotly.graph_objects as go

# ----------------------------------------------------------
# 1. 페이지 설정 및 디자인
# ----------------------------------------------------------
st.set_page_config(page_title="Nemostore Pro Dashboard v2.1", layout="wide")

# Neo Brutalism & Premium CSS
st.markdown("""
    <style>
    .stApp { background-color: #F8F9FB; }
    .property-card {
        background-color: white;
        border: 2px solid #000;
        box-shadow: 4px 4px 0px #000;
        padding: 15px;
        border-radius: 8px;
        margin-bottom: 20px;
        transition: transform 0.2s;
        cursor: pointer;
    }
    .property-card:hover {
        transform: translate(-2px, -2px);
        box-shadow: 6px 6px 0px #000;
    }
    .price-tag {
        font-size: 1.2rem;
        font-weight: 800;
        color: #1E1E1E;
    }
    .status-badge {
        display: inline-block;
        padding: 2px 8px;
        border: 1px solid #000;
        border-radius: 4px;
        font-size: 0.7rem;
        font-weight: bold;
        background-color: #FFE600;
    }
    .example-tag {
        display: inline-block;
        padding: 2px 10px;
        margin: 2px;
        background-color: #E0E0E0;
        border-radius: 20px;
        font-size: 0.8rem;
        cursor: pointer;
        border: 1px solid #CCC;
    }
    .benchmarking-plus { color: #D32F2F; font-weight: bold; }
    .benchmarking-minus { color: #388E3C; font-weight: bold; }
    .detail-row {
        background-color: #FFFFFF;
        border: 3px solid #000;
        padding: 25px;
        border-radius: 12px;
        margin-top: 30px;
        box-shadow: 8px 8px 0px #000;
    }
    </style>
""", unsafe_allow_html=True)

# ----------------------------------------------------------
# 2. 데이터 로드 및 전처리
# ----------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "data", "nemostore.db")

COL_MAPPING = {
    "title": "매물명",
    "businessMiddleCodeName": "업종",
    "deposit": "보증금(만)",
    "monthlyRent": "월세(만)",
    "premium": "권리금(만)",
    "maintenanceFee": "관리비(만)",
    "size_pyeong": "면적(평)",
    "floor_label": "층수",
    "subway_name": "인근역",
    "walk_min": "도보(분)",
    "viewCount": "조회수",
    "favoriteCount": "관심수"
}

SUBWAY_COORDS = {
    "종각역": {"lat": 37.5701, "lon": 126.9829},
    "을지로입구역": {"lat": 37.5660, "lon": 126.9821},
    "종로3가역": {"lat": 37.5704, "lon": 126.9921},
    "시청역": {"lat": 37.5657, "lon": 126.9769},
    "광화문역": {"lat": 37.5709, "lon": 126.9761},
    "을지로3가역": {"lat": 37.5662, "lon": 126.9910}
}

@st.cache_data
def load_and_prep_data():
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql("SELECT * FROM stores", conn)
    conn.close()
    
    df["title"] = df["title"].fillna("제목 없음")
    df["businessMiddleCodeName"] = df["businessMiddleCodeName"].fillna("미분류")
    df["floor_label"] = df["floor"].apply(
        lambda x: f"지하 {abs(x)}층" if x < 0 else ("지상 층 일부" if x == 0 else f"지상 {x}층")
    )
    df["subway_name"] = df["nearSubwayStation"].apply(
        lambda x: x.split(",")[0].strip() if isinstance(x, str) and "," in x else "기타"
    )
    def extract_walk(text):
        m = re.search(r"도보\s*(\d+)분", text)
        return int(m.group(1)) if m else 0
    df["walk_min"] = df["nearSubwayStation"].apply(extract_walk)
    df["size_pyeong"] = (df["size"] / 3.3058).round(1)
    
    def parse_images(x):
        try:
            urls = json.loads(x.replace("'", '"'))
            return urls if isinstance(urls, list) else []
        except: return []
    df["img_list_small"] = df["smallPhotoUrls"].apply(parse_images)
    df["img_list_origin"] = df["originPhotoUrls"].apply(parse_images)
    df["thumb"] = df["img_list_small"].apply(lambda x: x[0] if x else "")
    
    df["lat"] = df["subway_name"].apply(lambda x: SUBWAY_COORDS.get(x, {"lat": 37.566, "lon": 126.978})["lat"])
    df["lon"] = df["subway_name"].apply(lambda x: SUBWAY_COORDS.get(x, {"lat": 37.566, "lon": 126.978})["lon"])
    
    return df

df_raw = load_and_prep_data()

# ----------------------------------------------------------
# 3. 사이드바 - 스마트 필터
# ----------------------------------------------------------
with st.sidebar:
    st.image("https://www.nemoapp.kr/image/common/nemo_logo.svg", width=150)
    st.title("Pro Filter v2.1")
    
    # 세션 상태 초기화 (검색어 예시용)
    if "search_val" not in st.session_state:
        st.session_state.search_val = ""

    search_keyword = st.text_input("🏢 매물명/키워드 검색", value=st.session_state.search_val)
    
    st.markdown("**검색 예시 가이드**")
    ex_cols = st.columns(3)
    if ex_cols[0].button("#카페"): st.session_state.search_val = "카페"; st.rerun()
    if ex_cols[1].button("#무권리"): st.session_state.search_val = "권리금 없음"; st.rerun()
    if ex_cols[2].button("#대형"): st.session_state.search_val = "대형"; st.rerun()

    st.divider()
    
    # 다중 필터 탭
    t1, t2, t3 = st.tabs(["💰 가격", "📐 공간", "📈 지표"])
    with t1:
        deposit = st.slider("보증금(만)", 0, int(df_raw["deposit"].max()), (0, int(df_raw["deposit"].max())))
        rent = st.slider("월세(만)", 0, int(df_raw["monthlyRent"].max()), (0, int(df_raw["monthlyRent"].max())))
        premium = st.slider("권리금(만)", 0, int(df_raw["premium"].max()), (0, int(df_raw["premium"].max())))
    with t2:
        size = st.slider("면적(평)", 0.0, float(df_raw["size_pyeong"].max()), (0.0, float(df_raw["size_pyeong"].max())))
        selected_industries = st.multiselect("업종", sorted(df_raw["businessMiddleCodeName"].unique()))
        selected_subways = st.multiselect("역세권", sorted(df_raw["subway_name"].unique()))
    with t3:
        maintenance = st.slider("관리비(만)", 0, int(df_raw["maintenanceFee"].max()), (0, int(df_raw["maintenanceFee"].max())))
        min_views = st.number_input("최소 조회수", 0, 10000, 0)
        min_favs = st.number_input("최소 관심수", 0, 1000, 0)

# 필터 적용
df_filtered = df_raw.copy()
if search_keyword:
    df_filtered = df_filtered[df_filtered["title"].str.contains(search_keyword, case=False)]
df_filtered = df_filtered[
    (df_filtered["deposit"].between(deposit[0], deposit[1])) &
    (df_filtered["monthlyRent"].between(rent[0], rent[1])) &
    (df_filtered["premium"].between(premium[0], premium[1])) &
    (df_filtered["size_pyeong"].between(size[0], size[1])) &
    (df_filtered["maintenanceFee"].between(maintenance[0], maintenance[1])) &
    (df_filtered["viewCount"] >= min_views) &
    (df_filtered["favoriteCount"] >= min_favs)
]
if selected_industries: df_filtered = df_filtered[df_filtered["businessMiddleCodeName"].isin(selected_industries)]
if selected_subways: df_filtered = df_filtered[df_filtered["subway_name"].isin(selected_subways)]

# ----------------------------------------------------------
# 4. 메인 화면
# ----------------------------------------------------------
st.title("🚀 Nemostore Pro Dashboard v2.1")

main_tabs = st.tabs(["🖼️ 매물 갤러리", "📊 상권 분석", "🗺️ 지도"])

# --- 상세 정보 팝업 (Modal) 함수 ---
@st.dialog("💎 매물 상세 리포트", width="large")
def show_details(item):
    d_cols = st.columns([1.2, 1])
    
    with d_cols[0]:
        st.subheader("🖼️ 매물 사진 (Slide)")
        imgs = item['img_list_origin']
        if imgs:
            img_tabs = st.tabs([f"사진 {i+1}" for i in range(len(imgs[:10]))])
            for i, t in enumerate(img_tabs):
                if i < len(imgs):
                    t.image(imgs[i], use_container_width=True)
        else:
            st.warning("등록된 상세 이미지가 없습니다.")
            
    with d_cols[1]:
        st.subheader(item['title'])
        # 벤치마킹 계산
        avg_rent = df_raw[df_raw['businessMiddleCodeName'] == item['businessMiddleCodeName']]['monthlyRent'].mean()
        diff = ((item['monthlyRent'] / avg_rent) - 1) * 100
        color = "benchmarking-plus" if diff > 0 else "benchmarking-minus"
        
        st.markdown(f"""
            **업종 분석**: {item['businessMiddleCodeName']} 기준 평균 대비 <span class="{color}">{diff:.1f}%</span> 수준  
            ---
            - **임대료**: 보증금 {item['deposit']:,} / 월세 {item['monthlyRent']:,} (만원)
            - **권리금**: {item['premium']:,} 만원
            - **관리비**: {item['maintenanceFee']:,} 만원
            - **면적**: {item['size_pyeong']} 평 ({item['size']} ㎡)
            - **층수**: {item['floor_label']}
            - **조회/관심**: 👀 {item['viewCount']} / ❤️ {item['favoriteCount']}
        """, unsafe_allow_html=True)
        
        if st.button("창 닫기"):
            st.rerun()

with main_tabs[0]:
    v_mode = st.toggle("테이블 모드로 보기", False)
    
    if not v_mode:
        rows = (len(df_filtered) // 3) + (1 if len(df_filtered) % 3 > 0 else 0)
        for r in range(rows):
            cols = st.columns(3)
            for c in range(3):
                idx = r * 3 + c
                if idx < len(df_filtered):
                    item = df_filtered.iloc[idx]
                    with cols[c]:
                        st.markdown(f"""
                            <div class="property-card">
                                <img src="{item['thumb']}" style="width:100%; border-radius:4px; height:200px; object-fit:cover;">
                                <div style="margin-top:10px;"><span class="status-badge">{item['businessMiddleCodeName']}</span></div>
                                <div style="font-weight:700; margin-top:5px; height:2.5rem; overflow:hidden;">{item['title']}</div>
                                <div class="price-tag">월 {item['monthlyRent']:,} / 보 {item['deposit']:,}</div>
                                <div style="font-size:0.8rem; color:#666;">{item['floor_label']} · {item['size_pyeong']}평 · {item['subway_name']}</div>
                            </div>
                        """, unsafe_allow_html=True)
                        if st.button(f"상세보기 #{item['id'][:8]}", key=f"btn_{item['id']}"):
                            show_details(item.to_dict())

with main_tabs[1]:
    st.subheader("📊 데이터 인사이트")
    sc_cols = st.columns(2)
    with sc_cols[0]:
        fig1 = px.histogram(df_filtered, x="monthlyRent", nbins=20, title="월세 분포 현황", 
                           labels={"monthlyRent": "월세(만)"}, color_discrete_sequence=['#FFE600'])
        st.plotly_chart(fig1, width='stretch')
    with sc_cols[1]:
        fig2 = px.scatter(df_filtered, x="size_pyeong", y="monthlyRent", color="businessMiddleCodeName",
                         title="면적 대비 월세 상관관계", labels={"size_pyeong": "면적(평)", "monthlyRent": "월세(만)"})
        st.plotly_chart(fig2, width='stretch')

with main_tabs[2]:
    st.subheader("📍 역세권 매물 지도")
    fig_map = px.scatter_mapbox(df_filtered, lat="lat", lon="lon", color="businessMiddleCodeName", size="monthlyRent",
                               hover_name="title", zoom=12, height=600, mapbox_style="carto-positron")
    st.plotly_chart(fig_map, width='stretch')

st.caption("Nemostore Pro Dashboard v2.1 | Enhanced by Antigravity AI")
