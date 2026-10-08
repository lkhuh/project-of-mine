# School Question Paper Generator (Offline-First, Free)

A desktop app for your father's school: learn a question-paper pattern once
from sample papers, then generate new papers for a class + exam type +
subject — either from a photo of handwritten questions, or by having AI
write original questions from the syllabus. Runs fully offline by default
(free local AI via Ollama); optionally you can switch to Google's Gemini
cloud API in Settings for more accurate questions (needs internet + a free
API key).

## What it uses (all free by default)

| Job | Tool | Notes |
|---|---|---|
| Reading printed sample papers | Tesseract OCR | Free, offline, accurate on printed text |
| Reading handwritten photos | TrOCR (Microsoft, via `transformers`) | Free, runs locally. First use downloads the model (~1.3GB, one-time internet use), then fully offline forever |
| Writing questions from the syllabus | A local LLM via **Ollama** (default), or **Google Gemini** (optional) | Ollama: free, offline, but noticeably weaker at matching curriculum details precisely. Gemini: needs internet + an API key, generally more accurate — see "Optional: using Gemini instead of Ollama" below |
| PDF output | `reportlab` | Free, offline |
| Word output | `python-docx` | Free, offline |
| Final review/edit | Built into the app | Every field is editable before export |

## 1. One-time setup (on each teacher's computer)

1. **Install Python 3.10+**: https://www.python.org/downloads/
2. **Install Tesseract OCR** (the printed-text reader):
   - Windows: installer from https://github.com/UB-Mannheim/tesseract/wiki
   - Mac: `brew install tesseract`
   - Linux: `sudo apt install tesseract-ocr`
   - If Windows can't find it automatically, open the app's **Settings**
     screen and paste the full path to `tesseract.exe` there.
3. **Install Ollama** (the local AI for syllabus-based question writing):
   - Download from https://ollama.com and install it.
   - Then open a terminal and run:
     ```
     ollama pull llama3.2
     ```
     (this downloads the free model once, ~2GB; needs a computer with at
     least 8GB RAM to run smoothly)
4. **Install the app's Python packages**. Open a terminal **inside the
   `qpapp` folder** (the one containing `requirements.txt`) and run:
   ```
   cd qpapp
   pip install -r requirements.txt
   ```
5. **Run the app**:
   ```
   python main.py
   ```
   The very first time you use "Read Handwriting", it will download the
   TrOCR model automatically (needs internet, ~1.3GB, one-time only).

## 2. Using the app

1. **Home** → pick a class (1–8) → pick an **exam type** → pick/type a **subject**.
2. First time for that combination: click **"Set / Update Pattern"**, upload
   photo(s) of a sample paper, click **"Read Sample Paper(s)"**. The app
   guesses the pattern (sections, marks, instructions) using offline OCR and
   simple rules — **always review and correct the JSON shown** before
   clicking Save, since offline rule-based reading isn't perfect.
3. To make an actual paper, click **"Generate New Question Paper"**, then either:
   - Upload a photo of handwritten questions → click **"Read Handwriting"** →
     review/correct the extracted text (offline handwriting reading makes
     more mistakes than typed text, so check it carefully) → click
     **"Generate Paper (PDF)"**. If there aren't quite enough handwritten
     questions to fill every slot in the pattern, the local AI (Ollama)
     fills the remaining ones automatically.
   - Or choose **"No photo — let the local AI write questions from the
     syllabus"** → click **"Generate Paper (PDF)"**. The local AI writes an
     original paper matching the pattern, based on the UP Board/NCERT
     syllabus for that class and subject.
4. **Review & Edit screen**: the full paper (header, instructions, every
   question and its marks) shows up as editable text — change anything you
   want here (fix a question, adjust marks, reword instructions).
5. Tick **PDF**, **Word (.docx)**, or both, then click **Export**. The
   finished paper(s) are saved in `data/output/`.
6. Or click **Print** to send the paper straight to the computer's default
   printer (it builds the PDF and prints it in one step). If your printer
   isn't set up to receive this automatically, it'll tell you to open the
   saved PDF and print it manually instead.

## 3. Building a Windows .exe (optional, one-time per computer)

If you'd rather teachers double-click an icon than run `python main.py`
from a terminal, you can package the app into a standalone `.exe`:

