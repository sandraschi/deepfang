# Docker on Windows: Why It's Flaky and What to Do About It

## Root Cause

Docker Desktop on Windows runs `dockerd` inside a hidden WSL2 distro
(`docker-desktop`). The Windows side talks to it over a named pipe
(`npipe:////./pipe/dockerDesktopLinuxEngine`). This bridge layer is the
primary failure vector:

- Sleep/hibernate severs the pipe, and the reconnection logic is unreliable.
- WSL kernel updates (via Windows Update) silently break the integration.
- `vmmemWSL` memory ballooning causes OOM kills of the docker-desktop distro.
- `com.docker.backend.exe` sometimes starts but never creates the pipe.

None of these are Docker Desktop bugs per se. They're WSL2 integration bugs
that Microsoft and Docker have been playing hot-potato with for years.

## Recovery: `just docker-kill`

Three escalation tiers, tried in order:

```
just docker-kill
```

1. `wsl --terminate docker-desktop` -- kills just the Docker WSL distro,
   leaves your other WSL instances running. Fastest recovery.
2. `wsl --shutdown` -- kills all WSL distros. Slower but more thorough.
3. Triple kill: `Docker Desktop.exe`, `com.docker.backend.exe`, `vmmem`/`vmmemWSL`.

After tier 1 or 2, restart Docker Desktop. The engine usually recovers.

## Prevention

Add to `%USERPROFILE%\.wslconfig`:

```ini
[wsl2]
memory=8GB
processors=4
[experimental]
autoMemoryReclaim=true
```

Then `wsl --shutdown` and restart Docker Desktop. This caps the WSL2 VM
memory and enables automatic reclaim, preventing the OOM ballooning.

## Permanent Fix: Drop Docker Desktop

Docker Desktop is optional. You can run Docker Engine natively inside your
main WSL2 distro with zero GUI overhead and zero named pipe flakiness.

### Step 1: Install Docker Engine in WSL2

Open your WSL2 distro (Ubuntu) and run:

```bash
# Remove any old Docker packages
sudo apt remove docker docker-engine docker.io containerd runc

# Install Docker CE
sudo apt update
sudo apt install -y docker.io

# Start dockerd (needs to be done manually in WSL2)
sudo dockerd &
```

### Step 2: Verify from WSL2

```bash
docker info --format "{{.ServerVersion}}"
# Should print a version string, not an error
```

### Step 3: Expose to Windows

Edit `/etc/docker/daemon.json` inside WSL2:

```json
{
  "hosts": ["unix:///var/run/docker.sock", "tcp://0.0.0.0:2375"]
}
```

Then restart dockerd:

```bash
sudo killall dockerd
sudo dockerd &
```

### Step 4: Connect from Windows PowerShell

```powershell
$env:DOCKER_HOST = "tcp://localhost:2375"
docker info
```

Add the environment variable permanently:

```powershell
[System.Environment]::SetEnvironmentVariable("DOCKER_HOST", "tcp://localhost:2375", "User")
```

Now `docker` commands from PowerShell, CMD, or any tool talk directly to
the WSL2 daemon via TCP. No named pipe, no Desktop GUI, no bridge layer.

### Step 5: Auto-start dockerd in WSL2

Add to your WSL2 `~/.bashrc`:

```bash
# Start dockerd if not running
if ! pgrep -x dockerd > /dev/null; then
    sudo dockerd > /dev/null 2>&1 &
fi
```

### Step 6: Uninstall Docker Desktop (optional)

Once the WSL2-native Docker is stable:

```powershell
wsl --terminate docker-desktop
# Then uninstall Docker Desktop via Settings > Apps
```

## GUI for the WSL2-native setup

Once Docker runs natively in WSL2, you have several GUI options that don't
depend on the Docker Desktop bridge:

| Option | Type | How to use |
|--------|------|------------|
| **Portainer** | Web UI (containerized) | `docker run -d -p 9000:9000 -v /var/run/docker.sock:/var/run/docker.sock portainer/portainer` -- then open http://localhost:9000 |
| **Podman Desktop** | Native Windows app | Connects to any Docker socket including WSL2 TCP. More stable than Docker Desktop because it doesn't manage the daemon -- it's just a UI. |
| **VSCode Dev Containers** | IDE extension | Works with any Docker host. Zero GUI overhead if you're already in VSCode. |
| **LazyDocker** | Terminal UI | `docker run --rm -it -v /var/run/docker.sock:/var/run/docker.sock lazyteam/lazydocker` |

Of these, **Portainer** is the most common production choice -- it's a web app
so no Windows desktop app to crash, and it reconnects automatically if Docker
restarts.
