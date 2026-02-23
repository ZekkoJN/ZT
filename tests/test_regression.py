"""
Test HS code cleaning from AI extraction results.
Verifies that various AI output formats are correctly cleaned for UN Comtrade API.
"""
import sys
sys.path.insert(0, 'src')

from utils import clean_hs_code, extract_hs_codes_from_ai, get_best_hs_code, get_hs_code_description, select_hs_codes_with_conflict_resolution


print("=== TEST: HS Code Cleaning ===\n")

# Test various formats that Gemini might return
test_cases = [
    ("0801.12", "080112"),       # Standard dot format
    ("1513.11", "151311"),       # Standard dot format
    ("3401.11", "340111"),       # Standard dot format
    ("1704.10.00", "170410"),    # Long format with 2 dots
    ("0801.12.00", "080112"),    # Long format
    ("080112", "080112"),        # Already clean
    ("0801", "080100"),          # 4-digit (pad with zeros)
    ("08", "080000"),            # 2-digit chapter
    ("17.04", "170400"),         # Different dot position
    ("0901.11.00.00", "090111"), # Extra long format
]

all_pass = True
for raw_input, expected in test_cases:
    result = clean_hs_code(raw_input)
    status = "✅" if result == expected else "❌"
    if result != expected:
        all_pass = False
    print(f"  {status} clean_hs_code('{raw_input}') = '{result}' (expected: '{expected}')")

print(f"\n{'All tests passed!' if all_pass else 'Some tests FAILED!'}\n")


print("=== TEST: AI Result Extraction ===\n")

# Simulate AI result for "nira kelapa"
ai_result_nira = {
    "commodity_name": "coconut sap",
    "input_stage": "raw",
    "raw_material": "vegetable saps and extracts",
    "semi_finished": "sugar syrups",
    "finished_product": "sucrose",
    "keywords": ["coconut sugar", "natural sweetener", "food ingredients"],
    "raw_hs_codes": [
        {"code": "1302.19", "description": "Vegetable saps and extracts, n.e.c."},
        {"code": "0801.12", "description": "Coconuts, in the inner shell"}
    ],
    "semi_hs_codes": [
        {"code": "1702.90", "description": "Other sugars, including invert sugar"},
        {"code": "1702.30", "description": "Glucose and glucose syrup"}
    ],
    "finished_hs_codes": [
        {"code": "1701.14", "description": "Other cane sugar"},
        {"code": "1704.90", "description": "Sugar confectionery"}
    ],
    "industry_category": "agriculture",
    "selected_path_reason": "Coconut sugar has highest value-added as natural sweetener"
}

# Test extraction
raw_code = get_best_hs_code(ai_result_nira, 'raw')
semi_code = get_best_hs_code(ai_result_nira, 'semi')
finished_code = get_best_hs_code(ai_result_nira, 'finished')

print(f"  Raw HS Code:      {raw_code} (expected: 130219)")
print(f"  Semi HS Code:     {semi_code} (expected: 170290)")
print(f"  Finished HS Code: {finished_code} (expected: 170114)")

# Test descriptions
raw_desc = get_hs_code_description(ai_result_nira, 'raw', raw_code)
print(f"  Raw Description:  {raw_desc}")

# Test all alternatives
all_raw = extract_hs_codes_from_ai(ai_result_nira, 'raw')
print(f"  All Raw Codes:    {all_raw}")


print("\n=== TEST: Kelapa AI Result ===\n")

ai_result_kelapa = {
    "commodity_name": "coconut",
    "raw_hs_codes": [
        {"code": "0801.12", "description": "Coconuts, in the inner shell (endocarp)"},
        {"code": "0801.19", "description": "Coconuts, other"}
    ],
    "semi_hs_codes": [
        {"code": "1513.11", "description": "Coconut (copra) oil, crude"},
        {"code": "1513.19", "description": "Coconut (copra) oil, other than crude"}
    ],
    "finished_hs_codes": [
        {"code": "3401.11", "description": "Soap and organic surface-active products, for toilet use"},
        {"code": "3401.19", "description": "Soap, other"}
    ]
}

