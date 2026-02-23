import pandas as pd
import time
import streamlit as st
import os
import json
import hashlib
from pathlib import Path
import comtradeapicall
from ai_service import GeminiService  # Import AI service untuk ekstraksi HS code

# --- KONFIGURASI CACHE
CACHE_DIR = Path(__file__).parent / "cache"
CACHE_DIR.mkdir(exist_ok=True)

def get_cache_key(hs_code, year, mode):
    """Generate unique cache key"""
    key_string = f"{hs_code}_{year}_{mode}"
    return hashlib.md5(key_string.encode()).hexdigest()

def load_from_cache(cache_key):
    """Load data from cache if exists and valid"""
    cache_file = CACHE_DIR / f"{cache_key}.json"
    if cache_file.exists():
        try:
            with open(cache_file, 'r') as f:
                cached_data = json.load(f)
                # Check if cache is less than 30 days old
                import time
                cache_age = time.time() - cached_data.get('timestamp', 0)
                if cache_age < 30 * 24 * 60 * 60:  # 30 days
                    return pd.DataFrame(cached_data['data'])
        except Exception as e:
            print(f"Cache load error: {e}")
    return None

def save_to_cache(cache_key, df):
    """Save data to cache"""
    if df.empty:
        return
    
    cache_file = CACHE_DIR / f"{cache_key}.json"
    try:
        cache_data = {
            'timestamp': time.time(),
            'data': df.to_dict('records')
        }
        with open(cache_file, 'w') as f:
            json.dump(cache_data, f)
    except Exception as e:
        print(f"Cache save error: {e}")

# --- KONFIGURASI API KEY DARI ENVIRONMENT VARIABLES
API_KEYS = [
    os.getenv('COMTRADE_SUBSCRIPTION_KEY', 'KEY_AKUN_1'),
    os.getenv('COMTRADE_SUBSCRIPTION_KEY_2', 'KEY_AKUN_2'),
    os.getenv('COMTRADE_SUBSCRIPTION_KEY_3', 'KEY_AKUN_3'),
    os.getenv('COMTRADE_SUBSCRIPTION_KEY_4', 'KEY_AKUN_4'),
    os.getenv('COMTRADE_SUBSCRIPTION_KEY_5', 'KEY_AKUN_5'),
]
current_key_index = 0

def get_next_key():
    """Rotasi API Key secara Round-Robin"""
    global current_key_index
    key = API_KEYS[current_key_index]
    current_key_index = (current_key_index + 1) % len(API_KEYS)
    return key

def extract_and_fetch_data(product_description: str, start_year=2020, end_year=2024, mode='supply'):
    """
    Integrasi lengkap: Ekstrak HS codes menggunakan AI Gemini, lalu ambil data Comtrade.
    
    Args:
        product_description: Deskripsi produk dalam bahasa natural
        start_year: Tahun mulai
        end_year: Tahun akhir
        mode: Mode pengambilan ('supply', 'competitor', 'demand')
    
    Returns:
        Dictionary dengan data untuk raw, semi, finished HS codes
    """
    print(f"🤖 Mengekstrak HS codes untuk: {product_description}")
    
    # Inisialisasi AI service
    gemini = GeminiService()
    
    # Ekstrak HS codes menggunakan AI Gemini
    ai_result = gemini.extract_commodity_keywords(product_description)
    
    # Ekstrak HS codes dari hasil AI
    raw_hs_codes = [hs['code'] for hs in ai_result.get('raw_hs_codes', [])]
    semi_hs_codes = [hs['code'] for hs in ai_result.get('semi_hs_codes', [])]
    finished_hs_codes = [hs['code'] for hs in ai_result.get('finished_hs_codes', [])]
    
    print(f"📋 HS Codes ditemukan:")
    print(f"   Bahan Dasar: {raw_hs_codes}")
    print(f"   Setengah Jadi: {semi_hs_codes}")
    print(f"   Produk Jadi: {finished_hs_codes}")
    
    # Ambil data untuk setiap kategori HS code
    results = {}
    
    if raw_hs_codes:
        print(f"🔄 Mengambil data bahan dasar...")
        results['raw'] = fetch_comtrade_data(raw_hs_codes, start_year, end_year, mode)
    
    if semi_hs_codes:
        print(f"🔄 Mengambil data setengah jadi...")
        results['semi'] = fetch_comtrade_data(semi_hs_codes, start_year, end_year, mode)
    
    if finished_hs_codes:
        print(f"🔄 Mengambil data produk jadi...")
        results['finished'] = fetch_comtrade_data(finished_hs_codes, start_year, end_year, mode)
    
    return results, ai_result

