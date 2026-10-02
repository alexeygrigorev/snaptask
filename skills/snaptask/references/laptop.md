# Start a laptop session

Use the deployed service at [snaptask.dtcdev.click](https://snaptask.dtcdev.click). You need Git, Python 3.10 or newer, and your existing Codex installation on the laptop. The CLI uses Python's standard library.

Clone the repository and open it:

```bash
git clone https://github.com/alexeygrigorev/snaptask.git
cd snaptask
```

If you already cloned it, run `git pull --ff-only` from your checkout instead.

## Authenticate once on this laptop

Sign in on the web with the same approved Google account you use to capture photos. Open Connections, create an API token named `Laptop Codex`, and copy it.

Run the login command yourself in your laptop terminal and paste the token into the hidden prompt:

```bash
python3 cli/snaptask.py login
python3 cli/snaptask.py tasks list
```

The CLI stores credentials in `~/.config/snaptask/config.json` with permissions `0600`. If `XDG_CONFIG_HOME` is set, it stores them below that directory instead. Keep this file private and never paste its contents into chat. Every task belongs to the account that created it, so tokens from another account show a different inbox.

An empty `tasks` array means authentication worked and the account has no tasks yet. Capture a batch on your phone and tap Ready, then list tasks again. A 401 response means the token is invalid or revoked: create a new token and repeat login. A network error means you should check the laptop's connection and retry.

## Start Codex in the checkout

Open the checkout as a project in the Codex app, or launch your installed Codex CLI from its root:

```bash
codex
```

The checked-in `.agents/skills/snaptask` symlink points to `skills/snaptask`, so Codex can discover the skill in this project. This follows the [official skill discovery instructions](https://learn.chatgpt.com/docs/build-skills#where-codex-loads-local-skills).

For a first session, send:

```text
Use $snaptask to check my access and list available tasks. Wait for me to choose what to process.
```

To process one task, send:

```text
Use $snaptask to claim the next task as laptop-codex, download its photos, follow the task notes, and save outputs under work/<task-id>/. Renew the claim while working and mark it complete only when the requested work succeeds. Stop when there is no work.
```

If the skill is missing from the session, restart Codex after pulling the latest checkout. You can also ask it to read `skills/snaptask/SKILL.md` directly. Read that file for the claim, download, heartbeat, and completion commands.

## Work from another project

To make the skill discoverable from other checkouts, create a user-level symlink from the SnapTask checkout:

```bash
mkdir -p ~/.agents/skills
ln -s "$PWD/skills/snaptask" ~/.agents/skills/snaptask
```

If that destination already exists, look at it before changing it. Keep the SnapTask checkout at the same path so the symlink continues to work. The agent should resolve the skill's canonical location and use the CLI's absolute path while saving task outputs in your chosen project.
