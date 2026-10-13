---
name: nixos-vm-workflow
description: Modify and validate NixOS or Home Manager configurations using disposable QEMU VMs. Use when building a development VM, testing configuration changes before a host switch, or debugging guest provisioning, login, desktop sessions, and services.
---

# NixOS VM workflow

Turn configuration changes into observable guest behavior through an edit → build → start → verify cycle. A successful build proves evaluation and compilation; it does not prove provisioning, login, or a working session.

## Establish the baseline

Inspect repository instructions, the dirty working tree, entry points, channel/flake inputs, host profiles, hardware configuration, and Home Manager integration. Preserve user changes. Keep the user's branch and commit/push expectations explicit; a VM test does not authorize switching the physical host.

Use the project's existing Nixpkgs/Home Manager versions. Resolve uncertain options against their installed module sources and current upstream documentation. Do not retrofit flakes, change the desktop, or replace hardware configuration merely to make testing convenient.

## Make the configuration usable as a VM

These are design questions, not a universal configuration template. Research the actual modules and iterate from evaluation errors and guest logs.

- Keep development credentials, virtual hardware, resource limits, provisioning, and test networking in `virtualisation.vmVariant` or the project's equivalent VM entry point. Evaluate the physical-host configuration separately to check that overrides stayed gated. Treat `build-vm-with-bootloader` as a separate target and inspect its variant behavior for the installed release.
- A normal account and its password database are not a provisioned home. Ensure the guest user exists, has a usable home and authentication method, and receives the required Home Manager files. Integrating Home Manager into the guest can retain standalone Home Manager on the host. Provision before the greeter when the session depends on those files.
- Enable the intended system desktop/session integration and its Home Manager configuration together. Account for session packages, portals, PAM for the locker, audio, runtime utilities, fonts, and session-bound user services as required by that desktop.
- Separate physical-machine assumptions from guest behavior: disks, storage drivers, GPU-specific services, hardware tuning, secrets, SSH key loading, large inference workloads, and external home-directory symlinks. Preserve unrelated features that work in the VM.
- Select virtual GPU/display capabilities appropriate to the compositor. Some Wayland desktops require OpenGL/VirGL; a serial console or `-display none` does not establish a working graphical session. Choose resources sufficient to exercise the intended workload.
- Decide how to control and inspect the guest: SSH for ordinary commands, QMP for lifecycle and input, a guest agent if useful, serial logs for boot/failure evidence, and actual screenshots/input for desktop validation. See [headless-ssh.md](references/headless-ssh.md) for declarative public-key access.

## Edit, build, start, verify

1. Define the behavior to prove before editing. Include the regression trigger and observable success/failure, such as a fresh-disk login or locking before sleep.
2. Make a focused change. Build the repository's VM target, for example:

   ```sh
   nixos-rebuild build-vm -I nixos-config=./system/configuration.nix
   # Flake projects may instead use:
   nixos-rebuild build-vm --flake .#host
   ```

   Flake Git snapshots may omit untracked modules; check the inputs actually evaluated. Never substitute a host `switch` for a VM build. Inspect the generated runner to find its paths and runtime options.
3. Start the built runner with a test-owned disk and artifact directory. Use `NIX_DISK_IMAGE` to select a fresh qcow2 for provisioning checks; retain a persistent disk only when testing upgrades or retained state. Record the runner/store path, PID, logs, and control sockets. Do not overwrite a user's existing VM disk.
4. Poll a meaningful readiness condition with a deadline. A running QEMU process or visible greeter is insufficient. Establish SSH/agent access, provisioning success, and relevant services. A fresh guest may need time to render after its processes start.
5. Verify the behavior at the correct boundary. For desktops, log in through the actual greeter and inspect the selected session. Exercise input, an application, required services, and logout/session cleanup. For a service change, check its observable result, not just its installed package or unit text. Inspect failed system and user units separately.
6. For sleep changes, verify both lock ordering and actual suspend/resume. QMP must wake a suspended guest; its SSH/agent cannot respond while asleep. Keep emulator resume failures distinct from lock/provisioning regressions. A mocked sleep boundary is useful evidence but does not pass a real resume test.
7. Collect evidence on failure, stop the test-owned VM, then refine the smallest relevant change and repeat the checks affected by it. Use timeouts, TERM then KILL when needed, and reap the process. Avoid broad `pkill qemu` commands that could terminate unrelated VMs.
8. Finish with the diff, validation results, limitations, and requested commit/push. Report failed checks explicitly; do not call a suite fully passed when it skipped a required path. Do not repeat successful broad checks unless a new change or unresolved failure justifies it.

Read [control-and-debug.md](references/control-and-debug.md) when automating QMP/agent access, validating a desktop on a headless host, or diagnosing a hung guest. Its helper is available as [vm_control.py](scripts/vm_control.py).

## Authoritative starting points

- [NixOS VM module](https://github.com/NixOS/nixpkgs/blob/master/nixos/modules/virtualisation/qemu-vm.nix) and [VM variants](https://github.com/NixOS/nixpkgs/blob/master/nixos/modules/virtualisation/build-vm.nix); prefer the corresponding sources in the project's pinned release.
- [NixOS VM tutorial](https://nix.dev/tutorials/nixos/nixos-configuration-on-vm.html).
- [QEMU monitor protocol](https://www.qemu.org/docs/master/interop/qmp-intro.html) and [guest-agent protocol](https://www.qemu.org/docs/master/interop/qemu-ga-ref.html).
