"""
Aplikasi Streamlit Utama
Sistem Pendukung Keputusan Hilirisasi Ekspor
"""

import os
import sys
from pathlib import Path

# Tambahkan src ke path
sys.path.append(str(Path(__file__).parent))

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
from dotenv import load_dotenv

# Import modul kustom
from ai_service import get_gemini_service
from data_miner import fetch_comtrade_data, extract_and_fetch_data
from database import get_db_manager
from utils import (
    clean_hs_code, extract_hs_codes_from_ai, get_best_hs_code,
    get_hs_code_description, format_currency_compact, select_hs_codes_with_conflict_resolution
)

# Try to import Gurobi modules (optional)
try:
    from gurobi_modules.market_sharing import solve_competitor_displacement
    from gurobi_modules.supply_network import solve_price_arbitrage
    GUROBI_AVAILABLE = True
except ImportError:
    GUROBI_AVAILABLE = False
    print("Warning: Gurobi modules not available. Optimization features will be disabled.")

# Muat variabel environment
load_dotenv()

import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)



# Konfigurasi halaman
st.set_page_config(
    page_title="Sistem Pendukung Keputusan Hilirisasi Ekspor",
    layout="wide",
    initial_sidebar_state="expanded"
)

# CSS kustom
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #1f77b4;
        text-align: center;
        margin-bottom: 1rem;
    }
    .sub-header {
        font-size: 1.2rem;
        text-align: center;
        color: #666;
        margin-bottom: 2rem;
    }
    .metric-card {
        background-color: #f0f2f6;
        padding: 1rem;
        border-radius: 0.5rem;
        margin: 0.5rem 0;
    }
