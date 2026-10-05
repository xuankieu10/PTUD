import os

def fix_api_py():
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    api_path = os.path.join(BASE_DIR, 'backend', 'api.py')
    
    with open(api_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Find the double insertions
    bad_part = '''        # Chuẩn hóa dữ liệu học tập thông qua module normalize.py
        normalized_data = normalize_transcript(result["all_subjects"])
        
        # Đồng bộ dữ liệu normalized (code, credits, semester) vào all_subjects và failed_subjects'''
        
    old_part = '''        # Chuẩn hóa dữ liệu học tập thông qua module normalize.py
        normalized_data = normalize_transcript(result["all_subjects"])

        # Chuẩn hóa dữ liệu học tập thông qua module normalize.py
        normalized_data = normalize_transcript(result["all_subjects"])'''

    if old_part in content:
        content = content.replace(old_part, bad_part, 1)
        
    # Remove duplicate summary_contract
    dup_summary = '''        summary_contract = {

        summary_contract = {'''
        
    if dup_summary in content:
        content = content.replace(dup_summary, '        summary_contract = {', 1)

    with open(api_path, 'w', encoding='utf-8') as f:
        f.write(content)

fix_api_py()