raw_code = get_best_hs_code(ai_result_kelapa, 'raw')
semi_code = get_best_hs_code(ai_result_kelapa, 'semi')
finished_code = get_best_hs_code(ai_result_kelapa, 'finished')

print(f"  Raw:      {raw_code} - {get_hs_code_description(ai_result_kelapa, 'raw', raw_code)}")
print(f"  Semi:     {semi_code} - {get_hs_code_description(ai_result_kelapa, 'semi', semi_code)}")
print(f"  Finished: {finished_code} - {get_hs_code_description(ai_result_kelapa, 'finished', finished_code)}")

print("\n=== TEST: Moringa (Kelor) Conflict Resolution ===\n")

# Test case for moringa where raw and semi have same HS code initially
ai_result_moringa = {
    "commodity_name": "Moringa (Kelor) Leaves",
    "raw_hs_codes": [
        {"code": "1211.90", "description": "Plants and parts of plants (including seeds and fruits), of a kind used primarily in perfumery, in pharmacy or for insecticidal, fungicidal or similar purposes, fresh or dried, whether or not cut, crushed or powdered: Other"},
        {"code": "1211.90.90", "description": "Other (specific for plants used in perfumery, pharmacy, etc.)"}
    ],
    "semi_hs_codes": [
        {"code": "1211.90", "description": "Plants and parts of plants (including seeds and fruits), of a kind used primarily in perfumery, in pharmacy or for insecticidal, fungicidal or similar purposes, fresh or dried, whether or not cut, crushed or powdered: Other"},
        {"code": "2106.90", "description": "Food preparations not elsewhere specified or included: Other"}
    ],
    "finished_hs_codes": [
        {"code": "3004.90", "description": "Medicaments (excluding goods of heading 3002, 3005 or 3006) consisting of mixed or unmixed products for therapeutic or prophylactic uses, put up in measured doses (including those in the form of transdermal administration systems) or in forms or packings for retail sale: Other"},
        {"code": "3004.90.90", "description": "Other (specific for medicaments)"},
        {"code": "2106.90", "description": "Food preparations not elsewhere specified or included: Other"}
    ]
}

print("Before conflict resolution (old method):")
old_raw = get_best_hs_code(ai_result_moringa, 'raw')
old_semi = get_best_hs_code(ai_result_moringa, 'semi')
old_finished = get_best_hs_code(ai_result_moringa, 'finished')
print(f"  Raw:      {old_raw} - {get_hs_code_description(ai_result_moringa, 'raw', old_raw)}")
print(f"  Semi:     {old_semi} - {get_hs_code_description(ai_result_moringa, 'semi', old_semi)}")
print(f"  Finished: {old_finished} - {get_hs_code_description(ai_result_moringa, 'finished', old_finished)}")
print(f"  ⚠️  Conflict: Raw and Semi have same HS code: {old_raw}")

print("\nAfter conflict resolution (new method):")
resolved_codes = select_hs_codes_with_conflict_resolution(ai_result_moringa)
print(f"  Raw:      {resolved_codes['raw']} - {get_hs_code_description(ai_result_moringa, 'raw', resolved_codes['raw'])}")
print(f"  Semi:     {resolved_codes['semi']} - {get_hs_code_description(ai_result_moringa, 'semi', resolved_codes['semi'])}")
print(f"  Finished: {resolved_codes['finished']} - {get_hs_code_description(ai_result_moringa, 'finished', resolved_codes['finished'])}")
print("  ✅ No conflicts: Each stage has different HS code"if resolved_codes['raw'] != resolved_codes['semi'] and resolved_codes['semi'] != resolved_codes['finished'] else "  ⚠️  Still has conflicts (fallback used)")

print("\n=== DONE ===")
