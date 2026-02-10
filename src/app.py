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
from data_miner import get_comtrade_api
from database import get_db_manager
from utils import (
    clean_hs_code, extract_hs_codes_from_ai, get_best_hs_code,
    get_hs_code_description, calculate_cagr, calculate_value_added,
    format_currency, format_currency_compact
)

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
    .recommendation-box {
        padding: 1.5rem;
        border-radius: 0.5rem;
        margin: 1rem 0;
        font-size: 1.1rem;
        font-weight: bold;
    }
    .recommendation-positive {
        background-color: #d4edda;
        color: #155724;
        border: 2px solid #28a745;
    }
    .recommendation-negative {
        background-color: #f8d7da;
        color: #721c24;
        border: 2px solid #dc3545;
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
        comtrade = get_comtrade_api()
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

            # Step 4: Ambil dan bersihkan HS codes dari AI
            status_text.text("🔍 Memproses HS Code dari AI...")
            progress_bar.progress(40)

            # Ekstrak HS codes untuk setiap stage
            raw_hs_code = get_best_hs_code(ai_result, 'raw')
            semi_hs_code = get_best_hs_code(ai_result, 'semi')
            finished_hs_code = get_best_hs_code(ai_result, 'finished')

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

            # Tampilkan HS codes yang ditemukan untuk verifikasi user
            st.info(f"""
            🔍 **HS Codes dari AI (dibersihkan untuk UN Comtrade):**
            - **Bahan Mentah:** {raw_hs_code} - {raw_desc}
            - **Setengah Jadi:** {semi_hs_code or 'N/A'} - {semi_desc}
            - **Produk Jadi:** {finished_hs_code} - {finished_desc}
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
                db.cache_commodity_search(commodity_input, ai_result, raw_hs_code, finished_hs_code)

        # Step 5: Eksekusi 4-Request Protocol
        status_text.text("📡 Mengambil data perdagangan (4-Request)...")
        progress_bar.progress(60)

        years = list(range(datetime.now().year - st.session_state.get('years_to_analyze', 5), datetime.now().year + 1))
        protocol_results = comtrade.four_request_protocol(raw_hs_code, semi_hs_code, finished_hs_code, years)

        # Step 6: Analisis dan generate rekomendasi
        status_text.text("📈 Menganalisis data...")
        progress_bar.progress(80)

        analysis = protocol_results['analysis']

        # Generate rekomendasi
        recommendation = generate_recommendation(analysis)

        # Generate ringkasan AI
        status_text.text("✍️ Membuat ringkasan analisis...")
        progress_bar.progress(90)

        raw_data = {
            'total_value': analysis['raw_export_total'],
            'cagr': round(analysis['raw_export_trend'], 2)
        }

        finished_data = {
            'export_value': analysis['finished_export_total'],
            'world_import': analysis['global_demand_total'],
            'gap': analysis['market_gap'],
            'cagr': round(analysis['global_demand_trend'], 2)
        }

        ai_summary = gemini.generate_analysis_summary(
            commodity=ai_result['commodity_name'],
            raw_data=raw_data,
            finished_data=finished_data,
            recommendations=recommendation
        )

        # Simpan ke database
        if db:
            db.save_analysis_result({
                'commodity_name': ai_result['commodity_name'],
                'raw_hs_code': raw_hs_code,
                'finished_hs_code': finished_hs_code,
                'raw_export_value': analysis['raw_export_total'],
                'finished_export_value': analysis['finished_export_total'],
                'global_demand_value': analysis['global_demand_total'],
                'market_gap': analysis['market_gap'],
                'cagr_raw': analysis['raw_export_trend'],
                'cagr_finished': analysis['global_demand_trend'],
                'recommendation': recommendation['decision'],
                'analysis_summary': ai_summary
            })

        # Simpan hasil ke session state
        st.session_state.analysis_results = {
            'commodity': ai_result['commodity_name'],
            'raw_hs_code': raw_hs_code,
            'semi_hs_code': semi_hs_code,
            'finished_hs_code': finished_hs_code,
            'analysis': analysis,
            'recommendation': recommendation,
            'ai_summary': ai_summary,
            'protocol_data': protocol_results['data'],
            'ai_result': ai_result  # Sertakan AI result untuk reasoning path
        }

        st.session_state.analysis_complete = True

        status_text.text("✅ Analisis selesai!")
        progress_bar.progress(100)

    except Exception as e:
        st.error(f"Terjadi kesalahan: {str(e)}")
        import traceback
        st.error(traceback.format_exc())


def generate_recommendation(analysis: dict) -> dict:
    """
    Generate downstreaming recommendation based on analysis

    Args:
        analysis: Analysis results

    Returns:
        Recommendation dictionary with detailed reasoning
    """
    recommendation = {
        'decision': 'TIDAK LAYAK HILIRISASI',
        'reason': '',
        'score': 0,
        'details': []
    }

    score = 0
    reasons = []
    details = []

    # Faktor 1: Gap pasar (30%)
    gap = analysis['market_gap']
    if gap > 1_000_000_000:  # > $1B gap
        score += 30
        reasons.append(f"Gap pasar global sangat besar (${gap/1_000_000_000:.2f}B), menunjukkan peluang ekspor yang sangat potensial")
        details.append(f"Permintaan global mencapai ${analysis['global_demand_total']/1_000_000_000:.2f}B sementara ekspor Indonesia hanya ${analysis['finished_export_total']/1_000_000:.2f}M")
    elif gap > 100_000_000:  # > $100M gap
        score += 20
        reasons.append(f"Gap pasar global signifikan (${gap/1_000_000:.2f}M), ada ruang untuk ekspansi ekspor")
        # Perlindungan pembagian dengan nol
        if analysis['global_demand_total'] > 0:
            market_share = (analysis['finished_export_total']/analysis['global_demand_total']*100)
            details.append(f"Indonesia baru menguasai {market_share:.1f}% dari permintaan global")
        else:
            details.append("Data permintaan global tidak tersedia untuk perbandingan")
    elif gap < 0:
        reasons.append("Gap pasar negatif - ekspor produk jadi sudah melebihi permintaan global terdata")
        details.append("Perlu evaluasi lebih lanjut tentang pasar tujuan yang belum terdata")
    else:
        reasons.append(f"Gap pasar kecil (${gap/1_000_000:.2f}M), peluang terbatas")

    # Faktor 2: Pertumbuhan permintaan (30%)
    demand_cagr = analysis['global_demand_trend']
    if demand_cagr > 10:  # >10% CAGR
        score += 30
        reasons.append(f"Pertumbuhan permintaan global sangat tinggi ({demand_cagr:.1f}% CAGR), pasar sedang berkembang pesat")
        details.append("Momentum pasar sangat baik untuk memulai hilirisasi sekarang")
    elif demand_cagr > 5:  # >5% CAGR
        score += 20
        reasons.append(f"Pertumbuhan permintaan global positif ({demand_cagr:.1f}% CAGR)")
        details.append("Pasar menunjukkan tren pertumbuhan yang sehat")
    elif demand_cagr > 0:
        score += 10
        reasons.append(f"Pertumbuhan permintaan global lambat ({demand_cagr:.1f}% CAGR)")
        details.append("Pasar masih tumbuh namun tidak agresif")
    else:
        reasons.append(f"Permintaan global menurun ({demand_cagr:.1f}% CAGR), pasar sedang kontraksi")
        details.append("Risiko tinggi untuk investasi hilirisasi saat ini")

    # Faktor 3: Kemampuan ekspor saat ini (20%)
    current_ratio = (analysis['finished_export_total'] / analysis['raw_export_total'] * 100) if analysis['raw_export_total'] > 0 else 0
    if analysis['finished_export_total'] < analysis['raw_export_total'] * 0.1:
        score += 20
        reasons.append(f"Ekspor produk jadi sangat rendah ({current_ratio:.1f}% dari bahan mentah), potensi nilai tambah sangat besar")
        details.append("Indonesia saat ini lebih banyak mengekspor bahan mentah - kehilangan nilai tambah besar")
    elif analysis['finished_export_total'] < analysis['raw_export_total'] * 0.5:
        score += 10
        reasons.append(f"Ekspor produk jadi masih rendah ({current_ratio:.1f}% dari bahan mentah)")
        details.append("Masih ada ruang signifikan untuk meningkatkan hilirisasi")
    else:
        reasons.append(f"Ekspor produk jadi sudah cukup tinggi ({current_ratio:.1f}% dari bahan mentah)")
        details.append("Industri hilirisasi sudah cukup berkembang")

    # Faktor 4: Ketersediaan bahan mentah (20%)
    raw_export = analysis['raw_export_total']
    if raw_export > 100_000_000:  # > $100M
        score += 20
        reasons.append(f"Ketersediaan bahan mentah sangat mencukupi (${raw_export/1_000_000:.2f}M ekspor per tahun)")
        details.append("Pasokan bahan baku memadai untuk mendukung industri hilirisasi skala besar")
    elif raw_export > 10_000_000:  # > $10M
        score += 10
        reasons.append(f"Ketersediaan bahan mentah mencukupi (${raw_export/1_000_000:.2f}M ekspor per tahun)")
        details.append("Pasokan bahan baku cukup untuk industri hilirisasi skala menengah")
    else:
        reasons.append(f"Ketersediaan bahan mentah terbatas (${raw_export/1_000_000:.2f}M ekspor per tahun)")
        details.append("Perlu evaluasi kecukupan pasokan bahan baku untuk hilirisasi")

    # Logika keputusan
    if score >= 60:
        recommendation['decision'] = 'LAYAK HILIRISASI'
        recommendation['score'] = score
        recommendation['reason'] = '; '.join(reasons)
        recommendation['details'] = details
        recommendation['details'].append("💡 Rekomendasi: Segera mulai investasi hilirisasi atau tingkatkan kapasitas yang ada")
    else:
        recommendation['decision'] = 'TIDAK LAYAK HILIRISASI'
        recommendation['score'] = score
        if not reasons:
            recommendation['reason'] = 'Faktor-faktor ekonomi belum mendukung hilirisasi'
        else:
            recommendation['reason'] = '; '.join(reasons)
        recommendation['details'] = details
        recommendation['details'].append("⚠️ Rekomendasi: Tunda investasi hilirisasi hingga kondisi pasar lebih mendukung, atau fokus pada peningkatan kualitas bahan mentah")

    return recommendation


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

    # Metrik utama
    st.markdown("### 💹 Metrik Utama")

    # Tampilkan warning year alignment jika berlaku
    if 'aligned_years' in results['analysis'] and 'excluded_years' in results['analysis']:
        aligned_years = results['analysis']['aligned_years']
        excluded = results['analysis']['excluded_years']

        if excluded['global_only']:
            st.warning(f"""
            ⚠️ **Penyesuaian Data Perbandingan:** Permintaan Global memiliki data untuk tahun {', '.join(map(str, excluded['global_only']))},
            tetapi data Ekspor Indonesia untuk tahun tersebut belum tersedia di UN Comtrade.
            
            📊 **Data tahun tersebut tetap ditampilkan di grafik** (garis putus-putus), namun **tidak digunakan dalam perhitungan metrik** 
            (total, CAGR, gap pasar).
            
            Perbandingan metrik hanya menggunakan tahun {aligned_years[0]}-{aligned_years[-1]} dimana KEDUA dataset memiliki data.
            """)
        elif excluded['indonesia_only']:
            st.info(f"""
            ℹ️ **Penyesuaian Data Perbandingan:** Data Ekspor Indonesia memiliki data untuk tahun {', '.join(map(str, excluded['indonesia_only']))},
            tetapi data Permintaan Global untuk tahun tersebut belum tersedia.
            
            📊 **Data tahun tersebut tetap ditampilkan di grafik** (garis putus-putus), namun **tidak digunakan dalam perhitungan metrik** 
            (total, CAGR, gap pasar).
            
            Perbandingan metrik menggunakan tahun {aligned_years[0]}-{aligned_years[-1]} dimana KEDUA dataset memiliki data.
            """)

        if aligned_years:
            st.caption(f"📅 Rentang tahun analisis: **{aligned_years[0]} - {aligned_years[-1]}** ({len(aligned_years)} tahun)")

    # Ambil nama produk dari hasil AI
    raw_product_name = ""
    semi_product_name = ""
    finished_product_name = ""

    if 'ai_result' in results:
        raw_product_name = results['ai_result'].get('raw_material', '')
        semi_product_name = results['ai_result'].get('semi_finished', '')
        finished_product_name = results['ai_result'].get('finished_product', '')

    col1, col2, col3, col4, col5 = st.columns(5)

    with col1:
        st.metric(
            f"Ekspor Bahan Mentah",
            format_currency_compact(results['analysis']['raw_export_total']),
            f"{results['analysis']['raw_export_trend']:.1f}% CAGR"
        )
        st.caption(f"📦 {raw_product_name}")

    with col2:
        st.metric(
            f"Ekspor Setengah Jadi",
            format_currency_compact(results['analysis'].get('semi_export_total', 0)),
            f"{results['analysis'].get('semi_export_trend', 0):.1f}% CAGR"
        )
        st.caption(f"🔧 {semi_product_name}")

    with col3:
        st.metric(
            f"Ekspor Produk Jadi",
            format_currency_compact(results['analysis']['finished_export_total']),
            f"{results['analysis'].get('finished_export_trend', 0):.1f}% CAGR"
        )
        st.caption(f"✨ {finished_product_name}")

    with col4:
        st.metric(
            "Permintaan Global",
            format_currency_compact(results['analysis']['global_demand_total']),
            f"{results['analysis']['global_demand_trend']:.1f}% CAGR"
        )
        st.caption(f"🌍 {finished_product_name}")

    with col5:
        st.metric(
            "Gap Pasar (Peluang)",
            format_currency_compact(results['analysis']['market_gap'])
        )
        st.caption(f"💡 {finished_product_name}")

    # Rekomendasi
    st.markdown("---")
    st.markdown("### 🎯 Rekomendasi")

    rec = results['recommendation']
    is_positive = rec['decision'] == 'LAYAK HILIRISASI'

    box_class = "recommendation-positive" if is_positive else "recommendation-negative"
    icon = "✅" if is_positive else "❌"

    st.markdown(f"""
    <div class="recommendation-box {box_class}">
        {icon} <strong>{rec['decision']}</strong> (Skor: {rec['score']}/100)
    </div>
    """, unsafe_allow_html=True)

    # Alasan detail
    st.markdown("#### 📋 Alasan:")
    reasoning_points = rec['reason'].split(';') if ';' in rec['reason'] else [rec['reason']]
    for point in reasoning_points:
        if point.strip():
            st.markdown(f"- {point.strip()}")

    # Pertimbangan tambahan
    if 'details' in rec and rec['details']:
        st.markdown("#### 💡 Pertimbangan Tambahan:")
        for detail in rec['details']:
            st.markdown(f"- {detail}")

    # Ringkasan AI
    st.markdown("---")
    st.markdown("### 🤖 Ringkasan Analisis AI")
    st.markdown(results['ai_summary'])

    # Visualisasi
    st.markdown("---")
    st.markdown("### 📈 Visualisasi Data")

    # Buat visualisasi jika data tersedia
    render_visualizations(results['protocol_data'], results['analysis'])


def render_visualizations(data: dict, analysis: dict):
    """
    Render data visualizations as line charts with time series

    Args:
        data: Protocol data containing time series export/import data
        analysis: Analysis results
    """
    # Ekstrak data time series dari protocol
    raw_exports = data.get('indonesia_raw_export', pd.DataFrame())
    semi_exports = data.get('indonesia_semi_export', pd.DataFrame())
    finished_exports = data.get('indonesia_finished_export', pd.DataFrame())
    global_imports = data.get('world_finished_import', pd.DataFrame())

    # Ambil tahun yang selaras untuk filter
    aligned_years = analysis.get('aligned_years', [])
    excluded_years = analysis.get('excluded_years', {'indonesia_only': [], 'global_only': []})

    # Proses data per tahun
    def aggregate_by_year(df):
        if df.empty or 'period' not in df.columns or 'primaryValue' not in df.columns:
            return pd.DataFrame()

        yearly = df.groupby('period')['primaryValue'].sum().reset_index()
        yearly.columns = ['Year', 'Value']
        yearly = yearly.sort_values('Year')
        return yearly

    # Tampilkan SEMUA tahun yang tersedia 
    raw_yearly = aggregate_by_year(raw_exports)
    semi_yearly = aggregate_by_year(semi_exports)
    finished_yearly = aggregate_by_year(finished_exports)
    global_yearly = aggregate_by_year(global_imports)

    col1, col2 = st.columns(2)

    with col1:
        # Grafik 1: Tren ekspor per tahun
        st.markdown("#### 📊 Tren Ekspor Indonesia (Rentang Waktu)")

        fig = go.Figure()

        if not raw_yearly.empty:
            fig.add_trace(go.Scatter(
                x=raw_yearly['Year'],
                y=raw_yearly['Value'],
                mode='lines+markers',
                name='Bahan Mentah',
                line=dict(color='#ff7f0e', width=3),
                marker=dict(size=8)
            ))

        if not semi_yearly.empty:
            fig.add_trace(go.Scatter(
                x=semi_yearly['Year'],
                y=semi_yearly['Value'],
                mode='lines+markers',
                name='Setengah Jadi',
                line=dict(color='#9467bd', width=3),
                marker=dict(size=8)
            ))

        if not finished_yearly.empty:
            fig.add_trace(go.Scatter(
                x=finished_yearly['Year'],
                y=finished_yearly['Value'],
                mode='lines+markers',
                name='Produk Jadi',
                line=dict(color='#2ca02c', width=3),
                marker=dict(size=8)
            ))

        fig.update_layout(
            xaxis_title="Tahun",
            yaxis_title="Nilai Ekspor (USD)",
            height=450,
            hovermode='x unified',
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="center",
                x=0.5
            )
        )

        if raw_yearly.empty and semi_yearly.empty and finished_yearly.empty:
            st.warning("Tidak ada data ekspor untuk ditampilkan")
        else:
            st.plotly_chart(fig, width='stretch')

    with col2:
        # Grafik 2: Gap pasar dan tren permintaan
        st.markdown("#### 🌍 Permintaan Global vs Ekspor Indonesia")

        fig = go.Figure()

        # Tampilkan SEMUA data global 
        if not global_yearly.empty:
            # Pisahkan data berdasarkan aligned dan non-aligned years
            global_aligned = global_yearly[global_yearly['Year'].isin(aligned_years)] if aligned_years else global_yearly
            global_only = global_yearly[global_yearly['Year'].isin(excluded_years['global_only'])] if excluded_years['global_only'] else pd.DataFrame()
            
            # Data yang dibandingkan 
            if not global_aligned.empty:
                fig.add_trace(go.Scatter(
                    x=global_aligned['Year'],
                    y=global_aligned['Value'],
                    mode='lines+markers',
                    name='Permintaan Global (dibandingkan)',
                    line=dict(color='#1f77b4', width=3),
                    marker=dict(size=8),
                    fill='tozeroy',
                    fillcolor='rgba(31, 119, 180, 0.1)'
                ))
            
            # Data yang TIDAK dibandingkan 
            if not global_only.empty:
                fig.add_trace(go.Scatter(
                    x=global_only['Year'],
                    y=global_only['Value'],
                    mode='lines+markers',
                    name='Permintaan Global (tidak dibandingkan)',
                    line=dict(color='#1f77b4', width=2, dash='dash'),
                    marker=dict(size=6, symbol='circle-open'),
                    opacity=0.6
                ))

        # Tampilkan SEMUA data Indonesia
        if not finished_yearly.empty:
            # Pisahkan data berdasarkan aligned dan non-aligned years
            finished_aligned = finished_yearly[finished_yearly['Year'].isin(aligned_years)] if aligned_years else finished_yearly
            finished_only = finished_yearly[finished_yearly['Year'].isin(excluded_years['indonesia_only'])] if excluded_years['indonesia_only'] else pd.DataFrame()
            
            # Data yang dibandingkan 
            if not finished_aligned.empty:
                fig.add_trace(go.Scatter(
                    x=finished_aligned['Year'],
                    y=finished_aligned['Value'],
                    mode='lines+markers',
                    name='Ekspor Indonesia (dibandingkan)',
                    line=dict(color='#2ca02c', width=3),
                    marker=dict(size=8)
                ))
            
            # Data yang TIDAK dibandingkan 
            if not finished_only.empty:
                fig.add_trace(go.Scatter(
                    x=finished_only['Year'],
                    y=finished_only['Value'],
                    mode='lines+markers',
                    name='Ekspor Indonesia (tidak dibandingkan)',
                    line=dict(color='#2ca02c', width=2, dash='dash'),
                    marker=dict(size=6, symbol='circle-open'),
                    opacity=0.6
                ))

        fig.update_layout(
            xaxis_title="Tahun",
            yaxis_title="Nilai (USD)",
            height=450,
            hovermode='x unified',
            legend=dict(
                orientation="v",
                yanchor="top",
                y=0.99,
                xanchor="left",
                x=0.01,
                bgcolor='rgba(255, 255, 255, 0.8)'
            )
        )

        if global_yearly.empty and finished_yearly.empty:
            st.warning("Tidak ada data permintaan global untuk ditampilkan")
        else:
            st.plotly_chart(fig, width='stretch')
            
            # Tampilkan keterangan
            if excluded_years['global_only'] or excluded_years['indonesia_only']:
                st.caption(" Garis putus-putus menunjukkan data yang ditampilkan tetapi tidak digunakan dalam perhitungan metrik karena tidak ada data pembanding.")


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
