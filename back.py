import os
import subprocess

print("--- 🛠️ AXIS GIT BACKUP MANAGER ---")
try:
    log_format = "%h - %cd : %s"
    result = subprocess.run(["git", "log", "-n", "10", f"--format={log_format}", "--date=relative"], capture_output=True, text=True, check=True)
    print("\nAvailable Backups (Most Recent First):")
    print("=" * 50)
    print(result.stdout.strip())
    print("=" * 50)
    
    commit_hash = input("\nEnter the Backup/Commit ID to recover (or press Enter to cancel): ").strip()
    if commit_hash:
        confirm = input(f"⚠️ HARD RESET to '{commit_hash}'? Unsaved work will be lost! (y/n): ").strip().lower()
        if confirm == 'y':
            reset_result = subprocess.run(["git", "reset", "--hard", commit_hash], capture_output=True, text=True)
            if reset_result.returncode == 0:
                print(f"\n✅ Success! System recovered to: {commit_hash}")
            else:
                print(f"\n❌ Error: {reset_result.stderr}")
except Exception as e:
    print(f"Error: {e}")
