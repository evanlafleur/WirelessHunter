# --- updater.py ---
# Software updates for the device: check GitHub for newer commits, list what
# changed, fast-forward the checkout, and restart. "Change notes" are the
# subject lines of the commits being pulled in, so write clear ones.
#
# The app runs as root (monitor mode needs it), but the checkout belongs to
# a normal user whose SSH keys / credential helper are what authenticate
# against a private repo - so git always runs as the checkout's owner.

import os
import pwd
import re
import shutil
import subprocess
import sys
import time

import config
import system

REPO = config.BASE_DIR
GIT_OPTS = ["GIT_TERMINAL_PROMPT=0", "GIT_SSH_COMMAND=ssh -o BatchMode=yes -o ConnectTimeout=15"]

_NETWORK_ERRORS = re.compile(r"resolve host|unable to access|network is unreachable|timed out|"
                             r"connection (refused|reset)|could not connect|temporary failure", re.I)
_AUTH_ERRORS = re.compile(r"authentication|could not read (username|password)|permission denied|"
                          r"repository not found|403|401", re.I)

def _owner():
    try:
        return pwd.getpwuid(os.stat(REPO).st_uid)
    except (KeyError, OSError):
        return None

def _command(args):
    """argv for running `args` with prompts disabled, as the checkout's owner when we're root."""
    owner = _owner()
    if os.geteuid() == 0 and owner is not None and owner.pw_uid != 0:
        return ["runuser", "-u", owner.pw_name, "--", "env", f"HOME={owner.pw_dir}", *GIT_OPTS, *args]
    return ["env", *GIT_OPTS, *args]

def git(*args, timeout=60):
    """Returns (returncode, stdout, stderr), stripped."""
    rc, out, err = system.run(_command(["git", "-C", REPO, *args]), timeout=timeout)
    return rc, out.strip(), err.strip()

def _problem(out, err, default):
    text = (err or out or "").strip()
    last = text.splitlines()[-1] if text else default
    if _AUTH_ERRORS.search(text):   # checked first: a 403 also says "unable to access"
        owner = _owner()
        who = f" for {owner.pw_name}" if owner else ""
        return f"GitHub refused access - git credentials{who} aren't set up on this device."
    if _NETWORK_ERRORS.search(text):
        return "Can't reach GitHub - check the Wi-Fi connection in Settings."
    return last

def read_version():
    try:
        with open(os.path.join(REPO, "VERSION")) as f:
            return f.read().strip() or "unknown"
    except OSError:
        return "unknown"

def current_info():
    rc, commit, err = git("rev-parse", "--short", "HEAD")
    if rc != 0:
        raise RuntimeError("This copy isn't a git checkout, so it can't update itself.")
    return {
        "version": read_version(),
        "commit": commit,
        "date": git("log", "-1", "--format=%cs")[1],
        "branch": git("rev-parse", "--abbrev-ref", "HEAD")[1],
    }

def _upstream(branch):
    rc, ref, _ = git("rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}")
    return ref if rc == 0 and ref else f"origin/{branch}"

def check():
    """Fetches and compares with GitHub. Raises RuntimeError with a message
    fit for the screen. Returns {current, upstream, behind, ahead, notes,
    latest_version, latest_commit, dirty} where notes is a list of
    (short hash, subject, date), newest first."""
    info = current_info()
    rc, out, err = git("fetch", "--quiet", "origin", timeout=90)
    if rc != 0:
        raise RuntimeError(_problem(out, err, "fetch failed"))
    upstream = _upstream(info["branch"])
    if git("rev-parse", "--verify", "--quiet", upstream)[0] != 0:
        raise RuntimeError(f"Nothing to compare with: {upstream} doesn't exist on GitHub.")
    behind = int(git("rev-list", "--count", f"HEAD..{upstream}")[1] or 0)
    ahead = int(git("rev-list", "--count", f"{upstream}..HEAD")[1] or 0)
    notes = []
    if behind:
        _, log, _ = git("log", f"HEAD..{upstream}", "--max-count=40", "--format=%h%x1f%s%x1f%cs")
        for line in log.splitlines():
            parts = line.split("\x1f")
            if len(parts) == 3:
                notes.append(tuple(parts))
    rc, latest_version, _ = git("show", f"{upstream}:VERSION")
    return {
        "current": info,
        "upstream": upstream,
        "behind": behind,
        "ahead": ahead,
        "notes": notes,
        "latest_version": latest_version if rc == 0 and latest_version else None,
        "latest_commit": git("rev-parse", "--short", upstream)[1],
        "dirty": bool(git("status", "--porcelain", "--untracked-files=no")[1]),
    }

def apply_update():
    """Fast-forwards the checkout to GitHub's latest, reinstalling Python
    requirements if they changed. Returns (ok, message). Never rewrites or
    discards local work: a diverged or conflicting checkout just fails."""
    info = current_info()
    rc, out, err = git("fetch", "--quiet", "origin", timeout=90)
    if rc != 0:
        return False, _problem(out, err, "fetch failed")
    upstream = _upstream(info["branch"])
    old = git("rev-parse", "HEAD")[1]
    rc, out, err = git("merge", "--ff-only", upstream, timeout=120)
    if rc != 0:
        text = (err or out)
        if "overwritten" in text or "local changes" in text.lower():
            return False, "Local edits on this device conflict with the update."
        if "fast-forward" in text.lower() or "diverge" in text.lower():
            return False, "This copy has its own commits, so it can't fast-forward."
        return False, _problem(out, err, "update failed")
    new = git("rev-parse", "HEAD")[1]
    if new == old:
        return True, "Already up to date."
    changed = git("diff", "--name-only", old, new)[1].splitlines()
    if "requirements.txt" in changed:
        rc, out, err = system.run(_command([sys.executable, "-m", "pip", "install", "-q", "-r",
                                            os.path.join(REPO, "requirements.txt")]), timeout=900)
        if rc != 0:
            return False, "Updated, but installing new dependencies failed: " + _problem(out, err, "pip error")
    return True, "Update installed."

def restart_process():
    """Restarts the app so new code is loaded. Under systemd that means
    asking systemd to restart the service (it will SIGTERM us); otherwise
    the process replaces itself. The caller should already have released the
    display and stopped capture."""
    if os.environ.get("INVOCATION_ID") and shutil.which("systemctl"):
        subprocess.Popen(["systemctl", "restart", config.SERVICE_NAME], start_new_session=True)
        time.sleep(30)      # systemd stops us well before this returns
        os._exit(1)         # ...but if it didn't, exit non-zero so Restart=on-failure kicks in
    os.execv(sys.executable, [sys.executable] + sys.argv)
