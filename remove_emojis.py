import os
import re

# [OK] Emoji ทั้งหมดที่อาจมีในโปรเจค
EMOJIS = [
    "[BOT]", "[INFO]", "[TRADE]", "[ALERT]", "[WARN]", "[OK]", "[ERROR]", "[SELL]", "[BUY]",
    "[UP]", "[DOWN]", "[NOTIFY]", "[AI]", "[UPDATE]", "[TIME]", "[PARACHUTE]", "[BTC]", "[GOLD]", "[USD]", "[LOG]"
]

# [OK] ตารางแทนที่ (ถ้าอยากเก็บความหมาย)
EMOJI_MAP = {
    "[BOT]": "[BOT]", "[INFO]": "[INFO]", "[TRADE]": "[TRADE]", "[ALERT]": "[ALERT]",
    "[WARN]": "[WARN]", "[OK]": "[OK]", "[ERROR]": "[ERROR]", "[SELL]": "[SELL]",
    "[BUY]": "[BUY]", "[UP]": "[UP]", "[DOWN]": "[DOWN]", "[NOTIFY]": "[NOTIFY]",
    "[AI]": "[AI]", "[UPDATE]": "[UPDATE]", "[TIME]": "[TIME]", "[PARACHUTE]": "[PARACHUTE]",
    "[BTC]": "[BTC]", "[GOLD]": "[GOLD]", "[USD]": "[USD]", "[LOG]": "[LOG]",
}

def remove_emojis_in_file(filepath):
    """ลบ emoji ในไฟล์"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        original = content
        
        # [OK] แทนที่ emoji ด้วยข้อความ (หรือลบทิ้ง)
        for emoji, replacement in EMOJI_MAP.items():
            content = content.replace(emoji, replacement)
        
        # [OK] หรือถ้าอยากลบทิ้งเลย → ใช้บรรทัดนี้แทน:
        # for emoji in EMOJIS:
        #     content = content.replace(emoji, '')
        
        if content != original:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"[OK] Fixed: {filepath}")
            return True
        return False
        
    except Exception as e:
        print(f"[ERROR] Error {filepath}: {e}")
        return False

def scan_project(root_dir):
    """สแกนทั้งโปรเจค"""
    files_fixed = 0
    
    for root, dirs, files in os.walk(root_dir):
        # ข้ามโฟลเดอร์ที่ไม่จำเป็น
        if '__pycache__' in root or '.git' in root or 'venv' in root:
            continue
        
        for file in files:
            if file.endswith('.py'):
                filepath = os.path.join(root, file)
                if remove_emojis_in_file(filepath):
                    files_fixed += 1
    
    print(f"\n[OK] Done! Fixed {files_fixed} files")

# [OK] รันสคริปต์
if __name__ == "__main__":
    print("🔍 Scanning project for emojis...")
    scan_project(".")  # สแกนโฟลเดอร์ปัจจุบัน