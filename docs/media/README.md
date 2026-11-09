# Demo media

These assets are captured from, or generated around, Clira's real local **synthetic demo**.
No actual Google account, channel statistics, paid model requests, public replies or uploads are shown.

| Asset | Description |
|---|---|
| `clira-banner.svg` | Lightweight text/vector wordmark in Clira's charcoal, ivory and gold palette |
| `clira-preview.gif` | Silent looping preview of captured desktop, phone and completed-job screens |
| `Clira-tour.mp4` | 39-second, captioned guided tour using those screens, with visible preview limits |
| `Clira-cli.mp4` | 24-second captioned walkthrough of actual command-output excerpts |
| `cli-capture.json` | Captured output excerpts backing the CLI walkthrough |
| `*-poster.jpg` | Compressed video link posters |
| `clira-*.png` | Original browser-test screenshot evidence |

The guided tour uses pan/scroll presentation of static captures. It is not a continuous recording
of live YouTube or model behavior. The CLI video displays genuine command outputs with shorter
diagnostics for readability. Both are silent and include their explanations as readable on-screen text.

## Tour transcript

1. Your channel. One creative partner. Understand → Plan → Create → Review → Release.
2. Understand your channel with dated metrics, clear sources and channel context.
3. Carry ideas and operations between desktop and phone. The offline router uses templates;
   Gemini enables open-ended AI after owner configuration.
4. Review the exact action: MP4 QC → preview → owner approval → private-upload simulation → receipt.
5. Start locally with `./run.sh`. Google OAuth and a configured Gemini account are needed for live
   operations and model use. Live channel verification is pending; rendering stays external.

## Rebuild

Capture synthetic screens using `tests/browser_smoke.py`, then run:

```bash
uv run --with pillow python scripts/make_release_media.py --screenshots /absolute/path/to/captures
```

The authoring script requires ffmpeg and system DejaVu fonts. Font files are not redistributed.
