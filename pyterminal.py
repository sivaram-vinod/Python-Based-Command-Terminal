#!/usr/bin/env python3
"""
pyterminal.py
A simple Python-based command terminal (CLI) with:
 - built-in commands: ls, cd, pwd, mkdir, rm, cat, touch, ps, sys, history
 - run shell commands with `! your command` or `shell your command`
 - basic file-path tab-completion
 - persistent command history (~/.pyterm_history)
 - uses psutil (if available) for system/process info
"""

import os
import shlex
import subprocess
import shutil
import sys
import glob
import cmd
import stat
from pathlib import Path

# optional imports
try:
    import readline  # unix-style history & completion
except Exception:
    readline = None

try:
    import psutil
except Exception:
    psutil = None


HISTORY_FILE = os.path.expanduser("~/.pyterm_history")


def _expand_path(p: str) -> str:
    """Expand user (~) and environment variables and return normalized path."""
    if not p:
        return p
    return os.path.normpath(os.path.expandvars(os.path.expanduser(p)))


def _is_dir(path: str) -> bool:
    try:
        return os.path.isdir(path)
    except Exception:
        return False


def _list_matches(prefix: str):
    """Return filesystem names matching prefix (for completion)."""
    if prefix == "":
        prefix = "."
    # Use glob to handle patterns and prefix
    base_dir = os.path.dirname(prefix) or "."
    pattern = os.path.basename(prefix) + "*"
    try:
        candidates = glob.glob(os.path.join(base_dir, pattern))
    except Exception:
        candidates = []
    # Normalize names for completion
    return [c if os.path.isabs(prefix) else c for c in candidates]


