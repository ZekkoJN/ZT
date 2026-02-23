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


def select_hs_codes_with_conflict_resolution(ai_result: Dict) -> Dict[str, Optional[str]]:
    """
    Pilih HS code terbaik untuk semua stage (raw, semi, finished) dengan resolusi konflik.
    
    Logic:
    1. Prioritas: raw → semi → finished (urutan pemilihan)
    2. Untuk setiap stage, ambil HS code pertama yang tersedia
    3. Jika HS code sudah digunakan stage sebelumnya, skip dan ambil alternatif berikutnya
    4. Jika tidak ada alternatif, gunakan HS code yang sama (sebagai fallback)
    
    Args:
        ai_result: Dictionary hasil dari Gemini AI
        
    Returns:
        Dictionary dengan keys: 'raw', 'semi', 'finished' dan values berupa HS code atau None
    """
    result = {'raw': None, 'semi': None, 'finished': None}
    used_codes = set()
    
    stages = ['raw', 'semi', 'finished']
    
    for stage in stages:
        codes = extract_hs_codes_from_ai(ai_result, stage)
        
        if not codes:
            logger.warning(f"Tidak ada HS codes untuk stage: {stage}")
            continue
            
        # Cari kode yang belum digunakan
        selected_code = None
        for code in codes:
            if code not in used_codes:
                selected_code = code
                used_codes.add(code)
                break
        
        # Jika semua kode sudah digunakan, gunakan yang pertama sebagai fallback
        # (meskipun duplikat, tapi setidaknya ada data)
        if selected_code is None:
            selected_code = codes[0]
            logger.warning(f"Semua HS codes untuk {stage} sudah digunakan stage sebelumnya, menggunakan fallback: {selected_code}")
        
        result[stage] = selected_code
        
    return result


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
