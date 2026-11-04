# Lean→Rust interop and template requirements

Context: [GitHub issue #4 — Исследовать Lean→Rust interop и требования к шаблону](https://github.com/guility/eOCR/issues/4)  
Research checked: 2026-11-04.

## Update: third-party Lean-to-Rust generators

Follow-up checked 2026-11-04, after the original report. The finding above is about Lean's documented native compiler/FFI; it should not be read as saying that no third-party Lean-to-Rust generator exists.

- **Lungo** compiles Lean projects through Lean's compiler IR and emits Rust modules backed by a Rust port of the Lean runtime. Its trust documentation includes the Lean toolchain, worker adapter, Rust/C backends, facade conversions, runtime primitives, and host facilities in the trusted base. It validates Bridge IR and differentially tests output against Lean's native backend, but explicitly states this is not a proof of the backend. It is a candidate for template and disposable prototype work, not a verified production proof chain. ([Lungo README](https://github.com/machinefabric/lungo-rs), [architecture](https://machinefabric.com/lungo/docs/explanation/architecture), [trust and verification](https://machinefabric.com/lungo/docs/explanation/trust-and-verification))
- **Peregrine** supports a Lean frontend and a Rust backend, but its published backend table marks Rust unverified. The Lean frontend is partially verified and lacks IO, Task, primitive arrays, and primitive floats; the documented pipeline does not target GPU kernels. ([backend assurance matrix](https://github.com/peregrine-project/peregrine-tool/blob/master/doc/backends.md), [Lean frontend limitations](https://github.com/peregrine-project/peregrine-tool/blob/master/doc/frontends.md))

**Effect on the report:** there is still no official Lean Rust target, but direct third-party Lean-to-Rust code generation is available. Neither surveyed project meets eOCR's requested proof perimeter for the Rust runtime and GPU kernels. The choice between a conventional C-ABI template and a Lungo-based experimental template remains open under [issue #15](https://github.com/guility/eOCR/issues/15); neither option should be presented as satisfying the full proof requirement without an additional verified chain.

## Findings

- **There is no documented direct Lean→Rust code-generation target.** The Lean reference says the compiler translates Lean IR into C, producing one C file per module, then compiles that C to native code. The documented native interop path is the platform C ABI. I found no official Rust backend/target in the Lean build documentation. Treat Rust as a C-ABI caller or implementation, not as generated Lean output. [Lean compilation](https://lean-lang.org/doc/reference/latest/Elaboration-and-Compilation/) · [Lean FFI](https://lean-lang.org/doc/reference/latest/Run-Time-Code/Foreign-Function-Interface/)

- **Both call directions are available through C ABI.** In Lean, @[extern "sym"] binds a declaration to a foreign symbol (Lean calls Rust/C); @[export sym] exports a Lean declaration for a foreign caller (Rust calls Lean). The FFI reference explicitly says this interface is intended for internal use and is unstable, and compound C structs cannot currently be passed or returned by value. [Lean FFI](https://lean-lang.org/doc/reference/latest/Run-Time-Code/Foreign-Function-Interface/)

- **The ABI is Lean-runtime-specific for many values.** Fixed-width UInt types, Char, and Float map to C scalars. Nat, Int, and most inductive values use Lean runtime objects or representation-specific values. An extern parameter of lean_object* is owned by default; external code must consume or decrement it exactly once. Borrowed parameters use @& and have different rules; exports and returns are owned under the current ABI. The interface also requires calling module initializers before use; non-Lean-created threads require Lean thread initialization/finalization, and task-using code may need the task manager. [Lean FFI: ABI, borrowing, initialization](https://lean-lang.org/doc/reference/latest/Run-Time-Code/Foreign-Function-Interface/)

- **Lake can produce native libraries, but Cargo does not make Lean ABI details safe.** Lake exposes static and shared library facets for Lean libraries; Cargo build scripts can supply native link-search and link-library instructions. Rust declarations in unsafe extern blocks are unchecked imports, and a wrong signature or ownership rule can cause undefined behavior. Use a narrow Rust sys layer for raw ABI and wrap it in safe Rust APIs; for nontrivial Lean objects, prefer a small C shim that converts to a narrow scalar/opaque-handle API. Plan runtime library discovery/packaging as part of the target-platform contract. [Lake library facets](https://lean-lang.org/doc/reference/latest/Build-Tools-and-Distribution/Lake/) · [Cargo build scripts](https://doc.rust-lang.org/cargo/reference/build-scripts.html) · [Rust external blocks](https://doc.rust-lang.org/reference/items/external-blocks.html)

- **Proofs do not execute as runtime checks.** Lean propositions are erased from compiled code. The kernel checks the proof term against the theorem, but a theorem does not by itself validate a foreign implementation or make its result satisfy the specification at runtime. Lean explicitly permits runtime replacement through FFI or unsafe implementations while keeping the checked logical declaration; this preserves logical soundness but makes runtime behavior a separate trust boundary. Keep computational API data in runtime-relevant types and document which Rust/C code is trusted to implement the proved specification. [Propositions and erasure](https://lean-lang.org/doc/reference/latest/The-Type-System/Propositions/) · [runtime replacement and unsafe code](https://lean-lang.org/doc/reference/latest/Definitions/Recursive-Definitions/) · [proof validation and axioms](https://lean-lang.org/doc/reference/latest/ValidatingProofs/)

## Version and compatibility requirements

- On the research date, Lean’s release page lists **v4.35.0** as the latest stable release and **v4.36.0-rc2** as a prerelease. Lean’s own release policy says there is not yet a strong backwards-compatibility guarantee. The FFI is separately marked unstable. Pin an exact stable Lean toolchain in lean-toolchain, commit lake-manifest.json, build all Lean and native artifacts with that same toolchain, and revalidate/rebuild on upgrades. v4.35.0 is a research-time candidate baseline, not an eOCR support decision. [Lean releases](https://github.com/leanprover/lean4/releases) · [Lean compatibility note](https://github.com/leanprover/lean4/blob/master/RELEASES.md) · [Elan toolchain files](https://lean-lang.org/doc/reference/latest/Build-Tools-and-Distribution/Managing-Toolchains-with-Elan/)

- Rust’s release page lists **1.99.1** as current on the research date. This is not an interop-mandated version. Set a tested MSRV in Cargo.toml’s rust-version field and commit Cargo.lock; optionally pin the development toolchain for reproducible builds. [Rust releases](https://github.com/rust-lang/rust/releases) · [Cargo rust-version](https://doc.rust-lang.org/cargo/reference/rust-version.html)

## Suggested package shape

The sibling repository currently has branches and tags for Python, Node.js, Rust, Go, and C#, but no Lean branch/package. Its policy requires one long-lived language branch, a language-specific root AGENTS.md plus component template under template/, and immutable annotated tags named <language>/v<major>.<minor>.<patch>. Therefore Lean would require adding lean to the sibling repository’s allowed language/branch index before publishing a Lean package. Keep that package’s content on its Lean branch and tags, not the default branch. [agents-template-langs README](https://github.com/guility/agents-template-langs/blob/main/README.md) · [repository rules](https://github.com/guility/agents-template-langs/blob/main/AGENTS.md)

A compact integration template could use:

- Root of the language branch: AGENTS.md and template/.
- template/: lean-toolchain, lakefile.toml, lake-manifest.json, and Lean/ modules for the executable definitions/specification/proofs and the small exported or extern boundary.
- template/rust/: Cargo.toml, Cargo.lock, build.rs, and src/ split into raw FFI declarations plus a safe wrapper.
- Build the Lean native library through Lake, then have Cargo’s build script link the artifacts and required Lean runtime libraries for the selected target. Keep generated C and binaries in ignored build directories.

The raw Rust layer should mirror the pinned Lean ABI exactly and contain the unsafe ownership/init operations. The safe wrapper should expose ordinary Rust types and prevent borrowed Lean pointers from escaping their valid scope. For the first template, a narrow scalar API or C shim is safer to maintain than exposing arbitrary Lean inductives.

This report records findings and a suggested layout only; it does not create a Lean package or choose its final support policy.


