const statusEl = document.getElementById("status");
const terminalEl = document.getElementById("terminal");
const restartBtn = document.getElementById("restart");
const clearBtn = document.getElementById("clear");

const term = new Terminal({
  cursorBlink: true,
  convertEol: true,
  fontSize: 14,
  scrollback: 5000,
  theme: {
    background: "#000000",
    foreground: "#e6edf3",
    cursor: "#58a6ff"
  }
});
const fit = new FitAddon.FitAddon();
term.loadAddon(fit);
term.open(terminalEl);
fit.fit();
window.addEventListener("resize", () => fit.fit());

const PY_FILES = ["engine/__init__.py", "engine/manpages.py", "engine/missions.py", "engine/save.py", "engine/shell.py", "engine/ui.py", "engine/vfs.py", "engine/vnet.py", "main.py"];
let pyodide = null;
let inputBuffer = "";
let busy = false;
let running = true;
let passwordMode = false;

function write(text) {
  if (text) term.write(String(text).replace(/\n/g, "\r\n"));
}

async function py(command) {
  return await pyodide.runPythonAsync(command);
}

async function boot() {
  try {
    statusEl.textContent = "Loading Python…";
    pyodide = await loadPyodide();

    statusEl.textContent = "Loading LinuxQuest engine…";

    // Load every original Python source file into Pyodide's virtual filesystem.
    for (const file of PY_FILES) {
      const response = await fetch(file);
      if (!response.ok) throw new Error(`Failed to load ${file}`);
      const source = await response.text();
      const parent = file.substring(0, file.lastIndexOf("/"));
      if (parent) {
        const parts = parent.split("/");
        let current = "";
        for (const part of parts) {
          current += "/" + part;
          try { pyodide.FS.mkdir(current); } catch (_) {}
        }
      }
      pyodide.FS.writeFile("/" + file, source);
    }

    // Make sure the package is importable.
    pyodide.runPython(`
import sys
if "/" not in sys.path:
    sys.path.insert(0, "/")
exec(open("/runner.py").read(), globals())
`);

    const intro = await py("browser_start()");
    write(intro);
    write("\r\n");
    write(await py("browser_prompt()"));

    statusEl.textContent = "LinuxQuest ready";
    term.focus();
  } catch (err) {
    statusEl.textContent = "Startup failed";
    write("\\r\\n[ERROR] " + err.message + "\\r\\n");
    console.error(err);
  }
}

// We need safe JSON string encoding for arbitrary commands.
async function submitLine(line) {
  if (busy || !pyodide) return;
  busy = true;
  try {
    const encoded = JSON.stringify(line);
    const output = await py(`browser_command(${encoded})`);
    write(output);
    if (await py("browser_is_running()")) {
      write("\r\n" + await py("browser_prompt()"));
    } else {
      write("\r\n\\n[Game exited. Refresh the page to play again.]");
      running = false;
    }
  } catch (err) {
    write("\r\n[ERROR] " + err.message);
  } finally {
    busy = false;
  }
}

term.onData((data) => {
  if (!running || busy) return;

  if (data === "\r") {
    const line = inputBuffer;
    inputBuffer = "";
    term.write("\r\n");
    submitLine(line);
    return;
  }

  if (data === "\u007f") {
    if (inputBuffer.length) {
      inputBuffer = inputBuffer.slice(0, -1);
      term.write("\b \b");
    }
    return;
  }

  // Ctrl+C: don't kill the browser; just clear current input.
  if (data === "\u0003") {
    inputBuffer = "";
    term.write("^C\r\n");
    return;
  }

  if (data >= " " && data <= "~") {
    inputBuffer += data;
    term.write(data);
  }
});

restartBtn.addEventListener("click", () => {
  if (confirm("Reset LinuxQuest progress and start from Mission 1?")) {
    localStorage.removeItem("linuxquest_save");
    location.reload();
  }
});

clearBtn.addEventListener("click", () => {
  term.clear();
  
});

function awaitPromptFallback() {
  return "";
}

boot();
