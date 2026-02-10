"""
Modul AI Service untuk Integrasi Google Gemini
Menangani pemahaman bahasa natural untuk klasifikasi komoditas
"""

import os
import threading
from google import genai
from google.genai import types
from typing import Dict, List, Optional
import logging
import json

# Konfigurasi logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Lock threading untuk singleton
_gemini_lock = threading.Lock()


class GeminiService:
    """
    Service class untuk interaksi dengan Google Gemini API
    Mengekstrak keyword komoditas dan klasifikasi tahap pemrosesan
    """

    def __init__(self, api_key: Optional[str] = None):
        """
        Inisialisasi Gemini service

        Args:
            api_key: Google Gemini API key (jika None, muat dari env)
        """
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")

        if not self.api_key:
            raise ValueError("GEMINI_API_KEY not found in environment")

        self.client = genai.Client(api_key=self.api_key)

        logger.info("Gemini service berhasil diinisialisasi")

    def extract_commodity_keywords(self, user_input: str) -> Dict:
        """
        Ekstrak informasi komoditas dan HS codes dari input user menggunakan Gemini.
        Gemini langsung memberikan HS codes berdasarkan UN Comtrade classification.
        Tidak lagi menggunakan TF-IDF matching.

        Args:
            user_input: Input bahasa natural dari user (misal: "kelapa", "tebu", "nira kelapa")

        Returns:
            Dictionary berisi keyword hasil ekstraksi, tahap pemrosesan, dan HS codes
        """
        logger.info(f"Menggunakan Gemini AI untuk analisis + HS Code extraction: {user_input}")
        
        prompt = f"""
Kamu adalah konsultan strategi ekonomi ekspor Indonesia DAN ahli klasifikasi HS Code (Harmonized System) berdasarkan UN Comtrade.

Input Pengguna: "{user_input}"

INSTRUKSI PENTING:
1. DETEKSI kategori input user: Apakah ini bahan mentah, setengah jadi, atau produk jadi?
2. PAHAMI bahan yang dimaksud user - jangan loncat ke bagian/produk lain dari komoditas yang sama
   Contoh: "batok kelapa" ≠ "daging kelapa", "daun pisang" ≠ "buah pisang"
3. Identifikasi jalur transformasi yang KOHEREN: produk setengah jadi dan jadi HARUS hasil pengolahan dari bahan input, bukan produk terpisah
4. Dari jalur-jalur KOHEREN tersebut, pilih yang REALISTIS dan UMUM dilakukan (pertimbangkan industri existing dan penggunaan tradisional/lokal)
5. Evaluasi nilai tambah ekonomi HANYA dari jalur yang koheren - pilih SATU jalur dengan nilai ekonomi tertinggi DAN feasibility tinggi
6. SELALU berikan full chain: bahan mentah → setengah jadi → produk jadi (meskipun input user di tengah rantai)
7. **BERIKAN HS CODE YANG TEPAT** untuk setiap tahap (raw, semi, finished) berdasarkan UN Comtrade HS Classification

**CRITICAL - KOHERENSI JALUR:**
BENAR: Batok kelapa → Arang tempurung → Karbon aktif (transformasi langsung)
SALAH: Batok kelapa → Minyak kelapa (minyak dari daging buah, bukan batok)
BENAR: Daun pisang → Daun dipotong/dibersihkan → Piring/wadah disposable
SALAH: Daun pisang → Pisang goreng (produk dari buah, bukan daun)
BENAR: Kulit kayu manis → Bubuk kayu manis → Minyak esensial kayu manis
SALAH: Kulit kayu manis → Furniture kayu (furniture dari kayu batang, bukan kulit)

**PENTING - KONTEKS INDONESIA & PENGGUNAAN AKTUAL:**
- Prioritaskan jalur pemrosesan yang SUDAH ADA industrinya atau UMUM digunakan secara tradisional
- Pertimbangkan kegunaan aktual di pasar (lokal & global), bukan hanya kemungkinan teoretis
- Untuk bahan alami/tradisional: cek penggunaan eksisting sebelum mengasumsikan proses industri modern
- Untuk bahan mineral: ikuti jalur industri standar yang sudah established
- Jika komoditas bisa diproses berbagai jalur, pilih yang paling feasible dan profitable

**PRINSIP PEMILIHAN JALUR:**
PILIH: Jalur dengan industri yang sudah ada (proven market)
PILIH: Penggunaan tradisional yang memiliki nilai ekonomi tinggi
PILIH: Transformasi yang umum dilakukan secara komersial
HINDARI: Jalur teoretis yang jarang/tidak dipraktikkan di industri
HINDARI: Proses yang hanya mungkin secara kimia tapi tidak ekonomis
HINDARI: Asumsi penggunaan yang tidak sesuai karakteristik fisik bahan

**CRITICAL - HS CODE RULES:**
- HS Code HARUS berdasarkan klasifikasi UN Comtrade (Harmonized System)
- Berikan HS code dengan format lengkap (bisa pakai titik, misal: "0801.12" atau "1704.10.00")
- Berikan BEBERAPA alternatif HS code untuk setiap tahap (minimal 2-3 kode per tahap)
- HS codes harus sesuai BENTUK FISIK dan KEGUNAAN AKTUAL produk, bukan hanya komposisi kimia
- Prioritaskan kode berdasarkan bagaimana produk DIPERDAGANGKAN dan DIGUNAKAN
- Jika produk bisa masuk beberapa chapter, pilih yang paling spesifik untuk bentuk akhirnya

**CONTOH HS CODE YANG BENAR:**
- Produk pertanian segar: Chapter 06-14 (sesuai jenis tanaman)
- Minyak nabati/hewani: Chapter 15 
- Produk kimia: Chapter 28-38 (sesuai jenis kimia)
- Produk kertas/pulp: Chapter 47-48
- Produk anyaman/pressed dari tumbuhan: Chapter 46
- Makanan olahan: Chapter 16-24
- Sabun/kosmetik: Chapter 33-34

**CONTOH FORMAT HS CODE:**
Kode bisa dalam format: "0801.12", "08.01", "0801", "080112", "1513.11.00"
Semua format diterima - sistem akan membersihkan otomatis.

Berikan respons dalam format JSON dengan struktur berikut:
{{
    "commodity_name": "nama komoditas (English, generic category)",
    "input_stage": "raw/semi/finished",
    "raw_material": "deskripsi bahan mentah (English)",
    "semi_finished": "deskripsi produk setengah jadi (English)",
    "finished_product": "deskripsi produk jadi (English)",
    "keywords": ["keyword1", "keyword2", "keyword3"],
    "raw_hs_codes": [
        {{"code": "0801.12", "description": "Coconuts, in the inner shell (endocarp)"}},
        {{"code": "0801.19", "description": "Coconuts, other"}}
    ],
    "semi_hs_codes": [
        {{"code": "1513.11", "description": "Coconut (copra) oil, crude"}},
        {{"code": "1513.19", "description": "Coconut (copra) oil, other than crude"}}
    ],
    "finished_hs_codes": [
        {{"code": "3401.11", "description": "Soap and organic surface-active products, for toilet use"}},
        {{"code": "3401.19", "description": "Soap, other"}}
    ],
    "industry_category": "agriculture/mining/manufacturing",
    "selected_path_reason": "alasan pemilihan jalur (1-2 kalimat)",
    "user_position_note": "catatan posisi input (null jika raw)"
}}

PENTING untuk HS codes:
- WAJIB berikan minimal 2 kode per tahap (raw, semi, finished)
- Kode harus AKURAT berdasarkan UN Comtrade Harmonized System DAN sesuai BENTUK FISIK produk
- Sertakan deskripsi singkat untuk setiap kode
- Jika tidak yakin dengan kode spesifik, berikan kode chapter/heading (4-digit) yang paling mendekati
- Untuk komoditas niche, berikan kode kategori terdekat yang pasti ada di UN Comtrade
- PRIORITASKAN kode berdasarkan KEGUNAAN dan BENTUK AKHIR, bukan hanya komposisi material

LANGKAH ANALISIS:
1. Verifikasi apakah jalur pemrosesan yang kamu pikirkan BENAR-BENAR umum dilakukan (cek industri Indonesia & global)
2. Pastikan produk setengah jadi & jadi adalah bentuk yang REALISTIS dari bahan mentah tersebut
3. HS code harus sesuai dengan bentuk fisik dan kegunaan aktual produk di pasar

Sekarang analisis input pengguna "{user_input}" dengan mempertimbangkan konteks Indonesia dan penggunaan aktual di industri:
"""

        try:
            response = self.client.models.generate_content(
                model='models/gemini-2.5-flash',
                contents=prompt
            )
            result_text = response.text.strip()

            # Parse JSON dari respons API
            # Hapus markdown code blocks jika ada
            if "```json" in result_text:
                result_text = result_text.split("```json")[1].split("```")[0].strip()
            elif "```" in result_text:
                result_text = result_text.split("```")[1].split("```")[0].strip()

            result = json.loads(result_text)

            logger.info(f"Successfully extracted keywords for: {user_input}")
            return result

        except json.JSONDecodeError as e:
            logger.error(f"Gagal parse JSON response: {e}")
            # Fallback: kembalikan struktur dasar
            return {
                "commodity_name": user_input,
                "input_stage": "raw",
                "raw_material": user_input,
                "semi_finished": f"{user_input} processed",
                "finished_product": f"{user_input} finished",
                "keywords": [user_input],
                "raw_hs_codes": [],
                "semi_hs_codes": [],
                "finished_hs_codes": [],
                "industry_category": "manufacturing",
                "selected_path_reason": "Default path selected based on user input",
                "user_position_note": None
            }
        except Exception as e:
            logger.error(f"Error saat memanggil Gemini API: {e}")
            raise

    def generate_analysis_summary(
        self,
        commodity: str,
        raw_data: Dict,
        finished_data: Dict,
        recommendations: Dict
    ) -> str:
        """
        Generate ringkasan analisis yang mudah dibaca menggunakan Gemini

        Args:
            commodity: Nama komoditas
            raw_data: Data ekspor bahan mentah
            finished_data: Data ekspor/impor produk jadi
            recommendations: Rekomendasi analisis

        Returns:
            Ringkasan bahasa natural
        """
        prompt = f"""
Kamu adalah analis ekonomi ekspor Indonesia. Buatkan ringkasan analisis hilirisasi untuk komoditas berikut:

KOMODITAS: {commodity}

DATA BAHAN MENTAH (Ekspor Indonesia):
- Total Nilai: ${raw_data.get('total_value', 0):,.2f}
- Trend Pertumbuhan (CAGR): {raw_data.get('cagr', 0)}%

DATA PRODUK JADI:
- Ekspor Indonesia: ${finished_data.get('export_value', 0):,.2f}
- Impor Dunia (Demand): ${finished_data.get('world_import', 0):,.2f}
- Gap (Peluang): ${finished_data.get('gap', 0):,.2f}
- Trend Pertumbuhan (CAGR): {finished_data.get('cagr', 0)}%

REKOMENDASI: {recommendations.get('decision', 'N/A')}
ALASAN UTAMA: {recommendations.get('reason', 'N/A')}

Buatkan ringkasan analisis dalam 3-4 paragraf yang mudah dipahami, mencakup:
1. Kondisi ekspor bahan mentah saat ini
2. Analisis permintaan global untuk produk jadi
3. Potensi nilai tambah ekonomi dari hilirisasi
4. Rekomendasi strategis

Gunakan bahasa yang profesional namun mudah dipahami untuk pembuat keputusan bisnis.
"""

        try:
            response = self.client.models.generate_content(
                model='models/gemini-2.5-flash',
                contents=prompt
            )
            summary = response.text.strip()

            logger.info(f"Generated analysis summary for: {commodity}")
            return summary

        except Exception as e:
            logger.error(f"Error saat membuat summary: {e}")
            return "Error saat membuat ringkasan analisis. Silakan cek log."

    def classify_processing_stage(self, description: str) -> str:
        """
        Klasifikasi deskripsi HS code ke tahap pemrosesan (raw/semi/finished)

        Args:
            description: Deskripsi HS code

        Returns:
            Tahap pemrosesan: 'raw', 'semi', atau 'finished'
        """
        prompt = f"""
Klasifikasikan deskripsi produk berikut ke dalam salah satu kategori:
- "raw": Bahan mentah (belum diproses, bentuk alami)
- "semi": Setengah jadi (sudah diproses sebagian)
- "finished": Produk jadi (siap konsumsi/pakai)

Deskripsi: "{description}"

Jawab hanya dengan satu kata: raw, semi, atau finished
"""

        try:
            response = self.client.models.generate_content(
                model='models/gemini-2.5-flash',
                contents=prompt
            )
            stage = response.text.strip().lower()

            if stage in ['raw', 'semi', 'finished']:
                return stage
            else:
                # Fallback default
                if any(word in description.lower() for word in ['crude', 'ore', 'raw', 'fresh', 'live']):
                    return 'raw'
                elif any(word in description.lower() for word in ['processed', 'refined', 'matte', 'semi']):
                    return 'semi'
                else:
                    return 'finished'

        except Exception as e:
            logger.error(f"Error classifying stage: {e}")
            return 'raw'  # Fallback default


# Instance singleton
_gemini_service: Optional[GeminiService] = None


def get_gemini_service() -> GeminiService:
    """
    Ambil atau buat Gemini service singleton (thread-safe)

    Returns:
        Instance GeminiService
    """
    global _gemini_service

    if _gemini_service is None:
        with _gemini_lock:  # Inisialisasi thread-safe
            if _gemini_service is None:  # Pola double-check
                _gemini_service = GeminiService()

    return _gemini_service
