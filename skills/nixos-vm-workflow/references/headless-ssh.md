# Declarative guest SSH access

Use the guest account's NixOS `openssh.authorizedKeys.keys` for public-key strings or `openssh.authorizedKeys.keyFiles` for files read during evaluation/build. NixOS generates `/etc/ssh/authorized_keys.d/<user>` and configures sshd to read it; do not expect these declarations to populate `~/.ssh/authorized_keys`.

Illustrative VM-only module; adapt username, paths, existing settings, and host port:

```nix
virtualisation.vmVariant = {
  services.openssh = {
    enable = true;
    openFirewall = true;
    settings.PasswordAuthentication = false;
    settings.KbdInteractiveAuthentication = false;
  };
  users.users.alice.openssh.authorizedKeys.keyFiles = [
    "/absolute/host/path/to/id_ed25519.pub"
  ];
  virtualisation.forwardPorts = [ {
    from = "host";
    host.address = "127.0.0.1";
    host.port = 2222;
    guest.port = 22;
  } ];
};
```

Public keys may enter the Nix store; private keys stay on the host. A rebuild updates the declarative authorization even with an existing guest disk. Do not copy private keys, agent sockets, or the host's whole home into the guest to enable access.

An explicit module option for a list of public-key paths or strings is usually cleaner than silently guessing a key. If local development defaults to an existing `~/.ssh/id_ed25519.pub`, resolve the absolute host path, document the fallback when absent, and allow an override. Do not choose an SSH server host key instead of the user's client key. Public files may exist without a usable signing identity in the agent.

External home-directory paths work in channel/impure builds. Pure flake evaluation needs public-key data included in its inputs, for example a tracked `.pub` file or a public-key string. Do not change the entire project to impure evaluation merely to locate a key.

For a fresh disposable VM, use a test-specific known-hosts file:

```sh
ssh -o BatchMode=yes -o StrictHostKeyChecking=accept-new \
  -o UserKnownHostsFile="$artifacts/known_hosts" \
  -p 2222 alice@127.0.0.1 'id; systemctl --failed --no-legend'
```

Retain host-key checking; remove only the test-owned known-hosts file when intentionally replacing that VM with a new identity. Prefer an explicit identity when the agent offers many keys. Passwordless remote execution does not imply passwordless sudo; respect the guest's policy and do not silently broaden it.

SSH can inspect a GUI session without creating one. To run user-service commands from a root/agent shell, switch to the intended user and supply that user's runtime directory and bus address. Derive the UID in the guest. Starting a compositor in an SSH shell may bypass the greeter/session integration under test.

A headless services-only VM can use `-display none`. A GL desktop may need `egl-headless` or Xvfb with an SDL/GTK GL frontend and software host rendering. Verify the selected backend actually starts; SSH access by itself proves neither graphical rendering nor login. See [control-and-debug.md](control-and-debug.md).

Sources: [NixOS sshd module](https://github.com/NixOS/nixpkgs/blob/master/nixos/modules/services/networking/ssh/sshd.nix), [SSH key configuration](https://wiki.nixos.org/wiki/SSH_public_key_authentication), and [QEMU VM port forwarding](https://github.com/NixOS/nixpkgs/blob/master/nixos/modules/virtualisation/qemu-vm.nix).
