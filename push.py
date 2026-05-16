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
    print("🚀 Starting Fast Push with Secure Token...")
    
    # 1. Hardcoded Token Configuration
    # (Agli dafa token change karna ho to sirf neeche wali do lines badlein)
    USERNAME = "samianjum"
    TOKEN = "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"
    REPO_URL = f"https://{USERNAME}:{TOKEN}@github.com/samianjum/axisstock.git"
    
    # Remote URL ko chup chaap background mein update kar dete hain
    run_command(f"git remote set-url origin {REPO_URL}")

    # 2. Git Add
    run_command("git add .")
    print("✅ Files staged.")

    # 3. Get Commit Message
    commit_msg = input("📝 Enter commit message (or press Enter for 'Quick Update'): ")
    if not commit_msg:
        commit_msg = "Quick Update"

    # 4. Git Commit
    commit_output = run_command(f'git commit -m "{commit_msg}"')
    if commit_output and "nothing to commit" in commit_output:
        print("ℹ️ Nothing new to commit, checking push status...")

    # 5. Get Current Branch
    branch = run_command("git rev-parse --abbrev-ref HEAD")
    
    if branch:
        print(f"🛰️  Pushing to branch: {branch} using Access Token...")
        # Direct authenticated URL par push maarenge taake cache ka panga hi khatam ho
        push_output = run_command(f"git push origin {branch}")
        if push_output is not None:
            print(f"🎉 Successfully pushed to GitHub!")
        else:
            print("⚠️  Push failed. Token invalid ho chuka hai ya permissions ka masla hai.")

if __name__ == "__main__":
    fast_push()
