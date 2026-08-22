# LinuxQuest — GitHub Pages Ready

This is your original LinuxQuest game packaged for browser play.

## What was changed

- Original `engine/` and missions are preserved.
- Added a browser terminal using xterm.js.
- Added Pyodide so the existing Python game runs in WebAssembly.
- Added browser `localStorage` persistence for game progress.
- Added a browser-friendly SSH password prompt.
- Added GitHub Pages deployment via GitHub Actions.
- No access to the player's real filesystem or network is required.

## Deploy to GitHub Pages

1. Create a GitHub repository, e.g. `linuxquest`.
2. Upload the contents of this ZIP to the repository root.
3. Push to the `main` branch.
4. In GitHub, open **Settings → Pages**.
5. Set **Source** to **GitHub Actions**.
6. Wait for the `Deploy LinuxQuest to GitHub Pages` workflow.
7. Open the Pages URL shown by GitHub.

The game will then be accessible from a normal web URL.

## Local test

Do not open `index.html` with `file://`.

Run:

    python -m http.server 8000

Then visit:

    http://localhost:8000/

## Browser dependencies

The browser shell loads:

- Pyodide from jsDelivr
- xterm.js from jsDelivr

Therefore the first launch needs an internet connection. The game itself runs in the browser after the runtime and game files have loaded.
