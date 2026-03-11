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
st.set_page_config(page_title="Nemostore Pro Dashboard v2.0", layout="wide")

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
    .benchmarking-plus { color: #D32F2F; font-weight: bold; }
    .benchmarking-minus { color: #388E3C; font-weight: bold; }
    </style>
""", unsafe_allow_html=True)

# ----------------------------------------------------------
# 2. 데이터 로드 및 전처리
# ----------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "data", "nemostore.db")

# 컬럼 명 한글 매핑
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
    "favoriteCount": "관심수",
    "areaPrice": "평당가"
}

# 주요 지하철역 좌표 (CBD 기준)
SUBWAY_COORDS = {
    "종각역": {"lat": 37.5701, "lon": 126.9829},
    "을지로입구역": {"lat": 37.5660, "lon": 126.9821},
    "종로3가역": {"lat": 37.5704, "lon": 126.9921},
    "시청역": {"lat": 37.5657, "lon": 126.9769},
    "광화문역": {"lat": 37.5709, "lon": 126.9761},
    "을지로3가역": {"lat": 37.5662, "lon": 126.9910},
    "안국역": {"lat": 37.5765, "lon": 126.9854},
    "경복궁역": {"lat": 37.5758, "lon": 126.9735},
    "명동역": {"lat": 37.5609, "lon": 126.9863}
}

@st.cache_data
def load_and_prep_data():
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql("SELECT * FROM stores", conn)
    conn.close()
    
    # 기본 전처리
    df["title"] = df["title"].fillna("제목 없음")
    df["businessMiddleCodeName"] = df["businessMiddleCodeName"].fillna("미분류")
    df["is_underground"] = df["floor"] < 0
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
    
    # 이미지 파싱
    def parse_images(x):
        try:
            urls = json.loads(x.replace("'", '"'))
            return urls if isinstance(urls, list) else []
        except:
            return []
    df["img_list_small"] = df["smallPhotoUrls"].apply(parse_images)
    df["img_list_origin"] = df["originPhotoUrls"].apply(parse_images)
    df["thumb"] = df["img_list_small"].apply(lambda x: x[0] if x else "")
    
    # 좌표 매핑
    df["lat"] = df["subway_name"].apply(lambda x: SUBWAY_COORDS.get(x, {"lat": 37.566, "lon": 126.978})["lat"])
    df["lon"] = df["subway_name"].apply(lambda x: SUBWAY_COORDS.get(x, {"lat": 37.566, "lon": 126.978})["lon"])
    
    return df

df_raw = load_and_prep_data()

# ----------------------------------------------------------
# 3. 사이드바 - 고급 필터
# ----------------------------------------------------------
with st.sidebar:
    st.image("https://www.nemoapp.kr/image/common/nemo_logo.svg", width=150)
    st.title("Pro Filter v2.0")
    
    search_keyword = st.text_input("🏢 매물명/키워드 검색", "")
    
    tab_f1, tab_f2 = st.tabs(["💰 가격", "📐 조건"])
    with tab_f1:
        deposit = st.slider("보증금(만)", 0, int(df_raw["deposit"].max()), (0, int(df_raw["deposit"].max())))
        rent = st.slider("월세(만)", 0, int(df_raw["monthlyRent"].max()), (0, int(df_raw["monthlyRent"].max())))
        premium = st.slider("권리금(만)", 0, int(df_raw["premium"].max()), (0, int(df_raw["premium"].max())))
    
    with tab_f2:
        size = st.slider("면적(평)", 0.0, float(df_raw["size_pyeong"].max()), (0.0, float(df_raw["size_pyeong"].max())))
        industries = st.multiselect("업종 선택", sorted(df_raw["businessMiddleCodeName"].unique()))
        subways = st.multiselect("역세권 선택", sorted(df_raw["subway_name"].unique()))

# 필터 적용
df_filtered = df_raw.copy()
if search_keyword:
    df_filtered = df_filtered[df_filtered["title"].str.contains(search_keyword, case=False)]
df_filtered = df_filtered[
    (df_filtered["deposit"].between(deposit[0], deposit[1])) &
    (df_filtered["monthlyRent"].between(rent[0], rent[1])) &
    (df_filtered["premium"].between(premium[0], premium[1])) &
    (df_filtered["size_pyeong"].between(size[0], size[1]))
]
if industries: df_filtered = df_filtered[df_filtered["businessMiddleCodeName"].isin(industries)]
if subways: df_filtered = df_filtered[df_filtered["subway_name"].isin(subways)]

# ----------------------------------------------------------
# 4. 메인 대시보드
# ----------------------------------------------------------
st.title("🚀 Nemostore 상가 분석 서비스 Pro")

tab1, tab2, tab3 = st.tabs(["🖼️ 갤러리 탐색", "📊 상권 분석", "🗺️ 지도 뷰"])

# --- Tab 1: Gallery View ---
with tab1:
    view_mode = st.radio("보기 모드", ["갤러리(이미지)", "테이블(데이터)"], horizontal=True)
    
    if view_mode == "갤러리(이미지)":
        # 갤러리 구현
        cols = st.columns(3)
        for idx, row in df_filtered.iterrows():
            col_idx = idx % 3
            with cols[col_idx]:
                st.markdown(f"""
                    <div class="property-card">
                        <img src="{row['thumb']}" style="width:100%; border-radius:4px; margin-bottom:10px; height:180px; object-fit:cover;">
                        <div class="status-badge">{row['businessMiddleCodeName']}</div>
                        <div style="font-weight:700; font-size:1.1rem; margin-top:5px; height:3rem; overflow:hidden;">{row['title']}</div>
                        <div class="price-tag">월 {row['monthlyRent']:,} / 보 {row['deposit']:,}</div>
                        <div style="font-size:0.85rem; color:#666;">{row['floor_label']} · {row['size_pyeong']}평 · {row['subway_name']}</div>
                    </div>
                """, unsafe_allow_html=True)
                if st.button(f"상세 정보 확인 #{idx}", key=f"btn_{idx}", icon="🔍"):
                    st.session_state.selected_id = row['id']
                    st.rerun()

    else:
        # 테이블 한글화
        df_display = df_filtered[COL_MAPPING.keys()].rename(columns=COL_MAPPING)
        st.dataframe(df_display, width='stretch') # 'stretch' is the new recommended value for full width
        st.download_button("📥 검색 결과 CSV 다운로드", df_display.to_csv(index=False).encode('utf-8-sig'), "nemostore_search.csv", "text/csv")

# --- Tab 2: Analysis & Benchmarking ---
with tab2:
    st.subheader("💡 층별 & 상권 가치분석")
    
    c1, c2 = st.columns(2)
    with c1:
        # 층별 임대료 분석
        fig_floor = px.box(df_filtered, x="floor_label", y="monthlyRent", title="층별 월세 분포 (Box Plot)", 
                         labels={"floor_label": "층수", "monthlyRent": "월세(만)"})
        st.plotly_chart(fig_floor, width='stretch')
    
    with c2:
        # 업종별 벤치마킹 시각화
        bench_data = df_filtered.groupby("businessMiddleCodeName")["monthlyRent"].median().reset_index()
        fig_bench = px.bar(bench_data, x="monthlyRent", y="businessMiddleCodeName", orientation='h',
                          title="업종별 월세 중앙값 비교", labels={"monthlyRent": "월세 중앙값", "businessMiddleCodeName": "업종"})
    st.plotly_chart(fig_bench, width='stretch')

# --- Tab 3: Map View ---
with tab3:
    st.subheader("📍 매물 위치 현황 (역세권 중심)")
    map_df = df_filtered.copy()
    fig_map = px.scatter_mapbox(map_df, lat="lat", lon="lon", size="monthlyRent", color="businessMiddleCodeName",
                               hover_name="title", hover_data=["deposit", "monthlyRent", "subway_name"],
                               zoom=13, height=600, mapbox_style="carto-positron",
                               title="지하철역 기반 매물 분포 (원 크기=월세)")
    st.plotly_chart(fig_map, width='stretch')

# ----------------------------------------------------------
# 5. 상세 페이지 (Sidebar or Overlay)
# ----------------------------------------------------------
if 'selected_id' in st.session_state:
    selected_row = df_raw[df_raw['id'] == st.session_state.selected_id].iloc[0]
    
    st.sidebar.divider()
    st.sidebar.subheader("💎 매물 상세 리포트")
    
    # 이미지 갤러리 (상세)
    imgs = selected_row['img_list_origin']
    if imgs:
        st.sidebar.image(imgs[0], width='stretch')
        if len(imgs) > 1:
            with st.sidebar.expander("추가 사진 보기"):
                for im in imgs[1:5]: st.image(im)
    
    st.sidebar.markdown(f"### {selected_row['title']}")
    
    # 가치 평가 (Benchmarking) 로직
    avg_rent_industry = df_raw[df_raw['businessMiddleCodeName'] == selected_row['businessMiddleCodeName']]['monthlyRent'].mean()
    diff_percent = ((selected_row['monthlyRent'] / avg_rent_industry) - 1) * 100
    color_class = "benchmarking-plus" if diff_percent > 0 else "benchmarking-minus"
    diff_text = f"+{diff_percent:.1f}%" if diff_percent > 0 else f"{diff_percent:.1f}%"
    
    st.sidebar.markdown(f"""
        **업종:** {selected_row['businessMiddleCodeName']}  
        **가치 평가:** 동일 업종 평균 대비 월세가 <span class="{color_class}">{diff_text}</span> 수준입니다.  
        ---
        - **보증금:** {selected_row['deposit']:,} 만원
        - **월세:** {selected_row['monthlyRent']:,} 만원
        - **권리금:** {selected_row['premium']:,} 만원
        - **전용면적:** {selected_row['size_pyeong']} 평
        - **층수:** {selected_row['floor_label']}
        - **인근역:** {selected_row['subway_name']} (도보 {selected_row['walk_min']}분)
    """, unsafe_allow_html=True)
    
    if st.sidebar.button("닫기"):
        del st.session_state.selected_id
        st.rerun()

st.caption("Pro Dashboard v2.0 | Powerd by Antigravity AI")
