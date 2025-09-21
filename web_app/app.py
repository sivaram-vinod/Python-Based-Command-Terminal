# web_app/app.py
"""
Safe Flask wrapper for PyTerminal demo.

This file intentionally avoids running arbitrary shell commands.
It exposes a tiny allowlist of safe commands implemented in Python
so it works on Windows, macOS, and Linux.
"""

from flask import Flask, request, render_template, jsonify
import shlex
import os
from pathlib import Path
import json
import shutil

# optional psutil imports
try:
    import psutil
except Exception:
    psutil = None

app = Flask(__name__)

# ---------- utility functions ----------
def _expand_path(p: str):
    if not p:
        return p
    return os.path.normpath(os.path.expanduser(os.path.expandvars(p)))

def safe_ls(args):
    """List directory contents. args: list of path parts (maybe empty)."""
    path = args[0] if args else "."
    path = _expand_path(path)
    try:
        if not os.path.exists(path):
            return {"ok": False, "output": f"ls: no such file or directory: {path}"}
        if os.path.isdir(path):
            entries = sorted(os.listdir(path))
            out_lines = []
            for name in entries:
                full = os.path.join(path, name)
                suffix = "/" if os.path.isdir(full) else ""
                out_lines.append(name + suffix)
            return {"ok": True, "output": "\n".join(out_lines)}
        else:
            # if path is a file, just show the filename
            return {"ok": True, "output": os.path.basename(path)}
    except PermissionError:
        return {"ok": False, "output": f"ls: permission denied: {path}"}
    except Exception as e:
        return {"ok": False, "output": f"ls: error: {e}"}

def safe_pwd(args):
    return {"ok": True, "output": os.getcwd()}

def safe_cat(args):
    if not args:
        return {"ok": False, "output": "cat: missing file operand"}
    path = _expand_path(args[0])
    try:
        if os.path.isdir(path):
            return {"ok": False, "output": f"cat: {path}: Is a directory"}
        with open(path, "r", encoding="utf-8") as f:
            return {"ok": True, "output": f.read()}
    except FileNotFoundError:
        return {"ok": False, "output": f"cat: no such file: {path}"}
    except PermissionError:
        return {"ok": False, "output": f"cat: permission denied: {path}"}
    except Exception as e:
        return {"ok": False, "output": f"cat: error: {e}"}

def safe_mkdir(args):
    if not args:
        return {"ok": False, "output": "mkdir: missing operand"}
    path = _expand_path(args[0])
    try:
        os.makedirs(path, exist_ok=True)
        return {"ok": True, "output": f"created directory: {path}"}
    except Exception as e:
        return {"ok": False, "output": f"mkdir: error: {e}"}

def safe_rm(args):
    if not args:
        return {"ok": False, "output": "rm: missing operand"}
    # support rm -r <path>
    r_flag = False
    idx = 0
    if args[0] == "-r":
        r_flag = True
        idx = 1
        if len(args) <= 1:
            return {"ok": False, "output": "rm: missing operand after -r"}
    target = _expand_path(args[idx])
    try:
        if os.path.isdir(target):
            if r_flag:
                shutil.rmtree(target)
                return {"ok": True, "output": f"removed directory: {target}"}
            else:
                return {"ok": False, "output": "rm: cannot remove directory (use -r to remove directories)"}
        else:
            os.remove(target)
            return {"ok": True, "output": f"removed file: {target}"}
    except FileNotFoundError:
        return {"ok": False, "output": f"rm: no such file or directory: {target}"}
    except PermissionError:
        return {"ok": False, "output": f"rm: permission denied: {target}"}
    except Exception as e:
        return {"ok": False, "output": f"rm: error: {e}"}

def safe_ps(args):
    if psutil:
        try:
            procs = []
            for p in psutil.process_iter(["pid", "name"]):
                info = p.info
                procs.append(f"{info['pid']:6}  {info['name']}")
            return {"ok": True, "output": "\n".join(procs[:200])}
        except Exception as e:
            return {"ok": False, "output": f"ps: error: {e}"}
    else:
        return {"ok": False, "output": "ps: psutil not installed on the server."}

