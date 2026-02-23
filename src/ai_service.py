"""
Modul AI Service untuk Integrasi Google Gemini
Menangani pemahaman bahasa natural untuk klasifikasi komoditas
"""

import os
import threading
import google.generativeai as genai
from google.generativeai import types
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
        Inisialisasi Gemini service dengan smart load balancing

        Args:
            api_key: Google Gemini API key (jika None, muat dari env)
        """
        self.api_keys = [
            api_key or os.getenv("GEMINI_API_KEY"),
            os.getenv("GEMINI_API_KEY_BACKUP")
        ]
        
        # Remove None values
        self.api_keys = [key for key in self.api_keys if key]
        
        if not self.api_keys:
            raise ValueError("No GEMINI_API_KEY found in environment")

        # Initialize all clients for faster switching
        self.clients = {}
        self.current_key_index = 0
        
        for i, key in enumerate(self.api_keys):
            try:
                genai.configure(api_key=key)
                self.clients[key] = genai.GenerativeModel('gemini-pro')
                logger.info(f"Gemini client {i+1} initialized successfully")
            except Exception as e:
                logger.warning(f"Failed to initialize Gemini client {i+1}: {e}")
        
        if not self.clients:
            raise ValueError("All Gemini API keys failed to initialize")
        
        # Start with primary client
        self.client = self.clients[self.api_keys[0]]
        self.api_key = self.api_keys[0]
        logger.info("Gemini service initialized with smart load balancing")

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
            response = self.client.generate_content(
                prompt
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

        except Exception as e:
            error_msg = str(e).lower()
            
            # Check for quota/rate limit errors - switch immediately to backup
            quota_indicators = [
                'quota exceeded', 'rate limit', 'resource exhausted', 
                'billing', 'insufficient_quota', 'quota_exceeded',
                '429', 'rate_limit_exceeded'
            ]
            
            is_quota_error = any(indicator in error_msg for indicator in quota_indicators)
            
            if is_quota_error:
                logger.warning(f"Quota error detected with current key, switching to backup immediately: {e}")
                
                # Try backup keys immediately for quota issues
                for backup_key in self.api_keys:
                    if backup_key == self.api_key:
                        continue
                        
                    try:
                        logger.info(f"Trying backup Gemini API key for quota issue...")
                        backup_client = self.clients.get(backup_key)
                        if not backup_client:
                            logger.warning(f"Backup client not available for key: {backup_key[:20]}...")
                            continue
                            
                        response = backup_client.models.generate_content(
                            model='models/gemini-2.5-flash',
                            contents=prompt
                        )
                        result_text = response.text.strip()
                        
                        # Parse JSON
                        if "```json" in result_text:
                            result_text = result_text.split("```json")[1].split("```")[0].strip()
                        elif "```" in result_text:
                            result_text = result_text.split("```")[1].split("```")[0].strip()

                        result = json.loads(result_text)
                        
                        logger.info(f"Successfully extracted keywords using backup key: {user_input}")
                        
                        # Switch to backup key as primary for future requests
                        self.client = backup_client
                        self.api_key = backup_key
                        self.current_key_index = self.api_keys.index(backup_key)
                        
                        return result
                        
                    except Exception as backup_e:
                        logger.warning(f"Backup Gemini API key also failed: {backup_e}")
                        continue
                
                # If all keys failed, return fallback
                logger.error(f"All Gemini API keys failed for quota issue: {user_input}")
                return self._get_fallback_result(user_input)
            else:
                # For non-quota errors, try other keys as well
                logger.warning(f"Non-quota error with current key, trying backups: {e}")
                
                for backup_key in self.api_keys:
                    if backup_key == self.api_key:
                        continue
                        
                    try:
                        logger.info(f"Trying backup Gemini API key for general error...")
                        backup_client = self.clients.get(backup_key)
                        if not backup_client:
                            continue
                            
                        response = backup_client.models.generate_content(
                            model='models/gemini-2.5-flash',
                            contents=prompt
                        )
                        result_text = response.text.strip()
                        
                        # Parse JSON
                        if "```json" in result_text:
                            result_text = result_text.split("```json")[1].split("```")[0].strip()
                        elif "```" in result_text:
                            result_text = result_text.split("```")[1].split("```")[0].strip()

                        result = json.loads(result_text)
                        
                        logger.info(f"Successfully extracted keywords using backup key: {user_input}")
                        return result
                        
                    except Exception as backup_e:
                        logger.warning(f"Backup Gemini API key also failed: {backup_e}")
                        continue
                
                # If all keys failed, return fallback
                logger.error(f"All Gemini API keys failed for input: {user_input}")
                return self._get_fallback_result(user_input)

    def _get_fallback_result(self, user_input: str) -> Dict:
        """
        Return fallback result when all API keys fail
        
        Args:
            user_input: Original user input
            
        Returns:
            Fallback dictionary result
        """
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
            "selected_path_reason": "Default path selected due to API failure",
            "user_position_note": None
        }

    def generate_analysis_summary(
        self,
        commodity: str,
        optimization_results: Dict
    ) -> str:
        """
        Generate ringkasan analisis yang mudah dibaca menggunakan Gemini
        Berdasarkan hasil optimasi matematis Gurobi

        Args:
            commodity: Nama komoditas
            optimization_results: Hasil optimasi dari Gurobi (raw, semi, finished)

        Returns:
            Ringkasan bahasa natural
        """
        prompt = f"""
Kamu adalah analis ekonomi ekspor Indonesia. Buatkan ringkasan analisis hilirisasi untuk komoditas berikut berdasarkan hasil optimasi matematis:

KOMODITAS: {commodity}

HASIL OPTIMASI MATEMATIS (Gurobi):

"""
        # Tambahkan data untuk setiap stage yang ada
        stages = [('raw', 'Bahan Mentah'), ('semi', 'Setengah Jadi'), ('finished', 'Produk Jadi')]

        for stage_key, stage_name in stages:
            if stage_key in optimization_results:
                opt = optimization_results[stage_key]
                if opt.get('status') == 'Optimal':
                    prompt += f"""
{stage_name.upper()}:
- Potensi Devisa: ${opt.get('total_revenue', 0):,.2f}
- Volume Alokasi: {opt.get('total_volume', 0):,.2f} kg
- Strategi: {opt.get('strategy', 'N/A')}
"""
                else:
                    prompt += f"""
{stage_name.upper()}: Optimasi gagal - {opt.get('reason', 'Unknown error')}
"""

        prompt += """

Buatkan ringkasan analisis dalam 3-4 paragraf yang mudah dipahami, mencakup:
1. Potensi ekonomi dari optimasi matematis untuk setiap tahap
2. Strategi yang direkomendasikan (B1: Competitor Displacement atau B3: Price Arbitrage)
3. Volume dan nilai devisa yang dapat dicapai
4. Rekomendasi implementasi strategis

Gunakan bahasa yang profesional namun mudah dipahami untuk pembuat keputusan bisnis dan fokus pada hasil optimasi matematis.
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
