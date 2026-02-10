"""
Modul Data Mining untuk UN Comtrade API
Implementasi Strategi 4-Request untuk analisis supply/demand
"""

import os
import requests
import pandas as pd
from typing import Dict, List, Optional
import logging
from datetime import datetime, timedelta
import time
import threading
from database import DatabaseManager

# Konfigurasi logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Konstanta rate limiting API
API_RATE_LIMIT_DELAY = 0.5  # Jeda antar request tahun
API_RATE_LIMIT_SHORT = 0.3  # Jeda antar request importir
API_WAIT_BETWEEN_STAGES = 1  # Jeda antar tahap protocol

# Lock threading untuk singleton
_comtrade_lock = threading.Lock()


class ComtradeAPI:
    """
    UN Comtrade API client dengan caching dan protokol 4-request
    """

    BASE_URL = "https://comtradeapi.un.org/public/v1/preview/C/A/HS"

    def __init__(self, subscription_key: Optional[str] = None, db: Optional[DatabaseManager] = None):
        """
        Inisialisasi Comtrade API client

        Args:
            subscription_key: UN Comtrade subscription key (jika None, muat dari env)
            db: DatabaseManager instance untuk caching (jika None, buat instance baru)
        """
        self.subscription_key = subscription_key or os.getenv("COMTRADE_SUBSCRIPTION_KEY")

        if not self.subscription_key:
            raise ValueError("COMTRADE_SUBSCRIPTION_KEY not found in environment")

        self.headers = {
            "Ocp-Apim-Subscription-Key": self.subscription_key
        }
        
        # Setup database untuk caching
        self.db = db if db else DatabaseManager()

        logger.info("Comtrade API client initialized with caching")

    def _make_request(
        self,
        reporter: str,
        partner: str,
        flow_code: str,
        hs_code: str,
        period: str,
        max_retries: int = 3
    ) -> Optional[Dict]:
        """
        Buat request API ke Comtrade dengan retry logic

        Args:
            reporter: Kode negara reporter (misal: "360" untuk Indonesia, "all" untuk dunia)
            partner: Kode negara partner (misal: "0" untuk dunia)
            flow_code: Alur perdagangan (M=Import, X=Export)
            hs_code: Kode komoditas HS
            period: Periode waktu (misal: "2023" atau "2019,2020,2021,2022,2023")
            max_retries: Maksimum percobaan retry

        Returns:
            Respons JSON atau None jika gagal
        """
        # Buat cache key
        cache_key = f"{reporter}_{partner}_{flow_code}_{hs_code}_{period}"
        
        # Cek cache dulu
        cached_response = self.db.get_cached_api_response(cache_key)
        if cached_response:
            logger.info(f"Cache HIT: {cache_key}")
            return cached_response
        
        logger.info(f"Cache MISS: {cache_key} - calling API")
        
        # Tangani "all" untuk data agregat dunia
        # Untuk impor dunia, perlu agregasi data dengan cara berbeda
        if reporter == "all":
            # Untuk global demand, perlu menjumlahkan importir-importir utama
            # Ini ditangani di get_import_data dengan membuat banyak request
            reporter_val = reporter
        else:
            reporter_val = int(reporter)

        params = {
            "reporterCode": reporter_val,
            "partnerCode": int(partner),
            "partner2Code": 0,
            "flowCode": flow_code,
            "cmdCode": hs_code,
            "period": period,
            "customsCode": "C00"
        }

        for attempt in range(max_retries):
            try:
                logger.info(f"API Request: {reporter}/{partner}/{flow_code}/{hs_code}/{period}")

                response = requests.get(
                    self.BASE_URL,
                    params=params,
                    headers=self.headers,
                    timeout=30
                )

                if response.status_code == 200:
                    data = response.json()
                    logger.info(f"Success! Count: {data.get('count', 0)} records")
                    if 'data' in data and len(data['data']) > 0:
                        logger.info(f"First record primaryValue: ${data['data'][0].get('primaryValue', 0):,.2f}")
                    
                    # Simpan ke cache dengan TTL 30 hari
                    request_type = "export" if flow_code == "X" else "import"
                    self.db.cache_api_response(
                        cache_key=cache_key,
                        request_type=request_type,
                        hs_code=hs_code,
                        response_data=data,
                        ttl_days=30
                    )
                    
                    return data
                elif response.status_code == 429:
                    # Rate limit tercapai, tunggu lalu retry
                    wait_time = 2 ** attempt  # Backoff eksponensial
                    logger.warning(f"Rate limit hit, waiting {wait_time}s...")
                    time.sleep(wait_time)
                else:
                    logger.error(f"API error {response.status_code}: {response.text}")
                    return None

            except requests.exceptions.RequestException as e:
                logger.error(f"Request failed (attempt {attempt + 1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
                else:
                    return None

        return None

    def get_export_data(
        self,
        reporter_code: str,
        hs_code: str,
        years: List[int]
    ) -> pd.DataFrame:
        """
        Ambil data ekspor untuk negara dan komoditas tertentu

        Args:
            reporter_code: Kode negara (misal: "360" untuk Indonesia)
            hs_code: Kode komoditas HS
            years: List tahun yang akan di-query

        Returns:
            DataFrame dengan data ekspor
        """
        logger.info(f"Fetching EXPORT data: Reporter={reporter_code}, HS={hs_code}, Years={years}")

        all_data = []

        # API hanya menerima 1 periode, jadi loop tiap tahun
        for year in years:
            data = self._make_request(
                reporter=reporter_code,
                partner="0",  # Dunia
                flow_code="X",  # Ekspor
                hs_code=hs_code,
                period=str(year)  # Hanya satu tahun
            )

            if data and 'data' in data and len(data['data']) > 0:
                all_data.extend(data['data'])

            time.sleep(API_RATE_LIMIT_DELAY)  # Rate limiting antar tahun

        if all_data:
            df = pd.DataFrame(all_data)
            logger.info(f"Got {len(df)} records total, Total value: ${df['primaryValue'].sum():,.2f}")
            return df
        else:
            logger.warning(f"No data returned for HS {hs_code}")
            return pd.DataFrame()

    def get_import_data(
        self,
        reporter_code: str,
        hs_code: str,
        years: List[int]
    ) -> pd.DataFrame:
        """
        Ambil data impor untuk negara dan komoditas tertentu

        Args:
            reporter_code: Kode negara (misal: "all" untuk impor global)
            hs_code: Kode komoditas HS
            years: List tahun yang akan di-query

        Returns:
            DataFrame dengan data impor
        """
        logger.info(f"Fetching IMPORT data: Reporter={reporter_code}, HS={hs_code}, Years={years}")

        all_data = []

        # Tangani "all" untuk global demand dengan query importir-importir utama
        if reporter_code == "all":
            # Negara/region importir utama (ekonomi global terbesar)
            major_importers = [
                "842",  # USA
                "156",  # China
                "276",  # Germany
                "392",  # Japan
                "826",  # United Kingdom
                "251",  # France
                "381",  # Italy
                "528",  # Netherlands
                "124",  # Canada
                "410",  # South Korea
                "356",  # India
                "724",  # Spain
                "036",  # Australia
                "702",  # Singapore
                "458",  # Malaysia
            ]

            for country in major_importers:
                for year in years:
                    data = self._make_request(
                        reporter=country,
                        partner="0",  # Dunia
                        flow_code="M",  # Impor
                        hs_code=hs_code,
                        period=str(year)
                    )

                    if data and 'data' in data and len(data['data']) > 0:
                        all_data.extend(data['data'])

                    time.sleep(API_RATE_LIMIT_SHORT)  # Rate limiting
        else:
            # Data impor negara tunggal
            for year in years:
                data = self._make_request(
                    reporter=reporter_code,
                    partner="0",  # Dunia
                    flow_code="M",  # Impor
                    hs_code=hs_code,
                    period=str(year)  # Hanya satu tahun
                )

                if data and 'data' in data and len(data['data']) > 0:
                    all_data.extend(data['data'])

                time.sleep(API_RATE_LIMIT_DELAY)  # Rate limiting antar tahun

        if all_data:
            df = pd.DataFrame(all_data)
            logger.info(f"   Got {len(df)} records total, Total value: ${df['primaryValue'].sum():,.2f}")
            return df
        else:
            logger.warning(f"   No data returned for HS {hs_code}")
            return pd.DataFrame()

    def four_request_protocol(
        self,
        raw_hs_code: str,
        semi_finished_hs_code: str,
        finished_hs_code: str,
        years: Optional[List[int]] = None
    ) -> Dict:
        """
        Eksekusi Strategi Mining 4-Request untuk analisis hilirisasi

        Request 1: Ekspor Indonesia - Bahan Mentah
        Request 2: Ekspor Indonesia - Produk Setengah Jadi
        Request 3: Ekspor Indonesia - Produk Jadi
        Request 4: Impor Dunia - Produk Jadi (Global Demand)

        Args:
            raw_hs_code: Kode HS untuk bahan mentah
            semi_finished_hs_code: Kode HS untuk produk setengah jadi
            finished_hs_code: Kode HS untuk produk jadi
            years: List tahun untuk dianalisis (default: 5 tahun terakhir)

        Returns:
            Dictionary berisi semua 4 dataset dan analisis
        """
        if years is None:
            current_year = datetime.now().year
            # Gunakan hanya tahun-tahun lalu dengan data lengkap (exclude tahun ini dan tahun lalu)
            years = list(range(current_year - 6, current_year - 1))

        logger.info(f"Starting 4-Request Protocol: {raw_hs_code} -> {semi_finished_hs_code} -> {finished_hs_code}")

        result = {
            "raw_hs_code": raw_hs_code,
            "semi_finished_hs_code": semi_finished_hs_code,
            "finished_hs_code": finished_hs_code,
            "years": years,
            "data": {}
        }

        # Request 1: Ekspor Indonesia - Bahan Mentah (Cek Supply)
        logger.info("Request 1: Indonesia Raw Material Export")
        result["data"]["indonesia_raw_export"] = self.get_export_data(
            reporter_code="360",  # Indonesia
            hs_code=raw_hs_code,
            years=years
        )
        time.sleep(API_WAIT_BETWEEN_STAGES)  # Rate limiting

        # Request 2: Ekspor Indonesia - Setengah Jadi
        logger.info("Request 2: Indonesia Semi-Finished Product Export")
        result["data"]["indonesia_semi_export"] = self.get_export_data(
            reporter_code="360",
            hs_code=semi_finished_hs_code,
            years=years
        )
        time.sleep(API_WAIT_BETWEEN_STAGES)

        # Request 3: Ekspor Indonesia - Produk Jadi (Kemampuan Saat Ini)
        logger.info("Request 3: Indonesia Finished Product Export")
        result["data"]["indonesia_finished_export"] = self.get_export_data(
            reporter_code="360",
            hs_code=finished_hs_code,
            years=years
        )
        time.sleep(API_WAIT_BETWEEN_STAGES)

        # Request 4: Impor Dunia - Produk Jadi (Global Demand)
        logger.info("Request 4: World Finished Product Import (Demand)")
        result["data"]["world_finished_import"] = self.get_import_data(
            reporter_code="all",  # Semua negara (global demand)
            hs_code=finished_hs_code,
            years=years
        )
        time.sleep(API_WAIT_BETWEEN_STAGES)

        # Hitung agregat dan tren
        result["analysis"] = self._analyze_protocol_results(result["data"], years)

        logger.info("4-Request Protocol completed successfully")
        return result

    def _analyze_protocol_results(self, data: Dict, years: List[int]) -> Dict:
        """
        Analisis hasil dari protokol 4-request

        Args:
            data: Dictionary berisi semua 4 dataset
            years: Tahun yang dianalisis

        Returns:
            Ringkasan analisis
        """
        # YEAR ALIGNMENT: Temukan tahun umum dimana data Indonesia dan Global ada
        # PENTING: Alignment ini HANYA digunakan untuk PERHITUNGAN METRIK (total, CAGR, gap)
        # Data untuk tahun non-aligned TETAP DITAMPILKAN di visualisasi, tapi tidak dibandingkan
        indonesia_finished_years = set()
        global_demand_years = set()

        if not data["indonesia_finished_export"].empty and 'period' in data["indonesia_finished_export"].columns:
            indonesia_finished_years = set(data["indonesia_finished_export"]['period'].unique())

        if not data["world_finished_import"].empty and 'period' in data["world_finished_import"].columns:
            global_demand_years = set(data["world_finished_import"]['period'].unique())

        # Gunakan tahun dimana KEDUA dataset punya data untuk perhitungan metrik
        common_years = indonesia_finished_years.intersection(global_demand_years)

        if common_years:
            aligned_years = sorted(list(common_years))
            logger.info(f"Year alignment: Indonesia years={sorted(indonesia_finished_years)}, Global years={sorted(global_demand_years)}")
            logger.info(f"Using aligned years for comparison: {aligned_years}")
        else:
            aligned_years = []
            logger.warning("No common years found between Indonesia export and Global demand data")

        analysis = {
            "raw_export_total": 0,
            "raw_export_trend": 0,
            "semi_export_total": 0,
            "semi_export_trend": 0,
            "finished_export_total": 0,
            "finished_export_trend": 0,
            "global_demand_total": 0,
            "global_demand_trend": 0,
            "market_gap": 0,
            "unit_value_comparison": {},
            "aligned_years": aligned_years,  # Simpan untuk ditampilkan
            "excluded_years": {
                "indonesia_only": sorted(list(indonesia_finished_years - global_demand_years)),
                "global_only": sorted(list(global_demand_years - indonesia_finished_years))
            }
        }

        # Analisis ekspor bahan mentah
        if not data["indonesia_raw_export"].empty:
            df_raw = data["indonesia_raw_export"]
            analysis["raw_export_total"] = df_raw['primaryValue'].sum() if 'primaryValue' in df_raw else 0

            # Hitung tren (CAGR)
            if len(df_raw) > 1:
                yearly = df_raw.groupby('period')['primaryValue'].sum().sort_index()
                if len(yearly) > 1:
                    start_val = yearly.iloc[0]
                    end_val = yearly.iloc[-1]
                    n_years = len(yearly) - 1
                    if start_val > 0:
                        analysis["raw_export_trend"] = ((end_val / start_val) ** (1 / n_years) - 1) * 100

        # Analisis ekspor setengah jadi
        if "indonesia_semi_export" in data and not data["indonesia_semi_export"].empty:
            df_semi = data["indonesia_semi_export"]
            analysis["semi_export_total"] = df_semi['primaryValue'].sum() if 'primaryValue' in df_semi else 0

            # Hitung tren (CAGR)
            if len(df_semi) > 1:
                yearly = df_semi.groupby('period')['primaryValue'].sum().sort_index()
                if len(yearly) > 1:
                    start_val = yearly.iloc[0]
                    end_val = yearly.iloc[-1]
                    n_years = len(yearly) - 1
                    if start_val > 0:
                        analysis["semi_export_trend"] = ((end_val / start_val) ** (1 / n_years) - 1) * 100

        # Analisis ekspor produk jadi (HANYA tahun yang realigned untuk perbandingan)
        if not data["indonesia_finished_export"].empty:
            df_finished = data["indonesia_finished_export"]

            # Gunakan aligned years untuk perhitungan finished export
            if aligned_years:
                df_finished_aligned = df_finished[df_finished['period'].isin(aligned_years)]
                analysis["finished_export_total"] = df_finished_aligned['primaryValue'].sum() if 'primaryValue' in df_finished_aligned else 0

                # Hitung tren (CAGR) hanya menggunakan aligned years
                if len(df_finished_aligned) > 1:
                    yearly = df_finished_aligned.groupby('period')['primaryValue'].sum().sort_index()
                    if len(yearly) > 1:
                        start_val = yearly.iloc[0]
                        end_val = yearly.iloc[-1]
                        n_years = len(yearly) - 1
                        if start_val > 0:
                            analysis["finished_export_trend"] = ((end_val / start_val) ** (1 / n_years) - 1) * 100
            else:
                # Fallback: gunakan semua data jika tidak ada alignment
                analysis["finished_export_total"] = df_finished['primaryValue'].sum() if 'primaryValue' in df_finished else 0

        # Analisis global demand (HANYA tahun yang realigned untuk perbandingan)
        if not data["world_finished_import"].empty:
            df_demand = data["world_finished_import"]

            # Gunakan aligned years untuk perhitungan global demand
            if aligned_years:
                df_demand_aligned = df_demand[df_demand['period'].isin(aligned_years)]
                analysis["global_demand_total"] = df_demand_aligned['primaryValue'].sum() if 'primaryValue' in df_demand_aligned else 0

                # Hitung demand trend (CAGR) hanya menggunakan aligned years
                if len(df_demand_aligned) > 1:
                    yearly = df_demand_aligned.groupby('period')['primaryValue'].sum().sort_index()
                    if len(yearly) > 1:
                        start_val = yearly.iloc[0]
                        end_val = yearly.iloc[-1]
                        n_years = len(yearly) - 1
                        if start_val > 0:
                            analysis["global_demand_trend"] = ((end_val / start_val) ** (1 / n_years) - 1) * 100
            else:
                # Fallback: gunakan semua data jika tidak ada alignment
                analysis["global_demand_total"] = df_demand['primaryValue'].sum() if 'primaryValue' in df_demand else 0

        # Hitung market gap (peluang) - sekarang hanya gunakan aligned years
        analysis["market_gap"] = analysis["global_demand_total"] - analysis["finished_export_total"]

        return analysis


# Instance singleton
_comtrade_api: Optional[ComtradeAPI] = None


def get_comtrade_api() -> ComtradeAPI:
    """
    Ambil atau buat Comtrade API singleton (thread-safe)

    Returns:
        Instance ComtradeAPI dengan database caching
    """
    global _comtrade_api

    if _comtrade_api is None:
        with _comtrade_lock:  # Inisialisasi thread-safe
            if _comtrade_api is None:  # Pola double-check
                db = DatabaseManager()
                _comtrade_api = ComtradeAPI(db=db)

    return _comtrade_api
