# Philippine Government URL Typosquatting System

This project has two separate workflows:

- **Live application**: Flask backend, MySQL seed data, local scanner, and Chrome extension.
- **Thesis demonstration**: standalone enhanced-Levenshtein trace with compact terminal output.

## Quick start on Windows

Install [Python 3.10 or newer](https://www.python.org/downloads/windows/) and
MySQL 8.0 or newer first. During Python installation, enable **Add Python to
PATH**.

Open PowerShell in the cloned repository and copy/paste:

```powershell
.\setup.ps1
```

Start MySQL, then start the backend:

```powershell
.\start-backend.ps1
```

The script asks for the MySQL password, seeds the database, and starts the
backend at `http://127.0.0.1:5000`.

Open a second PowerShell window in the same repository for the interactive
scanner:

```powershell
.\run-local-test.ps1
```

If PowerShell blocks local scripts, run them with:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\setup.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\start-backend.ps1
```

The `.bat` versions (`setup.bat`, `start-backend.bat`, and
`run-local-test.bat`) can also be double-clicked.

## Quick start on macOS/Linux

From this folder, install dependencies once:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

Start the live backend:

```bash
./DEFENSE_1_START_BACKEND.command
```

Enter the MySQL root password when prompted. The backend runs at
`http://127.0.0.1:5000`.

In a second terminal, start the interactive scanner:

```bash
./DEFENSE_3_RUN_LOCAL_TEST.command
```

The scanner accepts multiple URLs until `Ctrl+C` is pressed.

## Thesis simulation

The simulation is independent of Flask and MySQL:

```bash
.venv/bin/python simulation/sim_enhanced.py
```

It uses a hardcoded target/candidate pair and prints the detailed operation
trace. On Windows, run:

```powershell
.\run-simulation.ps1
```

The `run-simulation.bat` file can also be double-clicked.

## Chrome extension

1. Start the backend with `.\start-backend.ps1`.
2. Open Chrome and go to `chrome://extensions`.
3. Enable **Developer mode**.
4. Click **Load unpacked**.
5. Select the repository's `clients\extension` folder.
6. Open the extension from Chrome's toolbar and scan the active tab or enter a
   test URL.

The extension calls the local backend at
`http://127.0.0.1:5000/check-url`, so the backend must remain running. On
macOS, `./DEFENSE_2_OPEN_CHROME_EXTENSION.command` opens the extensions page.

## Research experiment

The research experiment is independent of MySQL and can be run after
`.\setup.ps1`:

```bash
./RESEARCH_RUN_EXPERIMENT.command
```

Research input data is in [`research/data/`](research/data/), and generated
results are written to `research/results/`. On Windows, run:

```powershell
.\run-research.ps1
```

This runs both the calibration experiment and the comparative evaluation.
Generated results are intentionally ignored by Git so each user can produce
their own results locally.

To regenerate the comparative evaluation dataset used for Table 3.3, run:

```bash
.venv/bin/python generate_and_evaluate.py
```

This loads `research/data/ph_gov_domains.txt` and the current US CSV list,
generates deterministic
visual-homoglyph, transposition, omission, and insertion variants, prints
TP/TN/FP/FN, precision, recall, and F1-score for both algorithms, and writes
line-by-line results to `research/results/updated_results.csv`.

To collect domains from one or more directory pages, run:

```bash
.venv/bin/python -m research.scrape_domains \
  "https://en.wikipedia.org/wiki/Category:Government_agencies_of_the_Philippines"
```

The scraper uses a Chrome User-Agent, waits 3–6 seconds between page requests,
and writes unique `.gov.ph` domains to `scraped_domains.txt`.

## Folder guide

| Folder | Purpose |
| --- | --- |
| [`backend/`](backend/) | Flask API and production scoring algorithm |
| [`clients/`](clients/) | Interactive scanner and Chrome extension |
| [`simulation/`](simulation/) | Standalone thesis trace |
| [`research/`](research/) | Calibration scripts, domain data, and experiment results |
| [`docs/`](docs/) | Thesis and government-directory reference documents |
| [`_archive/`](_archive/) | Reserved for obsolete files retained during cleanup |

The root `.command` files and `run.sh` are compatibility launchers so the
existing macOS defense workflow remains unchanged. Personal Markdown notes,
reference documents, archives, generated results, local environments, and
operating-system files are excluded by `.gitignore`; `README.md` and the
research input data remain available in the repository.
