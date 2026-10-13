# Guest control and evidence

## Launch and cleanup

Use a private test artifact directory. Pass QEMU options through the runner's arguments or its supported environment variables after inspecting it. A useful setup has serial output and a QMP socket:

```sh
artifacts=$(mktemp -d)
NIX_DISK_IMAGE="$artifacts/disk.qcow2" ./result/bin/run-host-vm \
  -serial "file:$artifacts/serial.log" \
  -qmp "unix:$artifacts/qmp,server=on,wait=off" \
  >"$artifacts/qemu.log" 2>&1 &
vm_pid=$!
```

Record that PID and supervise it for the whole test. On failure, capture available evidence before sending TERM; if it does not exit by a short deadline, send KILL and wait/reap it. A suspended guest may be healthy but unable to answer until QMP wakes it. Stop only the VM created for this run.

For a headless host running a graphical desktop, investigate an EGL frontend first if the package and render device support it. Xvfb with `LIBGL_ALWAYS_SOFTWARE=1 GALLIUM_DRIVER=llvmpipe` and an SDL GL frontend is another workable approach. These variables select software rendering on the host; the guest still needs its virtual GL device. Do not universally disable the guest GPU to fix a cursor or screenshot issue.

## QMP and guest agent

Use QMP rather than reconnecting to the human monitor for each keyboard event. Consume the greeting, issue `qmp_capabilities`, assign request IDs, and ignore asynchronous events until the matching response arrives. `human-monitor-command` can issue `sendkey`, `info status`, and supported diagnostics; direct QMP `query-status` and `system_wakeup` are useful for sleep tests.

The bundled stdlib-only helper supports both protocols:

```sh
python3 scripts/vm_control.py qmp --socket "$artifacts/qmp" \
  --execute query-status
python3 scripts/vm_control.py qmp --socket "$artifacts/qmp" \
  --execute human-monitor-command --arguments '{"command-line":"sendkey meta_l-ret"}'
python3 scripts/vm_control.py qmp --socket "$artifacts/qmp" \
  --execute system_wakeup
```

If SSH is unsuitable, attach a virtio guest-agent channel and ensure the guest service is enabled. Inspect existing devices first to avoid duplicating the controller/channel:

```text
-device virtio-serial
-chardev socket,path=.../agent,server=on,wait=off,id=qga
-device virtserialport,chardev=qga,name=org.qemu.guest_agent.0
```

QGA clients must synchronize before commands, especially after timeouts or resume. Use `guest-sync-delimited`, a unique integer, and the `0xff` delimiter to discard stale/incomplete replies. `guest-exec` returns a PID, not the exit status; poll `guest-exec-status` and decode captured base64 output. The agent normally runs commands as root, so choose a user context deliberately.

```sh
python3 scripts/vm_control.py guest-exec --socket "$artifacts/agent" \
  --command 'systemctl status home-manager-alice greetd --no-pager' --timeout 30
```

Do not wait for a guest command's completion after it has already suspended the VM. Schedule sleep a short time ahead, observe QMP's suspended state, wake with QMP, then reconnect/synchronize and verify the session remains locked. For a locker using swayidle, inspect the sleep inhibitor and confirm command readiness semantics (`-w` plus a locker that reports successful lock before daemonizing).

## Desktop evidence

Check the selected greeter session and actual user login. An account can authenticate successfully yet enter a shell or an unintended session. Fresh greeters may have no remembered selection; inspect their documented configuration/state instead of assuming a default.

Use compositor IPC and real keybindings to verify windows, launcher, lock/unlock, and logout. Query the configured Mod key; host shortcuts may intercept Super, so use the frontend's grab or an explicitly scoped guest mapping. Match wrapped process names carefully and prefer compositor window IDs/application IDs over a fragile exact-name `pgrep`.

Check user units independently: `systemctl is-active a b` succeeds when any listed unit is active. A shell conjunction or separate assertions proves each unit. On logout, verify session-bound services actually stop.

For screenshots, prefer compositor facilities for the desktop and a host-display capture for the greeter. QEMU GL scanouts may reject `screendump` with "no surface". A host framebuffer screenshot may omit a hardware cursor; inspect/capture the cursor separately if its shape is the issue. Never assume a black screenshot means the guest failed without another readiness check.

## Failure isolation

Separate build/evaluation, home activation, greeter/session selection, compositor startup, rendering/input, service behavior, and emulator resume. Read logs at the failing boundary. Apply a narrow workaround only after checking the installed version supports it; for example, some wlroots/VirGL combinations need a software cursor specifically in the greeter. Greeter children may not inherit the greetd service environment, so verify the actual child environment when testing such settings.

For a hung guest, keep QMP state, serial/kernel logs, and a host screenshot. Debug-only guest kernel verbosity or SysRq blocked-task dumps can distinguish a guest kernel/filesystem deadlock from a stalled SSH/agent protocol. Scope such instrumentation to the test. A host process remaining alive is not evidence of guest health.

One observed S3 failure blocked PID 1 and new commands in `p9_client_rpc` after wake because the development VM shared `/nix/store` over 9P. `virtualisation.useNixStoreImage` provides a local-store alternative, at additional disk and startup cost. Investigate this when traces implicate 9P; do not apply it universally or blame every resume failure on the GPU. The installed VM module is the source of truth for image creation and mount behavior.

A successful mock of the sleep boundary proves lock ordering only. Record real suspend/resume failures separately and keep their logs even if other tests pass.
