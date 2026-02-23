# Sistem Pendukung Keputusan Hilirisasi Ekspor (Export Downstreaming DSS)

![Python](https://img.shields.io/badge/Python-3.10%2B-blue)
![Streamlit](https://img.shields.io/badge/Frontend-Streamlit-red)
![AI](https://img.shields.io/badge/AI-Google%20Gemini-orange)

Aplikasi web berbasis AI untuk menganalisis potensi hilirisasi ekspor komoditas Indonesia. Sistem ini menggunakan **Google Gemini AI** untuk memahami input natural language, mengklasifikasikan HS Code secara otomatis, dan memberikan rekomendasi berdasarkan data perdagangan UN Comtrade.

**Key Features:**
- AI HS Code classification 
- Trade data analysis from UN Comtrade API
- 🇮🇩 Context-aware untuk komoditas tradisional Indonesia
- Decision support: LAYAK dan TIDAK LAYAK hilirisasi

---

## Tentang Proyek

Aplikasi ini menggabungkan tiga komponen:
1. **Google Gemini AI** -- Memahami input user dalam bahasa natural, mengekstrak konteks rantai pasok (bahan mentah, setengah jadi, produk jadi), dan **langsung memberikan HS Code** yang tepat untuk setiap tahap.
2. **UN Comtrade API** -- Mengambil data statistik perdagangan internasional berdasarkan HS Code dari AI.
3. **MySQL Database** -- Caching hasil untuk mengurangi pemakaian API quota.

Hasil akhir berupa rekomendasi **LAYAK** atau **TIDAK LAYAK HILIRISASI** berdasarkan data perdagangan aktual.

---

## Fitur

### 1. AI-Direct HS Code Extraction
* User memasukkan nama komoditas bebas (misal: "Kelapa", "Daun Pisang", "Batok Kelapa").
* Gemini AI menganalisis komoditas dan **langsung memberikan HS Code** yang tepat untuk setiap tahap (raw/semi/finished).
* AI mempertimbangkan:
  - Konteks Indonesia dan penggunaan aktual (tradisional vs industri modern)
  - Koherensi jalur transformasi (produk harus hasil pengolahan langsung dari bahan input)
  - Kelayakan ekonomi dan industri yang sudah ada
  - Bentuk fisik dan kegunaan aktual produk di pasar

### 2. Data Mining (4-Request Protocol)
* Request 1-3: Ekspor Indonesia untuk bahan mentah, setengah jadi, dan produk jadi.
* Request 4: Impor dunia untuk produk jadi (global demand).
* Analisis tren 5 tahun terakhir.

### 3. Caching (MySQL)
* Response API disimpan lokal dengan TTL 30 hari.
* Mengurangi pemakaian kuota API pada pencarian berulang.
* Skema database dibuat otomatis saat aplikasi pertama kali dijalankan.

### 4. Decision Support
Rekomendasi berdasarkan:
* **Value Added** -- Selisih harga satuan ($/kg) produk jadi vs mentah.
* **CAGR** -- Compound Annual Growth Rate 5 tahun terakhir.
* **Market Gap** -- Selisih antara demand global dan supply domestik.

---

## Arsitektur Sistem

### Diagram 3-Layer

```
┌─────────────────────────────────────────────────────────────────┐
│                     PRESENTATION LAYER                          │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  Streamlit Web Dashboard                                 │  │
│  │  - Input Form | Charts (Plotly) | Metrics | Rekomendasi  │  │
│  └──────────────────────────────────────────────────────────┘  │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         v
┌─────────────────────────────────────────────────────────────────┐
│                     BUSINESS LOGIC LAYER                        │
│  ┌─────────────────┐  ┌──────────────┐  ┌──────────────────┐   │
│  │  AI Service     │  │ Data Miner   │  │ Decision Engine  │   │
│  │  (Gemini API)   │  │ (Comtrade)   │  │ (Rule-Based)     │   │
│  │  - Extraction   │  │ - 4-Request  │  │ - Scoring        │   │
│  │  - HS Code      │  │ - Rate Limit │  │ - Recommendation │   │
│  │    Direct       │  │ - Retry      │  │                  │   │
│  └─────────────────┘  └──────────────┘  └──────────────────┘   │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  Utils (utils.py)                                        │  │
│  │  - HS Code Cleaning | CAGR | Value Added | Formatting   │  │
│  └──────────────────────────────────────────────────────────┘  │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         v
┌─────────────────────────────────────────────────────────────────┐
│                       DATA LAYER                                │
│  ┌──────────────┐                        ┌─────────────────┐    │
│  │ MySQL DB     │                        │ External APIs   │    │
│  │ - 3 Tables   │                        │ - UN Comtrade   │    │
│  │ - Caching    │                        │ - Gemini AI     │    │
│  │              │                        │                 │    │
│  └──────────────┘                        └─────────────────┘    │
└─────────────────────────────────────────────────────────────────┘
```

### Alur Kerja

```
User Input (nama komoditas)
        |
        v
  Cache ada? --YES--> Ambil dari DB --> Dashboard
        |
       NO
        |
        v
  Gemini AI --> Ekstrak keywords + HS Codes
        |         - Analisis jalur transformasi koheren
        |         - Pertimbangkan konteks Indonesia & penggunaan aktual
        |         - Output: raw/semi/finished descriptions + HS codes
        v
  Clean HS Codes --> Format 6-digit untuk UN Comtrade
        |              - Hapus titik (0801.12 → 080112)
        |              - Padding zeros jika <6 digit
        v
  Simpan ke DB Cache
        |
        v
  UN Comtrade API (4 request)
        |  1. Ekspor ID - Raw
        |  2. Ekspor ID - Semi
        |  3. Ekspor ID - Finished
        |  4. Impor Dunia - Finished
        v
  Data Processing --> CAGR, Value Added, Market Gap
        |
        v
  Decision Engine --> LAYAK / TIDAK LAYAK
        |
        v
  Streamlit Dashboard
```

### Stack Teknologi

| Komponen | Teknologi | Fungsi |
|----------|-----------|--------|
| **Bahasa** | Python 3.10+ | Core logic dan data processing |
| **Frontend** | Streamlit | Dashboard interaktif |
| **AI** | Google Gemini 2.5 Flash | Ekstraksi keyword + HS Code classification |
| **Data Source** | UN Comtrade API | Statistik perdagangan internasional |
| **Database** | MySQL | Caching dan data persistence |
| **Visualization** | Plotly | Grafik interaktif |

### Penjelasan Per Layer

#### Layer 1: Presentation (Frontend)
- **Streamlit Dashboard**: Interface untuk input komoditas dan tampilan hasil.
- **Plotly Charts**: Grafik tren ekspor/impor, perbandingan harga.
- **Output**: Rekomendasi dengan skor dan penjelasan.

#### Layer 2: Business Logic (Backend)

**AI Service (`ai_service.py`)**
- Menggunakan Google Gemini untuk mengekstrak keyword DAN **HS Code** langsung dari input user.
- Output: nama komoditas, deskripsi per stage (raw/semi/finished), keywords, dan **array HS codes dengan descriptions** per stage.
- AI mempertimbangkan:
  - Koherensi jalur: produk setengah jadi/jadi HARUS hasil transformasi langsung dari bahan input
  - Konteks Indonesia: penggunaan tradisional/lokal vs teori industri modern
  - Bentuk fisik dan kegunaan aktual: HS code berdasarkan bagaimana produk diperdagangkan
  - Kelayakan industri: jalur yang sudah ada industrinya atau berpotensi besar
- Contoh: input "batok kelapa" → AI tidak akan suggest minyak kelapa (dari daging buah), tapi arang tempurung dan karbon aktif (dari batok).

**HS Code Processing (`utils.py`)**
- `clean_hs_code()`: Membersihkan HS code dari AI (hapus titik, ambil 6 digit, padding zeros).
- `extract_hs_codes_from_ai()`: Ekstrak dan clean semua HS codes untuk stage tertentu.
- `get_best_hs_code()`: Ambil HS code terbaik (pertama) dari hasil AI.
- `get_hs_code_description()`: Lookup deskripsi HS code dari hasil AI.
- `select_hs_codes_with_conflict_resolution()`: Menyelesaikan konflik HS code antar stage.
- `validate_supply_chain_consistency_universal()`: **Validasi universal rantai pasok untuk semua industri**.

**Universal Supply Chain Validation System**
Sistem validasi canggih yang memastikan konsistensi logis rantai pasok dari bahan mentah ke produk jadi. Mendukung **6 kategori industri utama**:

- **🌾 Agriculture**: Tanaman, pertanian, kehutanan
- **⛏️ Mining**: Pertambangan mineral dan logam
- **🧪 Chemical**: Bahan kimia dan petrokimia
- **🏭 Manufacturing**: Manufaktur dan otomotif
- **🧵 Textile**: Tekstil dan pakaian
- **💻 Technology**: Elektronik dan semikonduktor

**Fitur Validasi:**
- **200+ Transformation Patterns**: Pola transformasi spesifik per industri
- **HS Chapter Transition Logic**: Validasi perpindahan chapter HS yang logis
- **Keyword-Based Validation**: Deteksi inkonsistensi berdasarkan deskripsi produk
- **Confidence Scoring**: Skor kepercayaan 0-100 dengan level (High/Medium/Low)
- **Industry-Specific Adjustments**: Penyesuaian khusus untuk karakteristik setiap industri
- **Conflict Resolution**: Penyelesaian otomatis konflik HS code antar stage

**Contoh Validasi:**
```python
# Input: Moringa (Agriculture)
hs_codes = ['121190', '121190', '121190']  # Raw, Semi, Finished
stages = ['raw', 'semi', 'finished']

result = validate_supply_chain_consistency_universal(hs_codes, stages)
# Output: confidence_score=100, industry='agriculture', issues=[]
```

**Data Miner (`data_miner.py`)**
- Menangani request ke UN Comtrade API.
- 4-Request : 3 ekspor Indonesia (raw/semi/finished) + 1 impor dunia.
- Rate limiting, error handling, dan auto-retry.

**Decision Engine**
- Scoring berdasarkan value added, CAGR, dan market gap.
- Output: LAYAK atau TIDAK LAYAK hilirisasi.

#### Layer 3: Data (Storage & Sources)

**MySQL Database (`database.py`)**
- 3 tabel: `commodity_searches`, `api_cache`, `analysis_results`.
- Cache dengan TTL 30 hari.
- Schema dibuat otomatis saat first run.

**External APIs**
- UN Comtrade API: Rate limit 10 req/min.
- Google Gemini API: Rate limit 60 req/min.


## Instalasi

### Prasyarat
- Python 3.10 atau lebih tinggi
- MySQL Server (untuk caching)
- Google Gemini API Key
- UN Comtrade Subscription Key

### 1. Clone Repository
```bash
git clone <repository-url>
cd UNcomtrade
```

### 2. Buat Virtual Environment
```bash
python -m venv venv
```

### 3. Aktivasi Virtual Environment
**Windows:**
```bash
venv\Scripts\activate
```

**Linux/Mac:**
```bash
source venv/bin/activate
```

### 4. Install Dependencies
```bash
pip install -r requirements.txt
```

### 5. Setup Environment Variables
Buat file `.env` di root folder (gunakan `.env.example` sebagai template):
```env
# API Keys
GEMINI_API_KEY=your_gemini_api_key_here
COMTRADE_SUBSCRIPTION_KEY=your_comtrade_key_here

# Database Configuration
DB_HOST=localhost
DB_USER=root
DB_PASS=your_mysql_password
DB_NAME=comtrade_db
```

### 6. Setup Database
Database dan tabel akan otomatis dibuat saat aplikasi pertama kali dijalankan.  
Pastikan MySQL Server sudah berjalan dengan kredensial yang sesuai di `.env`.

---

## Menjalankan Aplikasi

### Cara 1: Menggunakan Script Launcher

**Windows:**
```bash
run.bat
```

**Linux/Mac:**
```bash
chmod +x run.sh
./run.sh
```

Script launcher akan otomatis:
- Mengecek/membuat virtual environment
- Menginstall dependencies jika belum
- Menjalankan aplikasi Streamlit

### Cara 2: Manual
```bash
cd src
streamlit run app.py
```

Aplikasi akan terbuka di browser pada `http://localhost:8501`

---

## Struktur Folder

```
UNcomtrade/
├── src/
│   ├── __init__.py
│   ├── app.py                   # Streamlit app utama
│   ├── database.py              # MySQL database manager
│   ├── ai_service.py            # Google Gemini integration (keyword + HS code extraction)
│   ├── data_miner.py            # UN Comtrade API client
│   └── utils.py                 # HS code cleaning + helper functions
│
├── tests/
│   ├── __init__.py
│   ├── test_integration.py      # Integration tests
│   ├── test_utils.py            # Unit tests (HS code cleaning, extraction)
│   └── test_regression.py       # Regression tests
│
├── .env                         # Environment variables (private)
├── requirements.txt             # Python dependencies
├── run.bat                      # Windows launcher
├── run.sh                       # Unix/Linux launcher
└── README.md
```

---

## Testing

Jalankan unit tests:
```bash
pytest tests/
```

Jalankan dengan coverage report:
```bash
pytest tests/ --cov=src --cov-report=html
```

### Universal Validation Testing
Test khusus untuk sistem validasi rantai pasok universal:
```bash
pytest tests/test_universal_validation.py -v
```

**Coverage Testing:**
- ✅ Agriculture: Moringa, kopi, kakao, kelapa
- ✅ Mining: Tembaga, emas, nikel, batubara  
- ✅ Chemical: Petrokimia, pupuk, plastik
- ✅ Manufacturing: Otomotif, elektronik, mesin
- ✅ Textile: Katun, wol, sintetis
- ✅ Technology: Semikonduktor, baterai, komponen elektronik

**Test Results:** 22/22 unit tests passed, 9/9 universal validation tests passed.

---

## Cara Mendapatkan API Keys

### Google Gemini API Key
1. Kunjungi [Google AI Studio](https://aistudio.google.com/app/apikey)
2. Login dengan akun Google
3. Klik "Create API Key"
4. Copy API key ke file `.env`

### UN Comtrade Subscription Key
1. Daftar di [UN Comtrade Developer Portal](https://comtradeplus.un.org/)
2. Login dan buka menu "API Management"
3. Subscribe ke plan yang sesuai (Free tier available)
4. Copy subscription key ke file `.env`

---

## Database Schema

Database `comtrade_db` memiliki 3 tabel utama yang dibuat otomatis oleh aplikasi:

**Catatan:** Sistem menggunakan AI-based HS Code classification. Tidak ada tabel HS Code lokal.

### 1. `commodity_searches`
Menyimpan history pencarian komoditas
```sql
- id (INT, PK)
- user_input (VARCHAR)
- commodity_name (VARCHAR)
- raw_hs_code (VARCHAR)
- finished_hs_code (VARCHAR)
- ai_extraction (JSON)
- created_at (TIMESTAMP)
```

### 2. `api_cache`
Cache response dari UN Comtrade API
```sql
- id (INT, PK)
- cache_key (VARCHAR, UNIQUE)
- request_type (VARCHAR)
- hs_code (VARCHAR)
- response_data (JSON)
- created_at (TIMESTAMP)
- expires_at (TIMESTAMP)
```

### 3. `analysis_results`
Menyimpan hasil analisis hilirisasi
```sql
- id (INT, PK)
- commodity_name (VARCHAR)
- raw_hs_code (VARCHAR)
- finished_hs_code (VARCHAR)
- raw_export_value (DECIMAL)
- finished_export_value (DECIMAL)
- global_demand_value (DECIMAL)
- market_gap (DECIMAL)
- cagr_raw (DECIMAL)
- cagr_finished (DECIMAL)
- recommendation (VARCHAR)
- analysis_summary (TEXT)
- created_at (TIMESTAMP)
```

---

## Cara Kerja Sistem

### Alur Lengkap:

1. **Input:** User memasukkan nama komoditas (contoh: "Kelapa").

2. **Cache Check:** Cek apakah data sudah ada di MySQL cache.

3. **AI Processing:** Gemini AI mengekstrak keyword DAN HS Code per stage:
   - Raw: "Fresh banana leaves" → HS: 1404.90, 0604.90
   - Semi: "Cleaned and cut banana leaves" → HS: 1404.90
   - Finished: "Pressed banana leaf plates" → HS: 4602.19, 4823.70
   - AI memastikan jalur koheren (daun → dipotong → piring, BUKAN daun → pulp kertas)

4. **Clean HS Codes:** Sistem membersihkan HS codes dari AI:
   - Format: "1404.90" → "140490" (6 digit, no dot)
   - Pilih HS code terbaik (pertama) dari array alternatif
   - Validasi format untuk UN Comtrade API

5. **Data Mining (4-Request Protocol):**
   - Request 1: Ekspor Indonesia - Bahan Mentah
   - Request 2: Ekspor Indonesia - Setengah Jadi
   - Request 3: Ekspor Indonesia - Produk Jadi
   - Request 4: Impor Dunia - Produk Jadi (Global Demand)

6. **Data Processing:**
   - Cleaning dan normalization
   - Aggregasi per tahun
   - Perhitungan unit value ($/kg)

7. **Analisis:**
   - CAGR 5 tahun
   - Value Added ($/kg selisih)
   - Market Gap (demand - supply)

8. **Rekomendasi:**
   - **LAYAK HILIRISASI** jika value added positif, market gap signifikan, tren produk jadi tumbuh.
   - **TIDAK LAYAK** jika margin kecil, demand rendah, atau tren negatif.

---

## Contoh Hasil AI Classification

Beberapa contoh komoditas yang dianalisis dengan AI-direct HS code extraction:

| Komoditas | Stage | HS Code | Deskripsi |
|-----------|-------|---------|-----------|
| Kelapa | Raw | 080112 | Coconuts, in the inner shell (endocarp) |
| Kelapa | Semi | 151311 | Coconut (copra) oil, crude |
| Kelapa | Finished | 340111 | Soap, for toilet use |
| Daun Pisang | Raw | 140490 | Vegetable products not elsewhere specified |
| Daun Pisang | Semi | 140490 | Cleaned and cut banana leaves |
| Daun Pisang | Finished | 460219 | Basketwork/articles from vegetable plaiting materials |
| Batok Kelapa | Raw | 080119 | Coconut shells |
| Batok Kelapa | Semi | 440290 | Coconut shell charcoal |
| Batok Kelapa | Finished | 380210 | Activated carbon |
| Nira Kelapa | Raw | 130219 | Coconut sap (vegetable saps and extracts) |
| Nira Kelapa | Semi | 170290 | Other sugars including chemically pure |
| Nira Kelapa | Finished | 170114 | Other cane sugar |

**Catatan Koherensi:**
- Batok kelapa ≠ Minyak kelapa (AI memahami batok vs daging buah berbeda)
- Daun pisang → Piring/wadah (BUKAN pulp kertas, karena daun pisang tidak digunakan untuk industri pulp)
- Nira kelapa → Gula (jalur tradisional Indonesia, bukan teori industri modern)



## Troubleshooting

### Database Connection Error
```
Solusi:
1. Pastikan MySQL Server berjalan
2. Cek kredensial di file .env
3. Buat database manual jika perlu:
   mysql -u root -p
   CREATE DATABASE comtrade_db;
```

### API Key Error
```
Solusi:
1. Pastikan API keys valid dan aktif
2. Cek quota API (Gemini & Comtrade)
3. Verifikasi format .env sudah benar
```

### Module Not Found
```
Solusi:
1. Pastikan virtual environment aktif
2. Install ulang dependencies:
   pip install -r requirements.txt
```

---

## Dokumentasi Teknis

### Module

#### `app.py`
Aplikasi Streamlit dan logic analisis hilirisasi:
- `perform_analysis()`: Koordinasi alur analisis dari input → AI → UN Comtrade → rekomendasi.
- `render_results()`: Menampilkan hasil analisis dengan visualisasi interaktif.
- `render_visualizations()`: Grafik tren ekspor/impor menggunakan Plotly.

#### `utils.py`
Helper functions untuk HS code processing dan kalkulasi ekonomi:
- `clean_hs_code()`: Membersihkan HS code dari format AI (hapus titik, 6-digit, padding).
- `extract_hs_codes_from_ai()`: Ekstrak semua HS codes untuk stage tertentu dari hasil AI.
- `get_best_hs_code()`: Ambil HS code terbaik (pertama) dari array AI.
- `get_hs_code_description()`: Lookup deskripsi HS code dari hasil AI.
- `calculate_cagr()`: Menghitung growth rate.
- `calculate_value_added()`: Menghitung selisih nilai ekonomi.
- `format_currency()`: Format angka mata uang.
- `validate_hscode()`: Validasi format HS Code.

#### `ai_service.py`
Integrasi Google Gemini:
- Ekstraksi keyword DAN HS Code dari input natural language.
- Output JSON terstruktur: `commodity_name`, `raw_material`, `semi_finished`, `finished_product`, `keywords`, `raw_hs_codes`, `semi_hs_codes`, `finished_hs_codes`.
- Prompt engineering untuk koherensi jalur dan konteks Indonesia.

#### `data_miner.py`
Client UN Comtrade API:
- Rate limiting (10 req/min).
- Error handling dan auto-retry.
- 4-request protocol per komoditas.

#### `database.py`
MySQL database manager:
- Connection pooling.
- Auto-schema creation.
- Cache management (TTL 30 hari).

### AI-Based HS Code Classification

Sistem menggunakan Google Gemini AI untuk klasifikasi HS Code dengan prompt engineering yang sophisticated:

**Prinsip Koherensi Jalur:**
- Produk setengah jadi dan jadi HARUS hasil transformasi langsung dari bahan input
- Contoh BENAR: Batok kelapa → Arang tempurung → Karbon aktif
- Contoh SALAH: Batok kelapa → Minyak kelapa (minyak dari daging buah, bukan batok)

**Konteks Indonesia & Penggunaan Aktual:**
- Prioritaskan jalur yang sudah ada industrinya atau umum digunakan tradisional
- Contoh: Daun pisang → piring/wadah disposable (BUKAN daun pisang → pulp kertas)
- Pertimbangkan bentuk fisik dan kegunaan aktual di pasar, bukan hanya komposisi kimia

**HS Code Format:**
- AI memberikan format lengkap dengan titik (0801.12, 1513.11.00)
- Sistem membersihkan menjadi 6-digit tanpa titik untuk UN Comtrade API
- Multiple alternatives per stage untuk fleksibilitas

**Keuntungan vs TF-IDF:**
- Lebih akurat untuk komoditas niche dan produk tradisional Indonesia
- Memahami konteks transformasi (daun ≠ buah, batok ≠ daging)
- Tidak perlu database HS Code lokal (langsung dari knowledge AI)
- Adaptif terhadap komoditas baru tanpa update dataset

---