1. Make sure Python 3.10+ is installed (see step 1 above).
2. Open a terminal inside the `qpapp` folder.
3. Double-click **`build_exe.bat`** (or run it from the terminal). It
   installs the app's dependencies + PyInstaller, then builds the exe.
   This takes a few minutes the first time (torch/transformers are large).
4. Your app is now at `dist\QuestionPaperGenerator\QuestionPaperGenerator.exe`.
   Copy the **whole `QuestionPaperGenerator` folder** (not just the .exe —
   it needs the files sitting next to it) to wherever you want to run it
   from, or onto another Windows computer. Tesseract and Ollama still need
   to be installed separately on that computer (see step 1) — the exe
   bundles the Python app itself, not those two external programs.

**Note:** this must be run *on Windows* to produce a Windows exe —
PyInstaller packages for whatever OS it's running on; it can't cross-build
a Windows exe from Linux/Mac (or vice versa).

## A note on an Android (.apk) version

This app can't be turned into a faithful Android app the way it can into a
Windows exe, for a few real reasons rather than just effort:

- **Tesseract OCR** is a separate native program the app shells out to --
  there's no equivalent "just install it" path on Android.
- **Ollama** (the free local AI) is a desktop background service; it has
  no Android build at all.
- **TrOCR** (handwriting reading) uses PyTorch, which is large and slow
  enough that it's impractical to bundle and run on a phone the same way.

A true Android version would mean a different, smaller app: cloud-only AI
(Gemini) instead of local Ollama, no offline handwriting reading, and a
different OCR approach -- essentially a lighter-weight companion app, not a
straight port of this one. If that trade-off is worth it to you, it's a
separate, scoped rebuild rather than a quick export of this project.

## Optional: using Gemini instead of Ollama

By default the app writes AI questions using the free, offline Ollama
model. If you'd rather use Google's Gemini (usually better at matching
NCERT topics precisely, but needs internet and an API key):

1. Get a free API key from https://aistudio.google.com/app/apikey (a
   Google account is enough; there's a free daily quota, then it's
   pay-as-you-go if you exceed it).
2. Open the app's **Settings** screen.
3. Under "AI provider", select **Gemini**.
4. Paste the API key into the **Gemini API key** field.
5. Leave **Gemini model name** as `gemini-flash-latest` (Google's own alias
   for their current recommended fast model — it stays up to date on its
   own) unless you want to try a different one, e.g. a "pro" model for
   higher quality at higher cost.
6. Click **Save**.

You can switch back to Ollama at any time from the same screen. The API key
is stored only on this computer, in `~/.qpapp/config.json`.

## Diagrams (geometry, graphs, number lines, circuits)

When the AI writes a paper from the syllabus (no photo), it can also add a
**diagram** to a question that genuinely needs one -- but not by generating
an image directly. Instead, the AI (Ollama or Gemini, either works) outputs
plain numbers describing the figure (e.g. "triangle with sides 3, 4, 5" or
"plot y = x^2 from -3 to 3"), and the app draws it precisely from those
numbers using a normal charting library. This is deliberately more limited
than "AI draws any picture", but it means the shape, labels, and numbers on
the diagram are always exactly correct -- important for something going on
a real exam.

Supported diagram types: triangles/polygons with labelled sides and
vertices, function graphs, number lines, and simple series circuits
(battery, resistor, bulb, switch). Anything else (e.g. "draw a labelled
plant cell") isn't attempted -- the question is written without a diagram
rather than risking an inaccurate one.

Diagrams show up automatically under the relevant question in both the PDF
and Word output. You can also see/edit the raw diagram data on the Review &
Edit screen, since it's just part of that question's JSON.

## Notes and honest limitations

- **Offline handwriting reading is not as accurate as a paid cloud AI**,
  especially with messy handwriting, math symbols, or diagrams — that's why
  there's always a review/edit step before the PDF is made.
- **The local AI (Ollama/llama3.2) is weaker than a large cloud model** at
  precisely matching NCERT topics — a teacher should glance over
  AI-generated questions before printing, the same way you'd review any
  question paper.
- Patterns are saved per (class, exam type, subject) in `data/templates/`
  as JSON — back this folder up if you reinstall.
- To change the classes list, exam types, or subject list, edit `CLASSES`,
  `EXAM_TYPES`, `SUBJECTS` near the top of `gui/app.py`.
- To use a different (possibly better/slower) local model, run
  `ollama pull <model name>` and set it in the app's Settings screen.
