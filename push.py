import os
import subprocess

def run_command(command):
    try:
        result = subprocess.run(command, shell=True, check=True, text=True, capture_output=True)
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        print(f"\n❌ Error: {e.stderr}")
        return None

def fast_push():
    print("🚀 Starting Fast Push...")
    
    # 1. Git Add
    run_command("git add .")
    print("✅ Files staged.")

    # 2. Get Commit Message
    commit_msg = input("📝 Enter commit message (or press Enter for 'Quick Update'): ")
    if not commit_msg:
        commit_msg = "Quick Update"

    # 3. Git Commit
    run_command(f'git commit -m "{commit_msg}"')
    
    # 4. Get Current Branch
    branch = run_command("git rev-parse --abbrev-ref HEAD")
    
    if branch:
        print(f"🛰️  Pushing to branch: {branch}...")
        push_output = run_command(f"git push origin {branch}")
        if push_output is not None:
            print(f"🎉 Successfully pushed to GitHub!")
        else:
            print("⚠️  Push failed. Check your internet or GitHub permissions.")

if __name__ == "__main__":
    fast_push()
