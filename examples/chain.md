---
name: bonfire-bass-rust-port
description: Sequential migration of Bonfire Bass DSP from C++ to Rust. Each step has its own contract and must pass the judge before the next starts.
---

1. port-dsp-core-to-rust
2. wire-up-ffi-shim
3. swap-cpp-for-rust-in-host
4. delete-cpp-tree
