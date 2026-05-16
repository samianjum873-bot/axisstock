import os
import subprocess

def run_command(command):
    try:
        result = subprocess.run(command, shell=True, check=True, text=True, capture_output=True)
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        print(f"\n❌ Error: {e.stderr if e.stderr else e.output}")
        return None

def load_token():
    if os.path.exists(".env"):
        with open(".env", "r") as f:
            for line in f:
                if line.startswith("GITHUB_TOKEN="):
                    return line.strip().split("=")[1]
    return None

def fast_push():
    print("🚀 Starting Fast Push with Secure Environment...")
    
    TOKEN = load_token()
    USERNAME = "samianjum"
    
    if not TOKEN:
        print("❌ Error: .env file mein GITHUB_TOKEN nahi mila!")
        return

    REPO_URL = f"https://{USERNAME}:{TOKEN}@github.com/samianjum/axisstock.git"
    
    # Background mein authenticated remote set karein
    run_command(f"git remote set-url origin {REPO_URL}")

    # 1. Git Add
    run_command("git add .")
    print("✅ Files staged.")

    # 2. Get Commit Message
    commit_msg = input("📝 Enter commit message (or press Enter for 'Quick Update'): ")
    if not commit_msg:
        commit_msg = "Quick Update"

    # 3. Git Commit
    run_command(f'git commit -m "{commit_msg}"')

    # 4. Push to GitHub
    print("🛰️  Pushing to branch: main securely...")
    push_output = run_command("git push origin main")
    
    if push_output is not None:
        print("🎉 Successfully pushed to GitHub!")
    else:
        print("⚠️  Push failed. Check your token or repository state.")

if __name__ == "__main__":
    fast_push()
