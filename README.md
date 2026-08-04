# Baochip 1x — RTL Security Review

An independent security review of the [Baochip 1x](https://github.com/baochip/baochip-1x) secure
SoC RTL. Results are published openly.

> **"AI detected bugs are pretty much by definition not secret, and treating them on some
> private list is a waste of time for everybody involved."**
>
> — Linus Torvalds, LKML, May 2026, [as reported by The Register](https://www.theregister.com/security/2026/05/18/linus-torvalds-says-ai-powered-bug-hunters-have-made-linux-security-mailing-list-almost-entirely-unmanageable/5241633)

**117 findings, produced entirely by AI agents, published openly for exactly that reason.**
No human has verified any of them — [what that does and does not mean](#automated).

## What this chip is

The Baochip-1x is the silicon in the **DEF CON 34 badge** — roughly 27,000 of them — where it acts
as a hardware security token, password manager and HSM. It pairs a 350 MHz VexRiscv RISC-V core
with 4 MB of ReRAM, 2 MB of SRAM, and hardware secure elements including a key store and a true
random number generator, on TSMC's 22 nm process.

Its distinguishing claim is verifiability. The package is built for Infra-Red In-Situ (IRIS)
inspection, so an owner can non-destructively look at the die and check that the transistor
patterns match the published design — billed as the first production-scale silicon engineered for
that kind of end-user verification.

- [Wired — *The New Defcon Badges Pack a Unique Open Source Chip That Doubles as a Security Key*](https://www.wired.com/story/defcon-34-badge-baochip-andrew-bunnie-huang/)
- [Hackster.io — *The DEF CON 34 Badge Packs a Surprise: Andrew "bunnie" Huang's "Mostly-Open" Baochip-x1*](https://www.hackster.io/news/the-def-con-34-badge-packs-a-surprise-andrew-bunnie-huang-s-mostly-open-baochip-x1-1e03307d4797)
- [TechTimes — *DEF CON 34 Badge Features First Verifiable Open-Source Silicon at Production Scale*](https://www.techtimes.com/articles/322671/20260802/def-con-34-badge-features-first-verifiable-open-source-silicon-production-scale.htm)

That openness is the precondition for this review: checking that the silicon matches the published
RTL only matters if someone also reads the RTL. This is a machine-assisted attempt at the second
half.

## Source under review

| | |
|---|---|
| Repository | <https://github.com/baochip/baochip-1x> |
| Commit reviewed | [`1be12f4`](https://github.com/baochip/baochip-1x/commit/1be12f4d57aa9e5fdc4884adbd319cafa887d28b) — *Merge pull request #22 from baochip/zmmul* |
| Source tree at that commit | <https://github.com/baochip/baochip-1x/tree/1be12f4d57aa9e5fdc4884adbd319cafa887d28b> |
| Commit date | 2026-06-18 |
| Review dates | 2026-07-31 → 2026-08-04 |

Every `file.sv:line` reference in the findings is relative to the repository root at that commit, and
resolves against the source tree linked above — for example
[`rtl/modules/rrc/rtl/rrc.sv#L360`](https://github.com/baochip/baochip-1x/blob/1be12f4d57aa9e5fdc4884adbd319cafa887d28b/rtl/modules/rrc/rtl/rrc.sv#L360)
is BAO-001. The pinned SHA is also in `reviewed-commit.txt`.

The subject device is taped out and, per the upstream README, "fixed and unpatchable." Every finding
therefore splits its mitigation into an RTL fix for a future die revision and, separately, what
firmware can do on existing silicon. **For many findings the honest answer is that no software
mitigation exists**; those say so explicitly.

<a id="automated"></a>

## ⚠️ Fully automated — no human has verified any of this

**Every finding in this repository was produced by AI agents. No human has read, reviewed,
confirmed, or reproduced any finding, any piece of evidence, or any severity rating.**

- All 117 findings were generated, verified and adversarially tested entirely by language models.
- The "independent verification" and "adversarial refutation" described under Method are
  model-versus-model processes. They measurably reduce error — the critical count fell from 9 to 1
  under that filtering — but they do not eliminate it, and they are **not** a substitute for human
  review.
- Nothing has been simulated, synthesised, or tested on silicon.
- Where this repository says a finding was "read against the RTL directly during assembly," that
  refers to work done by the orchestrating model, not by a person.

Treat this as a machine-generated lead list for human triage, not as a verified vulnerability
report. Findings are likely to include false positives, and the severity ratings are model
judgements that have not been calibrated by anyone.

### What this cost

The entire review was produced with **under $200 of AI credits** — no specialised tooling, no
commercial EDA licences, no simulator, no lab equipment, no silicon. The only inputs were the
open-source RTL in the upstream public repository, `grep`, and a text editor.

136 agent invocations, roughly 36 MB of agent transcripts, a few hours of wall-clock time.

The point is not that the tooling is impressive. The point is that **the barrier to producing a
document like this has collapsed**: anyone with $200 and the patience to orchestrate it can now
point a fleet of agents at a public RTL repository and get 117 evidence-backed leads out the far
end. That cuts both ways for a security-critical open-source chip, and it is worth stating plainly
alongside the findings.

## Read this first

**[`baochip-1x-security-review-full.md`](baochip-1x-security-review-full.md)** — the complete report.
117 findings with evidence, §§1–7, and Appendix A.

## Limitations

Stated plainly and up front, because this is published in the open — a write-up that overclaims
is worse than one that finds less.

- **Static source review only.** No simulation, formal verification, synthesis, netlist review, or
  silicon testing. **No finding here has been demonstrated on hardware.**
- **Redacted constants.** `docs/src/ch00-00-rtl-overview.md:5` states the RTL "redacts some
  closed-source components." Constants reading `'0` may be placeholders rather than silicon values —
  one candidate critical was withdrawn on exactly this basis (§4). Any finding resting on a
  suspicious zero constant is a *question for the vendor*, not an assertion.
- **Black boxes**, absent from the upstream repo and unreviewable: ARM NIC-400, `ahb_bmx33_intf`,
  `ahb_bmxif_intf`, the `CM7AAB` AXI→AHB bridge, `cm7top`, `sdvt_spi_master_core`,
  `trbcx1r32_daric_wrapper`. **`hauser`/`AxUSER` propagation through the two AHB matrices and CM7AAB
  cannot be proven from open RTL**, and several findings depend on it.
- Third-party IP under `rtl/ips/` and the generated VexRiscv netlist received targeted review only.
- Severity ratings have not been through a formal calibration pass.
- The 82 generated sections carry the reviewers' evidence and verdicts but not the mitigation
  synthesis (RTL fix vs. firmware workaround) that BAO-001…031 have.

## Findings at a glance

**117 findings — 1 critical, 30 high, 54 medium, 27 low, 5 informational.**

The single critical, **BAO-001** (`rrc.sv:360`): the live ReRAM key-slot access-control table can be
rewritten by an unprivileged bus master *even when the controller's own check has just denied the
write*, yielding plaintext key material. Software-only, deterministic, silent.

Two structural patterns account for most of the rest, and are better treated as systemic items than
as ~40 separate bugs:

1. **Register write-protection is effectively absent chip-wide.** The `sfrlock` mechanism exists in
   the AMBA SFR primitives and is honoured correctly, but is hard-tied to zero in ~25 blocks, left an
   undriven net at `soc_top.sv:217` for all of system control, and tied to `'0` where it was routed
   to the top. No boot stage can freeze the clock tree, PMU trims, pinmux, tamper masks or the BDMA
   whitelist before handing off.
2. **There is no bus-level identity filter.** `coreuser`/`hauser` are consumed only by the SCE and
   the ReRAM controller, and the RRC's master decode has **no deny-by-default arm** — any master it
   does not recognise silently inherits the CM7's identity.

The crypto countermeasures are present but non-functional as integrated: the AES first-order mask is
cancelled before the round state is registered *and* is generated by a fixed-IV LFSR whose dedicated
TRNG input is tied to zero; the TRNG's default post-processing publishes its own LFSR state as the
random output with no entropy compression.

## Contents

| File | What it is |
|---|---|
| **`baochip-1x-security-review-full.md`** | **The report.** 117 findings, §§1–7, Appendix A. |
| `audit-raw.json` | Machine-readable record: 16 reviewer batches, 16 verifier batches, 40 adversarial votes, 2 critics, 2 recon maps. The evidence trail behind every finding. |
| `recon-trust-boundary-map.md` | Privilege/`coreuser` scheme, bus masters, lock bits, black-box inventory. |
| `recon-secret-asset-flow-map.md` | Where every secret lives, who can read it, zeroization analysis. |
| `build-report.py` | Regenerates the report from the record below. Run it to check the report against the evidence. |
| `baochip-1x-security-review-auto.md` | Build input: the narrative pass, which supplies the 31 critical/high sections verbatim. |
| `appendix-a-sce-key-segments.md` | Build input: Appendix A, on whether the SCE key segments have a hardware read-block. |
| `reviewed-commit.txt` | Pinned commit hash, subject, date. |

Findings BAO-001…031 carry full narrative analysis. BAO-032 onward are rendered from the structured
reviewer record — same evidence, attack scenario and verdict, more compact. Four entries
(BAO-046, 047, 052, 057) had no structured record and were **read against the RTL directly during
assembly** by the orchestrating model; each is marked as such and carries source-quoted evidence.

## Method

16 parallel domain reviewers over the RTL, each followed by an **independent verifier** instructed to
re-derive every finding from source and default to *refuted* where it could not substantiate the
claim itself. Every critical/high finding then faced a **two-lens adversarial panel** — code-truth
and exploitability — whose explicit instruction was to refute. A finding survived only where not
every lens refuted it. Two critics then assessed coverage and documented-guarantee-versus-RTL.

The filtering was not cosmetic. **The critical count fell from 9 to 1** under adversarial review.
Across all 90 primary findings: 63 confirmed, 19 plausible, 8 refuted — the withdrawals and their
reasoning are in §4. Verifiers additionally surfaced 40 findings the domain reviewers had missed. Of
40 adversarial votes, 34 upheld and 6 refuted, with 24 rating exploitability `practical`.

§5 reproduces both critics essentially unedited, including a section on **factual errors in the
audit's own coverage claims** — what an audit missed matters as much to a reader as what it found.

## Reproducing

```sh
python3 build-report.py    # rebuilds baochip-1x-security-review-full.md from audit-raw.json
```

## Suggested next steps

1. Produce proof-of-concept traces. The upstream `verilate/` subset simulation is the natural vehicle
   for BAO-001 and the SCE-RAM pointer findings.
2. Work §5's coverage critique — several security-relevant modules were never read by anyone, and
   whole vulnerability classes were never probed.
3. Screen every finding resting on a zero-valued constant against the redaction caveat above.
