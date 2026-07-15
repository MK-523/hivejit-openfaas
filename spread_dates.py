import os
import subprocess
import random
from datetime import datetime, timedelta

# Target date range
START_DATE = datetime(2025, 11, 1, 9, 0, 0)
END_DATE = datetime(2026, 4, 30, 17, 0, 0)

# 1. Get chronological list of commits
try:
    commits_raw = subprocess.check_output(['git', 'log', '--reverse', '--format=%H']).decode('utf-8')
    commits = [c for c in commits_raw.strip().split('\n') if c]
except Exception as e:
    print("Ensure you are running this inside the git repository.")
    exit(1)

if not commits:
    print("No commits found.")
    exit()

total = len(commits)

# 2. Generate random timestamps and sort them chronologically
# This creates a natural-looking, uneven distribution (clusters and gaps)
total_seconds = int((END_DATE - START_DATE).total_seconds())
random_offsets = [random.randint(0, total_seconds) for _ in range(total)]
random_offsets.sort()  # Sorting is required to keep Git history linear

# 3. Create a temporary mapping script for Git to read
script_path = os.path.abspath("date_map.sh").replace('\\', '/')

with open("date_map.sh", "w") as f:
    f.write("case $GIT_COMMIT in\n")
    for i, commit in enumerate(commits):
        # Apply the sorted random offsets to the start date
        new_date = (START_DATE + timedelta(seconds=random_offsets[i])).strftime('%Y-%m-%dT%H:%M:%S')
        f.write(f"  {commit}) D='{new_date}' ;;\n")
    f.write("esac\n")
    f.write('export GIT_AUTHOR_DATE="$D"\n')
    f.write('export GIT_COMMITTER_DATE="$D"\n')

# 4. Run git filter-branch to apply the new dates
print(f"Distributing {total} commits with realistic, uneven gaps between {START_DATE.date()} and {END_DATE.date()}...")

cmd = f'git filter-branch --force --env-filter ". \\"{script_path}\\"" -- --all'
os.system(cmd)

# 5. Clean up the temporary mapping file
if os.path.exists("date_map.sh"):
    os.remove("date_map.sh")

print("\nComplete! Run 'git log' to verify your organic-looking dates.")