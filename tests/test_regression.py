"""
Test HS code cleaning from AI extraction results.
Verifies that various AI output formats are correctly cleaned for UN Comtrade API.
"""
import sys
sys.path.insert(0, 'src')

from utils import clean_hs_code, extract_hs_codes_from_ai, get_best_hs_code, get_hs_code_description


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

print("\n=== DONE ===")