</style>
""", unsafe_allow_html=True)


def initialize_session_state():
    """Inisialisasi variabel session state Streamlit"""
    if 'analysis_complete' not in st.session_state:
        st.session_state.analysis_complete = False
    if 'analysis_results' not in st.session_state:
        st.session_state.analysis_results = None


def render_header():
    """Render header aplikasi"""
    st.markdown('<div class="main-header">Sistem Pendukung Keputusan Hilirisasi Ekspor</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-header">Export Downstreaming Decision Support System</div>', unsafe_allow_html=True)
    st.markdown("---")


def render_sidebar():
    """Render sidebar dengan informasi"""
    with st.sidebar:
        

        
        st.markdown("""
        Sistem yang membantu menganalisis potensi hilirisasi komoditas ekspor Indonesia menggunakan:

        - **AI (Google Gemini)** untuk analisis komoditas & HS Code
        - **UN Comtrade API** untuk data perdagangan real-time
        - **MySQL Caching** untuk efisiensi
        """)

        st.markdown("---")
        st.markdown("## ⚙️ Pengaturan")

        # Pengaturan lanjutan
        with st.expander("Pengaturan Lanjutan"):
            years_to_analyze = st.slider("Jumlah Tahun Analisis", 3, 7, 5)

            st.session_state.years_to_analyze = years_to_analyze



def perform_analysis(commodity_input: str):
    """
    Melakukan analisis hilirisasi lengkap.
    HS codes langsung dari Gemini AI (tanpa TF-IDF matching).

    Args:
        commodity_input: Nama komoditas input dari user
    """
    progress_bar = st.progress(0)
    status_text = st.empty()

    try:
        # Step 1: Inisialisasi layanan
        status_text.text("Menginisialisasi layanan...")
        progress_bar.progress(10)

        gemini = get_gemini_service()
        db = get_db_manager()

        # Step 2: Cek cache
        status_text.text("Memeriksa cache...")
        progress_bar.progress(20)

        cached_search = None
        if db:
            cached_search = db.get_cached_commodity_search(commodity_input)

        # Step 3: Ekstraksi AI atau gunakan cache
        if cached_search:
            status_text.text("Data ditemukan di cache!")
            ai_result = cached_search['ai_extraction']
            raw_hs_code = cached_search['raw_hs_code']
            finished_hs_code = cached_search['finished_hs_code']
            semi_hs_code = cached_search.get('semi_hs_code')
        else:
            status_text.text("🤖 Mengekstrak informasi & HS Code dengan AI...")
            progress_bar.progress(30)

            ai_result = gemini.extract_commodity_keywords(commodity_input)
            
            # Tampilkan hasil ekstraksi AI
            with st.expander("🤖 Hasil Ekstraksi AI", expanded=False):
                st.json({
                    "Komoditas": ai_result.get('commodity_name'),
                    "Bahan Mentah": ai_result.get('raw_material'),
                    "Setengah Jadi": ai_result.get('semi_finished'),
                    "Produk Jadi": ai_result.get('finished_product'),
                    "Keywords": ai_result.get('keywords', []),
                    "HS Code Bahan Mentah": ai_result.get('raw_hs_codes', []),
                    "HS Code Setengah Jadi": ai_result.get('semi_hs_codes', []),
                    "HS Code Produk Jadi": ai_result.get('finished_hs_codes', []),
                    "Alasan Jalur": ai_result.get('selected_path_reason', 'N/A')
                })

            # Step 4: Ambil dan bersihkan HS codes dari AI dengan resolusi konflik
            status_text.text("🔍 Memproses HS Code dari AI...")
            progress_bar.progress(40)

            # Pilih HS codes untuk semua stage dengan menghindari konflik
            hs_codes = select_hs_codes_with_conflict_resolution(ai_result)
            raw_hs_code = hs_codes['raw']
            semi_hs_code = hs_codes['semi']
            finished_hs_code = hs_codes['finished']

            if not raw_hs_code:
                st.error("❌ AI tidak dapat menentukan HS Code bahan mentah. Coba dengan kata kunci lain.")
                return

            if not finished_hs_code:
                st.error("❌ AI tidak dapat menentukan HS Code produk jadi. Coba dengan kata kunci lain.")
                return

            # Ambil deskripsi dari AI
            raw_desc = get_hs_code_description(ai_result, 'raw', raw_hs_code)
            semi_desc = get_hs_code_description(ai_result, 'semi', semi_hs_code) if semi_hs_code else 'N/A'
            finished_desc = get_hs_code_description(ai_result, 'finished', finished_hs_code)

            # Cek apakah ada konflik HS code yang di-resolve
            conflict_note = ""
            if raw_hs_code and semi_hs_code and raw_hs_code == semi_hs_code:
                conflict_note = " ⚠️ **Catatan:** HS Code bahan mentah dan setengah jadi sama karena keterbatasan klasifikasi UN Comtrade untuk produk herbal."
            elif raw_hs_code and finished_hs_code and raw_hs_code == finished_hs_code:
                conflict_note = " ⚠️ **Catatan:** HS Code bahan mentah dan produk jadi sama karena keterbatasan klasifikasi UN Comtrade untuk produk herbal."
            elif semi_hs_code and finished_hs_code and semi_hs_code == finished_hs_code:
                conflict_note = " ⚠️ **Catatan:** HS Code setengah jadi dan produk jadi sama karena keterbatasan klasifikasi UN Comtrade untuk produk herbal."

            # Tampilkan HS codes yang ditemukan untuk verifikasi user
            st.info(f"""
            🔍 **HS Codes dari AI (dibersihkan untuk UN Comtrade):**
            - **Bahan Mentah:** {raw_hs_code} - {raw_desc}
            - **Setengah Jadi:** {semi_hs_code or 'N/A'} - {semi_desc}
            - **Produk Jadi:** {finished_hs_code} - {finished_desc}
            {conflict_note}
            """)

            # Tampilkan semua alternatif HS codes
            with st.expander("📋 Semua Alternatif HS Code dari AI", expanded=False):
                all_raw_codes = extract_hs_codes_from_ai(ai_result, 'raw')
                all_semi_codes = extract_hs_codes_from_ai(ai_result, 'semi')
                all_finished_codes = extract_hs_codes_from_ai(ai_result, 'finished')
                
                st.markdown("**Bahan Mentah:**")
                for code in all_raw_codes:
                    desc = get_hs_code_description(ai_result, 'raw', code)
                    marker = " ✅" if code == raw_hs_code else ""
                    st.markdown(f"- `{code}` - {desc}{marker}")
                
                st.markdown("**Setengah Jadi:**")
                for code in all_semi_codes:
                    desc = get_hs_code_description(ai_result, 'semi', code)
                    marker = " ✅" if code == semi_hs_code else ""
                    st.markdown(f"- `{code}` - {desc}{marker}")
                
                st.markdown("**Produk Jadi:**")
                for code in all_finished_codes:
                    desc = get_hs_code_description(ai_result, 'finished', code)
                    marker = " ✅" if code == finished_hs_code else ""
                    st.markdown(f"- `{code}` - {desc}{marker}")

            # Simpan pencarian ke cache
            if db:
                db.cache_commodity_search(commodity_input, ai_result, raw_hs_code, semi_hs_code, finished_hs_code)

        # Step 5: Ambil data untuk optimasi Gurobi
        status_text.text("📡 Mengambil data untuk optimasi...")
        progress_bar.progress(60)

        years_to_analyze = st.session_state.get('years_to_analyze', 3)
        start_year = datetime.now().year - years_to_analyze
        end_year = datetime.now().year

        # Gunakan extract_and_fetch_data untuk mendapatkan data semua kategori sekaligus
        # Untuk supply: gunakan raw_hs_code
        # Untuk competitor & demand: gunakan finished_hs_code
        # Jika ada semi: gunakan untuk competitor
        
        # Ambil data Supply (ekspor Indonesia) - bahan dasar menggunakan extract_and_fetch_data
        supply_results, supply_ai_info = extract_and_fetch_data(commodity_input, start_year, end_year, mode='supply')
        df_supply = supply_results.get('raw', pd.DataFrame())
        
        # Ambil data Competitor (ekspor negara lain) - produk jadi
        df_competitor = fetch_comtrade_data(finished_hs_code, start_year, end_year, mode='competitor')
        
        # Ambil data Demand (impor dunia) - produk jadi
        df_demand = fetch_comtrade_data(finished_hs_code, start_year, end_year, mode='demand')

        # Jika ada semi_hs_code, ambil data demand untuk semi juga
        if semi_hs_code:
            df_demand_semi = fetch_comtrade_data(semi_hs_code, start_year, end_year, mode='demand')

        # Step 6: Jalankan Optimasi Gurobi
        status_text.text("🎯 Menjalankan optimasi matematis...")
        progress_bar.progress(80)

        optimization_results = {}

        if GUROBI_AVAILABLE:
            # Optimasi untuk Bahan Mentah (Strategi B1: Competitor Displacement)
            if not df_supply.empty:
                b1_result = solve_competitor_displacement(df_supply, df_competitor)
                optimization_results['raw'] = b1_result

            # Optimasi untuk Produk Jadi (Strategi B3: Price Arbitrage)  
            if not df_supply.empty and not df_demand.empty:
                b3_result = solve_price_arbitrage(df_supply, df_demand)
                optimization_results['finished'] = b3_result

            # Jika ada Semi, gunakan B3 juga
            if semi_hs_code and not df_supply.empty and not df_demand.empty:
                # Untuk semi, gunakan HS code semi tapi data supply tetap dari raw
                df_demand_semi = fetch_comtrade_data(semi_hs_code, start_year, end_year, mode='demand')
                if not df_demand_semi.empty:
                    b3_semi_result = solve_price_arbitrage(df_supply, df_demand_semi)
                    optimization_results['semi'] = b3_semi_result
        else:
            optimization_results = {"status": "Gurobi not available", "reason": "Optimization features disabled"}

        # Step 7: Generate ringkasan AI
        status_text.text("✍️ Membuat ringkasan analisis...")
        progress_bar.progress(90)

        # Generate ringkasan AI berdasarkan hasil optimasi
        ai_summary = gemini.generate_analysis_summary(
            commodity=ai_result['commodity_name'],
            optimization_results=optimization_results
        )

        # Simpan ke database (update schema jika perlu)
        if db:
            db.save_analysis_result({
                'commodity_name': ai_result['commodity_name'],
                'raw_hs_code': raw_hs_code,
                'semi_hs_code': semi_hs_code,
                'finished_hs_code': finished_hs_code,
                'optimization_results': optimization_results,
                'analysis_summary': ai_summary
            })

        # Simpan hasil ke session state
        st.session_state.analysis_results = {
            'commodity': ai_result['commodity_name'],
            'raw_hs_code': raw_hs_code,
            'semi_hs_code': semi_hs_code,
            'finished_hs_code': finished_hs_code,
            'optimization_results': optimization_results,
            'ai_summary': ai_summary,
            'protocol_data': {
                'supply': df_supply,
                'competitor': df_competitor, 
                'demand': df_demand
            },
            'ai_result': ai_result
        }

        st.session_state.analysis_complete = True

        status_text.text("✅ Analisis selesai!")
        progress_bar.progress(100)

    except Exception as e:
        st.error(f"Terjadi kesalahan: {str(e)}")
        import traceback
        st.error(traceback.format_exc())


def render_results():
    """Render analysis results"""
    if not st.session_state.analysis_complete or not st.session_state.analysis_results:
        return

    results = st.session_state.analysis_results

    st.markdown("## 📊 Hasil Analisis")

    # Info komoditas dengan deskripsi HS Code (dari AI result)
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Komoditas", results['commodity'])

    # Ambil deskripsi HS Code dari AI result
    ai_result = results.get('ai_result', {})
    raw_desc = get_hs_code_description(ai_result, 'raw', results['raw_hs_code'])
    semi_desc = get_hs_code_description(ai_result, 'semi', results.get('semi_hs_code', '')) if results.get('semi_hs_code') else 'N/A'
    finished_desc = get_hs_code_description(ai_result, 'finished', results['finished_hs_code'])

    with col2:
        st.metric("HS Bahan Mentah", results['raw_hs_code'])
        st.caption(f"📦 {raw_desc[:50]}..." if len(raw_desc) > 50 else f"📦 {raw_desc}")
    with col3:
        st.metric("HS Setengah Jadi", results.get('semi_hs_code', 'N/A'))
        if results.get('semi_hs_code'):
            st.caption(f"🔧 {semi_desc[:50]}..." if len(semi_desc) > 50 else f"🔧 {semi_desc}")
    with col4:
        st.metric("HS Produk Jadi", results['finished_hs_code'])
        st.caption(f"✨ {finished_desc[:50]}..." if len(finished_desc) > 50 else f"✨ {finished_desc}")

    # Tampilkan alasan pemilihan jalur terbaik
    if 'ai_result' in results and 'selected_path_reason' in results['ai_result']:
        st.info(f"🎯 **Jalur Hilirisasi Terpilih:** {results['ai_result']['selected_path_reason']}")

    # Tampilkan catatan posisi input user
    if 'ai_result' in results and results['ai_result'].get('user_position_note'):
        input_stage = results['ai_result'].get('input_stage', 'raw')
        if input_stage == 'semi':
            st.warning(f"📍 **Posisi Input Anda:** {results['ai_result']['user_position_note']}")
        elif input_stage == 'finished':
            st.error(f"⚠️ **Perhatian:** {results['ai_result']['user_position_note']}")

    st.markdown("---")

    # Hasil Optimasi Gurobi
    st.markdown("### 🎯 Hasil Optimasi Matematis")

    opt_results = results.get('optimization_results', {})

    # Tampilkan hasil untuk setiap stage
    stages = [('raw', 'Bahan Mentah'), ('semi', 'Setengah Jadi'), ('finished', 'Produk Jadi')]
    
    for stage_key, stage_name in stages:
        if stage_key in opt_results:
            opt = opt_results[stage_key]
            
            if opt.get('status') == 'Optimal':
                st.markdown(f"#### 📦 {stage_name}")
                
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric(
                        "Potensi Devisa ($)",
                        format_currency_compact(opt.get('total_revenue', 0))
                    )
                with col2:
                    st.metric(
                        "Volume Alokasi (Kg)",
                        format_currency_compact(opt.get('total_volume', 0))
                    )
                with col3:
                    strategy = opt.get('strategy', 'N/A')
                    st.metric("Strategi", strategy)
                
                # Tampilkan detail alokasi
                if 'details' in opt and opt['details']:
                    with st.expander(f"📋 Detail Alokasi {stage_name}", expanded=False):
                        for detail in opt['details'][:5]:  # Tampilkan top 5
                            st.markdown(f"""
                            - **{detail.get('Negara Tujuan', 'N/A')}**: 
                              {format_currency_compact(detail.get('Volume Alokasi (Kg)', 0))} kg → 
                              ${format_currency_compact(detail.get('Potensi Devisa ($)', 0))}
                            """)
            else:
                st.warning(f"⚠️ Optimasi {stage_name} gagal: {opt.get('reason', 'Unknown error')}")

    # Ringkasan AI
    st.markdown("---")
    st.markdown("### 🤖 Ringkasan Analisis AI")
    st.markdown(results['ai_summary'])

    # Visualisasi
    st.markdown("---")
    st.markdown("### 📈 Visualisasi Data")

    # Buat visualisasi jika data tersedia
    render_visualizations(results['protocol_data'])


def render_visualizations(data: dict):
    """
    Render data visualizations for optimization results

    Args:
        data: Protocol data containing time series export/import data
    """
    # Ekstrak data time series dari protocol
    supply_data = data.get('supply', pd.DataFrame())
    competitor_data = data.get('competitor', pd.DataFrame())
    demand_data = data.get('demand', pd.DataFrame())

    # Fungsi helper untuk aggregate data per tahun
    def aggregate_by_year(df, value_col='TradeValue'):
        if df.empty:
            return pd.DataFrame()

        # Cek berbagai kemungkinan nama kolom
        period_cols = ['Period', 'period', 'ps']
        value_cols = ['TradeValue', 'PrimaryValue', 'tradeValue', 'primaryValue']

        period_col = None
        for col in period_cols:
            if col in df.columns:
                period_col = col
                break

        actual_value_col = value_col
        for col in value_cols:
            if col in df.columns:
                actual_value_col = col
                break

        if period_col is None or actual_value_col not in df.columns:
            return pd.DataFrame()

        yearly = df.groupby(period_col)[actual_value_col].sum().reset_index()
        yearly.columns = ['Year', 'Value']
        yearly = yearly.sort_values('Year')
        return yearly

    # Aggregate data
    supply_yearly = aggregate_by_year(supply_data)
    competitor_yearly = aggregate_by_year(competitor_data)
    demand_yearly = aggregate_by_year(demand_data)

    # Tampilkan data dalam tabel sederhana
    st.markdown("#### 📊 Data Ekspor Indonesia (Supply)")
    if not supply_yearly.empty:
        st.dataframe(supply_yearly, use_container_width=True)
        st.info(f"📈 Total records: {len(supply_data)} | Columns: {list(supply_data.columns)}")
    else:
        st.info("Data supply tidak tersedia")
        if not supply_data.empty:
            st.warning(f"Data ada tapi kosong setelah aggregate. Columns: {list(supply_data.columns)}")
            st.dataframe(supply_data.head(), use_container_width=True)

    st.markdown("#### 📊 Data Kompetitor")
    if not competitor_yearly.empty:
        st.dataframe(competitor_yearly, use_container_width=True)
        st.info(f"📈 Total records: {len(competitor_data)} | Columns: {list(competitor_data.columns)}")
    else:
        st.info("Data kompetitor tidak tersedia")
        if not competitor_data.empty:
            st.warning(f"Data ada tapi kosong setelah aggregate. Columns: {list(competitor_data.columns)}")
            st.dataframe(competitor_data.head(), use_container_width=True)

    st.markdown("#### 📊 Data Permintaan Global (Demand)")
    if not demand_yearly.empty:
        st.dataframe(demand_yearly, use_container_width=True)
        st.info(f"📈 Total records: {len(demand_data)} | Columns: {list(demand_data.columns)}")
    else:
        st.info("Data demand tidak tersedia")
        if not demand_data.empty:
            st.warning(f"Data ada tapi kosong setelah aggregate. Columns: {list(demand_data.columns)}")
            st.dataframe(demand_data.head(), use_container_width=True)


def main():
    """Main application function"""
    initialize_session_state()
    render_header()
    render_sidebar()

    # Konten utama
    st.markdown("## 🔍 Input Komoditas")
    st.markdown("Masukkan nama komoditas yang ingin dianalisis (contoh: kelapa, nikel, sawit, kopi)")

    col1, col2 = st.columns([3, 1])

    with col1:
        commodity_input = st.text_input(
            "Nama Komoditas",
            placeholder="Contoh: kelapa, nikel, sawit...",
            label_visibility="collapsed"
        )

    with col2:
        analyze_button = st.button("🚀 Analisis", type="primary", use_container_width=False)

    if analyze_button and commodity_input:
        st.session_state.analysis_complete = False
        perform_analysis(commodity_input)
    elif analyze_button:
        st.warning("⚠️ Mohon masukkan nama komoditas terlebih dahulu.")

    # Tampilkan hasil jika tersedia
    if st.session_state.analysis_complete:
        render_results()

    # Footer aplikasi
    st.markdown("---")
    st.markdown("""
    <div style="text-align: center; color: #666; padding: 2rem;">
        <small>
        Sistem Pendukung Keputusan Hilirisasi Ekspor<br>
        Dikembangkan dengan Python, Streamlit, Google Gemini AI, dan UN Comtrade API<br>
        </small>
    </div>
    """, unsafe_allow_html=True)


if __name__ == "__main__":
    main()