def safe_sys(args):
    if psutil:
        try:
            cpu = psutil.cpu_percent(interval=0.3)
            mem = psutil.virtual_memory()
            out = f"CPU usage: {cpu}%\nMemory: {mem.percent}% used — {round(mem.used/1024/1024,1)}MB used / {round(mem.total/1024/1024,1)}MB total"
            return {"ok": True, "output": out}
        except Exception as e:
            return {"ok": False, "output": f"sys: error: {e}"}
    else:
        return {"ok": False, "output": "sys: psutil not installed on the server."}

# ---------- allowlist mapping ----------
ALLOWED = {
    "ls": safe_ls,
    "pwd": safe_pwd,
    "cat": safe_cat,
    "mkdir": safe_mkdir,
    "rm": safe_rm,
    "ps": safe_ps,
    "sys": safe_sys,
}

# ---------- routes ----------
@app.route("/")
def index():
    return render_template("index.html")

@app.route("/ping")
def ping():
    return jsonify({"ok": True, "msg": "pong"})
# add this above the /run route (anywhere near other routes)
@app.route("/testform", methods=["GET", "POST"])
def test_form():
    """
    Very small HTML form to test POSTing to /run from a browser without JS.
    Submits to /run but we present the response as plain text.
    """
    from flask import request, Response, redirect, url_for
    if request.method == "POST":
        # forward the same form data to the existing /run handler by calling it directly
        # Build a tiny request-like dict and call run_command()
        form_cmd = request.form.get("cmd", "")
        # Call the existing function directly to reuse logic:
        with app.test_request_context(method="POST", data={"cmd": form_cmd}):
            resp = run_command()  # reuse existing handler; it returns a Flask Response/json
            # resp may be a tuple or Response; standardize to Response then return text
            try:
                # If resp is (body, status), handle that
                if isinstance(resp, tuple):
                    body = resp[0].get_json() if hasattr(resp[0], 'get_json') else resp[0]
                else:
                    body = resp.get_json() if hasattr(resp, 'get_json') else resp
            except Exception:
                body = {"ok": False, "output": "Internal response parse error"}
        # return the output as plain text so it's human-readable
        out_text = body.get("output", "") if isinstance(body, dict) else str(body)
        return Response(out_text, mimetype="text/plain")
    # GET: show a simple form
    return """
    <!doctype html>
    <html>
      <body style="font-family:Helvetica,Arial,monospace;padding:20px;">
        <h3>Test form — send a command to /run</h3>
        <form method="post">
          <input name="cmd" placeholder="e.g. ls" style="width:300px;padding:8px;margin-right:8px"/>
          <button type="submit">Send</button>
        </form>
        <p>After submitting, the response will be displayed as plain text.</p>
      </body>
    </html>
    """
from flask import request, Response

@app.route("/run_get")
def run_get():
    # use query param ?cmd=... to call the same run handler but via GET for quick debugging
    cmd = request.args.get("cmd", "")
    # call run_command() inside a test_request_context to reuse the logic
    with app.test_request_context(method="POST", data={"cmd": cmd}):
        resp = run_command()
        # resp may be a Response or (body, status)
        try:
            if isinstance(resp, tuple):
                body = resp[0].get_json() if hasattr(resp[0], "get_json") else resp[0]
            else:
                body = resp.get_json() if hasattr(resp, "get_json") else resp
        except Exception:
            body = {"ok": False, "output": "internal parse error"}
    out = body.get("output", "") if isinstance(body, dict) else str(body)
    return Response(out, mimetype="text/plain")


@app.route("/run", methods=["POST"])
def run_command():
    data = request.form
    cmdline = data.get("cmd", "").strip()
    if not cmdline:
        return jsonify({"ok": False, "output": "No command provided"}), 400

    # split safely
    try:
        parts = shlex.split(cmdline)
    except Exception:
        parts = cmdline.split()
    name = parts[0]
    args = parts[1:]

    func = ALLOWED.get(name)
    if not func:
        return jsonify({"ok": False, "output": f"Command not allowed: {name}"}), 403

    try:
        result = func(args)
        # result is expected to be a dict {"ok": bool, "output": str}
        if not isinstance(result, dict) or "ok" not in result or "output" not in result:
            return jsonify({"ok": False, "output": "Internal: command handler returned bad response"}), 500
        return jsonify(result)
    except Exception as e:
        return jsonify({"ok": False, "output": f"Error executing command: {e}"}), 500

if __name__ == "__main__":
    # local dev server
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=True)
