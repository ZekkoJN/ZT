"""
Fungsi Utility untuk Export Downstreaming DSS
Berisi HS Code cleaning dari AI extraction dan fungsi helper
"""

import os
import re
from typing import Dict, List, Tuple, Optional
import logging

# Konfigurasi logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def clean_hs_code(raw_code: str) -> Optional[str]:
    """
    Bersihkan HS code dari format Gemini AI menjadi format UN Comtrade (6 digit, tanpa titik).
    
    Gemini AI biasanya memberikan HS code dengan titik (misal: "0801.12", "1513.11.00")
    UN Comtrade API membutuhkan kode 6-digit tanpa titik (misal: "080112", "151311")
    
    Rules:
    1. Hapus semua titik
    2. Ambil 6 digit pertama saja
    3. Jika kurang dari 6 digit, pad dengan "0" di kanan
    4. Validasi: harus numerik
    
    Args:
        raw_code: HS code mentah dari AI (misal: "0801.12", "1704.10.00", "080112")
        
    Returns:
        HS code bersih 6-digit (misal: "080112") atau None jika tidak valid
    """
    if not raw_code:
        return None
    
    # Konversi ke string dan hapus whitespace
    code_str = str(raw_code).strip()
    
    # Hapus semua titik
    code_str = code_str.replace(".", "")
    
    # Hapus karakter non-numerik
    code_str = re.sub(r'[^0-9]', '', code_str)
    
    if not code_str:
        return None
    
    # Ambil 6 digit pertama
    if len(code_str) > 6:
        code_str = code_str[:6]
    
    # Pad dengan 0 di kanan jika kurang dari 6 digit
    if len(code_str) < 6:
        code_str = code_str.ljust(6, '0')
    
    # Validasi: harus numerik dan 6 digit
    if not code_str.isdigit() or len(code_str) != 6:
        return None
    
    return code_str


def extract_hs_codes_from_ai(ai_result: Dict, stage: str) -> List[str]:
    """
    Ekstrak dan bersihkan HS codes dari hasil AI untuk stage tertentu.
    
    Args:
        ai_result: Dictionary hasil dari Gemini AI
        stage: 'raw', 'semi', atau 'finished'
        
    Returns:
        List HS codes bersih 6-digit, sudah deduplicated
    """
    stage_key_map = {
        'raw': 'raw_hs_codes',
        'semi': 'semi_hs_codes',
        'finished': 'finished_hs_codes'
    }
    
    key = stage_key_map.get(stage)
    if not key:
        logger.warning(f"Stage tidak dikenal: {stage}")
        return []
    
    hs_codes_raw = ai_result.get(key, [])
    
    if not hs_codes_raw:
        logger.warning(f"Tidak ada HS codes dari AI untuk stage: {stage}")
        return []
    
    cleaned_codes = []
    seen = set()
    
    for item in hs_codes_raw:
        # item bisa berupa dict {"code": "0801.12", "description": "..."} atau string
        if isinstance(item, dict):
            raw_code = item.get('code', '')
        else:
            raw_code = str(item)
        
        cleaned = clean_hs_code(raw_code)
        if cleaned and cleaned not in seen:
            seen.add(cleaned)
            cleaned_codes.append(cleaned)
            logger.info(f"  [{stage}] HS Code: {raw_code} → {cleaned}")
    
    return cleaned_codes


def get_best_hs_code(ai_result: Dict, stage: str) -> Optional[str]:
    """
    Ambil HS code terbaik (pertama) dari hasil AI untuk stage tertentu.
    
    Args:
        ai_result: Dictionary hasil dari Gemini AI
        stage: 'raw', 'semi', atau 'finished'
        
    Returns:
        HS code 6-digit terbaik atau None
    """
    codes = extract_hs_codes_from_ai(ai_result, stage)
    return codes[0] if codes else None


def get_hs_code_description(ai_result: Dict, stage: str, hs_code: str) -> str:
    """
    Ambil deskripsi HS code dari hasil AI.
    
    Args:
        ai_result: Dictionary hasil dari Gemini AI
        stage: 'raw', 'semi', atau 'finished'
        hs_code: HS code yang dicari deskripsinya
        
    Returns:
        Deskripsi HS code atau 'N/A'
    """
    stage_key_map = {
        'raw': 'raw_hs_codes',
        'semi': 'semi_hs_codes',
        'finished': 'finished_hs_codes'
    }
    
    key = stage_key_map.get(stage)
    if not key:
        return 'N/A'
    
    for item in ai_result.get(key, []):
        if isinstance(item, dict):
            raw_code = item.get('code', '')
            cleaned = clean_hs_code(raw_code)
            if cleaned == hs_code:
                return item.get('description', 'N/A')
    
    return 'N/A'


def calculate_cagr(start_value: float, end_value: float, years: int) -> float:
    """
    Hitung Compound Annual Growth Rate (CAGR)

    Args:
        start_value: Nilai awal
        end_value: Nilai akhir
        years: Jumlah tahun

    Returns:
        CAGR dalam persentase
    """
    if start_value <= 0 or end_value <= 0 or years <= 0:
        return 0.0

    cagr = ((end_value / start_value) ** (1 / years) - 1) * 100
    return round(cagr, 2)


def calculate_value_added(raw_price: float, finished_price: float) -> float:
    """
    Hitung persentase Economic Value Added

    Args:
        raw_price: Harga per unit bahan mentah
        finished_price: Harga per unit produk jadi

    Returns:
        Persentase value added
    """
    if raw_price <= 0:
        return 0.0

    value_added = ((finished_price - raw_price) / raw_price) * 100
    return round(value_added, 2)


def format_currency(amount: float, currency: str = "USD") -> str:
    """
    Format mata uang untuk ditampilkan

    Args:
        amount: Jumlah yang akan diformat
        currency: Kode mata uang

    Returns:
        String mata uang terformat
    """
    if currency == "USD":
        return f"${amount:,.2f}"
    else:
        return f"{currency} {amount:,.2f}"


def format_currency_compact(amount: float) -> str:
    """
    Format mata uang dalam bentuk kompak (Jutaan/Miliaran)

    Args:
        amount: Jumlah yang akan diformat

    Returns:
        String mata uang terformat dengan notasi M/B
    """
    if amount >= 1_000_000_000:
        return f"${amount / 1_000_000_000:.2f}B"
    elif amount >= 1_000_000:
        return f"${amount / 1_000_000:.2f}M"
    elif amount >= 1_000:
        return f"${amount / 1_000:.2f}K"
    else:
        return f"${amount:.2f}"


def validate_hscode(hscode: str) -> bool:
    """
    Validasi format HS code

    Args:
        hscode: HS code untuk divalidasi

    Returns:
        True jika format valid
    """
    if not hscode:
        return False

    # HS codes harus 2, 4, atau 6 digit
    if len(hscode) not in [2, 4, 6]:
        return False

    # Harus numerik
    return hscode.isdigit()
