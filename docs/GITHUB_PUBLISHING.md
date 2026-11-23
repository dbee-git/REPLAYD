# Publish the REPLAYD portfolio repository

## Before publishing

The archive is a **clean source release**. It intentionally excludes any `.local_data/` SQLite databases, private uploads, actual football broadcasts, rendered user clips and personal campaign/earnings records. Never copy those files into the repository. Keep your v0.6 folder as a backup of your private working data.

Review `docs/LIMITATIONS.md` for claims this project cannot yet make. This is a local-first project: **do not deploy `python run.py` publicly** as a multi-user service.

## Create the GitHub repository

1. Open https://github.com/new, signed in to your own account.
2. Repository name: `REPLAYD` (or `replayd-football-creator-studio` if occupied).
3. Choose **Public** for a portfolio, unless you want to review privately first.
4. Description: `Local-first football highlight discovery, creator analytics & paid campaign tracking — FastAPI, FFmpeg, SQLite`.
5. **Leave GitHub's README, .gitignore and license checkboxes unchecked.** These already exist in this source release.
6. Create the empty repository. Copy its actual HTTPS Git URL (avoid inventing a URL).

## Push from your Mac

Extract the portfolio ZIP into Downloads and run:

```bash
cd ~/Downloads/REPLAYD_v1_0_PORTFOLIO
git init -b main
# Stage source files explicitly instead of including accidental private footage.
git add README.md LICENSE .gitignore requirements.txt run.py start_mac.command
git add replayd static tests scripts data docs evaluation .github
git status --short
```

**Before committing**, confirm that `git status --short` lists only code, docs, tests, generated synthetic fixtures and screenshots. Do not stage private MP4s or database files.

```bash
git commit -m "Release REPLAYD portfolio v1.0"
git remote add origin YOUR_ACTUAL_GITHUB_REPO_HTTPS_URL
git push -u origin main
```

Replace the placeholder URL with the **real** URL provided by GitHub. Authenticate through your configured Git credentials or GitHub Desktop. Do not paste passwords or tokens into chat.

GitHub documentation: https://docs.github.com/en/repositories/creating-and-managing-repositories/creating-a-new-repository

## After the push

- Verify that `README.md` renders and `.github/workflows/tests.yml` appears under **Actions**.
- Inspect the repository file list for `.local_data`, actual football footage, SQLite databases and private data; none should be present.
- Copy the repository's real URL into your resume and project portfolio.
- Add a video link only after recording a genuine, clearly labeled demonstration.
- When actual held-out evaluation data exists, update the README benchmark table with real metrics and sample sizes.

The GitHub integration used in ChatGPT can add files **after** an actual repository exists, but it may not support creating repositories. The simplest first step is creating the empty repository in GitHub's web interface.
