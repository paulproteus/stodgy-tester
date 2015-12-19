## stodgy-tester

If you're writing code whose behavior changes based on Linux distribution details, such as kernel
version or `nsswitch.conf` details or libc version, then you need stodgy-tester so you can write
tests.

stodgy-tester is not fazed by having to operate at many levels of abstraction at once.

### Origin

stodgy-tester originated as a tool to test the [Sandstorm.io](https://sandstorm.io/) install
script. Sandstorm is Linux-based server software that runs on a variety of Linux distributions.

Here are some details about the install script to give you a sense of it. It will:

- Accept interactive input to choose between different install modes.

- Detect if your Linux kernel is too old to run Sandstorm, and print a message.

- Test if your Linux kernel has the right `/sys` features enabled, and enable them if the user
  consents.

- Provision a dynamic DNS domain that points at the server in question.

Here are some actual bugs we've had to fix in the install script:

- When checking if a port is open, we'd use a syntax for `nmap` that works on Debian but not Fedora.

- If the user's `/etc/hosts` does not contain an entry for the system's hostname, the install script
  would fail with an obscure error mesasge.

- When checking if the system has unprivileged user namespaces available, we run a 64-bit binary, which
  would fail with an obscure error message if your system is a 32-bit system.

I didn't want to maintain a big build farm with each Linux distribution, so I wrote scripts to use
Vagrant to define virtual machines on which to run the tests, and used `qemu` plus `libvirt` so that
I could run those tests on any regular cloud VM as part of our automated test process.

This project captures that approach and generalizes it, so you can enjoy this level of testing.

### How to use the software

An overview:

- Install `stodgy-tests`.

- `cd` into a directory containing `*.t` files and a `Vagrantfile`. Then run:

- `stodgy-tests`

You'll probably need to do something involving plugins to actually get the tests to run, though.

### Installation instructions

To install this from git, run:

```
git clone https://github.com/paulproteus/stodgy-tester.git
cd stodgy-tester
pip install --user --editable .
```

One day it'll be installable from PyPI, but it's not yet.

### Copyright & license

This program is (C) Sandstorm Development Group, Inc. Re-use permitted under the terms of Apache
License 2.0.

### Common problems

A quick bullet things of things to know:

- This program assumes that you have `cd`'d to the directory containing the `*.t` files and the
  `Vagrantfile`.