def fetch_comtrade_data(hs_codes, start_year=2020, end_year=2024, mode='supply'):
    """
    Mengambil data Comtrade menggunakan library comtradeapicall.
    Mendukung multiple HS codes (bahan dasar, setengah jadi, jadi)
    
    Args:
        hs_codes: String tunggal atau list HS codes
        start_year: Tahun mulai (default 2020)
        end_year: Tahun akhir (default 2024)
        mode: Mode pengambilan ('supply', 'competitor', 'demand')
    
    Returns:
        Jika hs_codes adalah string: DataFrame
        Jika hs_codes adalah list: Dictionary dengan key HS code dan value DataFrame
    """
    # Handle single HS code or list
    if isinstance(hs_codes, str):
        hs_codes = [hs_codes]
        return_single = True
    else:
        return_single = False
    
    results = {}
    
    for hs_code in hs_codes:
        print(f"🔄 Memproses HS Code: {hs_code}")
        all_data = []
        years = list(range(start_year, end_year + 1))
        
        subscription_key = get_next_key()  # Use rotating key

        for year in years:
            current_year = time.localtime().tm_year
            if year > current_year:
                continue

            # Generate periods for the entire year
            periods = ','.join([f'{year}{str(m).zfill(2)}' for m in range(1, 13)])
            
            cache_key = get_cache_key(hs_code, year, mode)
            cached_df = load_from_cache(cache_key)
            if cached_df is not None:
                print(f"   ✅ Cache hit for {hs_code} - {year}")
                all_data.extend(cached_df.to_dict('records'))
                continue

            # Configuration mapping for different modes
            mode_configs = {
                'supply': {
                    'reporterCode': '360',  # Indonesia
                    'flowCode': 'X',  # Export
                    'partnerCode': None  # All partners
                },
                'competitor': {
                    'reporterCode': None,  # All reporters
                    'flowCode': 'X',  # Export to Indonesia
                    'partnerCode': '360'  # Indonesia as partner
                },
                'demand': {
                    'reporterCode': None,  # All reporters
                    'flowCode': 'M',  # Import (global demand)
                    'partnerCode': None  # All partners
                }
            }
            
            # Get configuration for the mode, default to supply config
            config = mode_configs.get(mode, mode_configs['supply'])
            reporterCode = config['reporterCode']
            flowCode = config['flowCode']
            partnerCode = config['partnerCode']

            try:
                df = comtradeapicall.getFinalData(
                    subscription_key, typeCode='C', freqCode='M', clCode='HS', period=periods,
                    reporterCode=reporterCode, cmdCode=hs_code, flowCode=flowCode, partnerCode=partnerCode,
                    partner2Code=None,
                    customsCode=None, motCode=None, maxRecords=100000, format_output='JSON',
                    aggregateBy=None, breakdownMode='classic', countOnly=None, includeDesc=True
                )
                if df is not None and not df.empty:
                    print(f"   ✅ {hs_code} - {year}: Berhasil ambil {len(df)} baris data.")
                    save_to_cache(cache_key, df)
                    all_data.extend(df.to_dict('records'))
                else:
                    print(f"   ⚠️ {hs_code} - {year}: Data kosong/belum tersedia.")
                    save_to_cache(cache_key, pd.DataFrame())
            except Exception as e:
                print(f"   ❌ Exception fetching {hs_code} - {year}: {e}")
            time.sleep(1)  # Rate limiting

        if all_data:
            df = pd.DataFrame(all_data)
            numeric_cols = ['NetWeight', 'PrimaryValue', 'TradeValue', 'GrossWeight']
            for col in numeric_cols:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce')
            if 'period' in df.columns:
                df['date'] = pd.to_datetime(df['period'].astype(str), format='%Y%m', errors='coerce')
            results[hs_code] = df
        else:
            results[hs_code] = pd.DataFrame()
    
    # Return single DataFrame if input was single HS code, otherwise return dict
    if return_single:
        return results[hs_codes[0]]
    else:
        return results