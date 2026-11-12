# ChapterCraft

ChapterCraft turns SRT, WebVTT, or pasted timestamped transcripts into editable
video chapter suggestions. The chapter generator compares English vocabulary
across nearby time windows and uses topic words to draft titles.

## Run locally

Run `python app.py` with Python 3, or `py app.py` on Windows, then open
http://127.0.0.1:5000. Choose **Try sample** and **Generate chapters**, or supply
your own captions. Review the suggested timestamps and titles before copying them.

The app uses Python's standard library, processes transcripts in memory, and
listens only on the local machine.
