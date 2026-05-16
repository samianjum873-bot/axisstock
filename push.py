import os
import subprocess

def run_command(command):
    try:
        result = subprocess.run(command, shell=True, check=True, text=True, capture_output=True)
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        print(f"\n❌ Error: {e.stderr if e.stderr else e.output}")
        return None

def fast_push():
    print("🚀 Starting Fast Push with Classic Token...")
    
    USERNAME = "samianjum"
    # Aap ka naya Classic Token
    TOKEN = "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"
    REPO_URL = f"https://{USERNAME}:{TOKEN}@github.com/samianjum/axisstock.git"
    
    # Remote URL reset aur set karein
    run_command("git remote remove origin")
    run_command(f"git remote add origin {REPO_URL}")
    run_command("git branch -M main")

    # 2. Git Add
    run_command("git add .")
    print("✅ Files staged.")

    # 3. Get Commit Message
    commit_msg = input("📝 Enter commit message (or press Enter for 'Quick Update'): ")
    if not commit_msg:
        commit_msg = "Quick Update"

    # 4. Git Commit
    run_command(f'git commit -m "{commit_msg}"')

    # 5. Push to GitHub
    print("🛰️  Pushing to branch: main using Classic Token...")
    push_output = run_command("git push -u origin main")
    
    if push_output is not None:
        print("🎉 Successfully pushed to GitHub!")
    else:
        print("⚠️  Push failed. Agar error 403 hai to token banate waqt 'repo' check karna lazmi tha.")

if __name__ == "__main__":
    fast_push()