class PyTerminal(cmd.Cmd):
    intro = "Welcome to PyTerminal — a simple Python command terminal. Type help or ? to list commands."
    ruler = "-"
    file = None

    def __init__(self):
        super().__init__()
        self.prompt = f"{os.getcwd()} $ "
        self.history = []
        # load persistent history (readline)
        if readline:
            try:
                readline.read_history_file(HISTORY_FILE)
            except Exception:
                # no history file yet
                pass

    # -------------------------
    # helper internals
    # -------------------------
    def precmd(self, line: str) -> str:
        # store command in history (both our list and readline if available)
        line = line.strip()
        if line:
            self.history.append(line)
            if readline:
                try:
                    readline.add_history(line)
                    # write immediately to file for persistence
                    try:
                        readline.write_history_file(HISTORY_FILE)
                    except Exception:
                        pass
                except Exception:
                    pass
        return line

    def postcmd(self, stop: bool, line: str):
        # update prompt to reflect current directory
        self.prompt = f"{os.getcwd()} $ "
        return stop

    def emptyline(self):
        # do nothing on empty line (override cmd.Cmd behaviour which repeats last command)
        pass

    # -------------------------
    # built-in commands
    # -------------------------
    def do_ls(self, arg):
        """ls [path] — list files and directories in path (default: current directory)."""
        args = shlex.split(arg)
        path = _expand_path(args[0]) if args else "."
        try:
            entries = os.listdir(path)
            entries.sort()
            for name in entries:
                full = os.path.join(path, name)
                try:
                    mode = os.stat(full).st_mode
                    suffix = "/" if stat.S_ISDIR(mode) else ""
                except Exception:
                    suffix = ""
                print(name + suffix)
        except FileNotFoundError:
            print(f"ls: no such file or directory: {path}")
        except NotADirectoryError:
            print(f"ls: not a directory: {path}")
        except PermissionError:
            print(f"ls: permission denied: {path}")
        except Exception as e:
            print(f"ls: error: {e}")

    def complete_ls(self, text, line, begidx, endidx):
        return _list_matches(text)

    def do_cd(self, arg):
        """cd <path> — change current directory."""
        if not arg.strip():
            # go to home if no argument
            target = os.path.expanduser("~")
        else:
            (target,) = shlex.split(arg)
            target = _expand_path(target)
        try:
            os.chdir(target)
        except FileNotFoundError:
            print(f"cd: no such file or directory: {target}")
        except NotADirectoryError:
            print(f"cd: not a directory: {target}")
        except PermissionError:
            print(f"cd: permission denied: {target}")
        except Exception as e:
            print(f"cd: error: {e}")

    def complete_cd(self, text, line, begidx, endidx):
        return _list_matches(text)

    def do_pwd(self, arg):
        """pwd — print current working directory."""
        print(os.getcwd())

    def do_mkdir(self, arg):
        """mkdir [-p] <dirname> — create a directory. Use -p to create parent directories."""
        args = shlex.split(arg)
        if not args:
            print("usage: mkdir [-p] <dirname>")
            return
        p_flag = False
        if args[0] == "-p":
            p_flag = True
            args = args[1:]
            if not args:
                print("mkdir: missing directory name")
                return
        path = _expand_path(args[0])
        try:
            if p_flag:
                os.makedirs(path, exist_ok=True)
            else:
                os.mkdir(path)
        except FileExistsError:
            print("mkdir: cannot create directory: File exists")
        except Exception as e:
            print(f"mkdir: error: {e}")

    def complete_mkdir(self, text, line, begidx, endidx):
        return _list_matches(text)

    def do_rm(self, arg):
        """rm [-r] <path> — remove file. Use -r to remove directories recursively."""
        args = shlex.split(arg)
        if not args:
            print("usage: rm [-r] <path>")
            return
        r_flag = False
        if args[0] == "-r":
            r_flag = True
            args = args[1:]
            if not args:
                print("rm: missing path")
                return
        target = _expand_path(args[0])
        if _is_dir(target):
            if r_flag:
                try:
                    shutil.rmtree(target)
                    print(f"removed directory: {target}")
                except Exception as e:
                    print(f"rm: error removing directory: {e}")
            else:
                print("rm: cannot remove directory (use -r to remove directories)")
        else:
            try:
                os.remove(target)
            except FileNotFoundError:
                print(f"rm: no such file: {target}")
            except PermissionError:
                print(f"rm: permission denied: {target}")
            except IsADirectoryError:
                print(f"rm: is a directory: {target}")
            except Exception as e:
                print(f"rm: error: {e}")

    def complete_rm(self, text, line, begidx, endidx):
        return _list_matches(text)

    def do_cat(self, arg):
        """cat <filename> — display file contents."""
        args = shlex.split(arg)
        if not args:
            print("usage: cat <file>")
            return
        path = _expand_path(args[0])
        try:
            with open(path, "r", encoding="utf-8") as f:
                for line in f:
                    print(line, end="")
        except FileNotFoundError:
            print(f"cat: no such file: {path}")
        except IsADirectoryError:
            print(f"cat: {path}: Is a directory")
        except Exception as e:
            print(f"cat: error: {e}")

    def complete_cat(self, text, line, begidx, endidx):
        return _list_matches(text)

    def do_touch(self, arg):
        """touch <filename> — create an empty file or update modification time."""
        args = shlex.split(arg)
        if not args:
            print("usage: touch <file>")
            return
        path = _expand_path(args[0])
        try:
            Path(path).parent.mkdir(parents=True, exist_ok=True)
            Path(path).touch()
        except Exception as e:
            print(f"touch: error: {e}")

    def complete_touch(self, text, line, begidx, endidx):
        return _list_matches(text)

    def do_history(self, arg):
        """history — show the command history for this session."""
        for i, cmdline in enumerate(self.history[-200:], start=max(1, len(self.history)-199)):
            print(f"{i}: {cmdline}")

    # -------------------------
    # system & processes (psutil optional)
    # -------------------------
    def do_ps(self, arg):
        """ps — list running processes (if psutil installed), otherwise tries 'ps' or 'tasklist'."""
        if psutil:
            print(f"{'PID':>6}  {'Name':30} {'CPU%':>6} {'Mem%':>6}")
            for p in psutil.process_iter(["pid", "name", "cpu_percent", "memory_percent"]):
                try:
                    info = p.info
                    print(f"{info['pid']:6}  {info['name'][:30]:30} {info['cpu_percent']:6} {info['memory_percent']:.2f}")
                except Exception:
                    continue
        else:
            # fallback: system command
            if sys.platform.startswith("win"):
                subprocess.run(["tasklist"])
            else:
                subprocess.run(["ps", "aux"])

    def do_sys(self, arg):
        """sys — show CPU and memory usage (requires psutil)."""
        if not psutil:
            print("sys: psutil not installed. Install with `pip install psutil` to get system metrics.")
            return
        try:
            cpu = psutil.cpu_percent(interval=0.3)
            mem = psutil.virtual_memory()
            print(f"CPU usage: {cpu}%")
            print(f"Memory: {mem.percent}% used — {round(mem.used/1024/1024,1)}MB used / {round(mem.total/1024/1024,1)}MB total")
        except Exception as e:
            print(f"sys: error: {e}")

    # -------------------------
    # run shell commands
    # -------------------------
    def do_shell(self, arg):
        """shell <command> — run an external shell command."""
        if not arg.strip():
            print("usage: shell <command>")
            return
        try:
            subprocess.run(arg, shell=True)
        except Exception as e:
            print(f"shell: error: {e}")

    def default(self, line: str):
        """
        If a command isn't recognized as a built-in, try to run it in the shell.
        Also supports lines starting with "!" to run shell commands: e.g. !echo hi
        """
        if line.startswith("!"):
            cmd = line[1:].strip()
            if cmd:
                try:
                    subprocess.run(cmd, shell=True)
                except Exception as e:
                    print(f"shell: error: {e}")
            return

        # try running as external program
        try:
            parts = shlex.split(line)
        except Exception:
            parts = [line]
        try:
            subprocess.run(parts)
        except FileNotFoundError:
            print(f"command not found: {line}")
        except Exception as e:
            print(f"error running command: {e}")

    # -------------------------
    # completion for commands that accept paths by delegating to _list_matches
    # (already added above individually for many commands)
    # -------------------------

    # -------------------------
    # exiting
    # -------------------------
    def do_exit(self, arg):
        """exit — exit the terminal."""
        print("Bye.")
        return True

    def do_EOF(self, arg):
        """Ctrl-D / EOF — exit."""
        print("Bye.")
        return True


def main():
    term = PyTerminal()
    try:
        term.cmdloop()
    except KeyboardInterrupt:
        print("\nKeyboardInterrupt — exiting.")
    finally:
        # try to save history persistently
        if readline:
            try:
                readline.write_history_file(HISTORY_FILE)
            except Exception:
                pass


if __name__ == "__main__":
    main()
