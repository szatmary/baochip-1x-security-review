# Baochip 1x — RTL Security Review

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

*An independent review of the open-source RTL. Static source review only; no finding has been demonstrated on hardware — see Limitations.*

Reviewed commit: `1be12f4` — *"Merge pull request #22 from baochip/zmmul"*
Report date: 2026-08-03
Findings: 117 (1 critical, 30 high, 54 medium, 27 low, 5 informational)

---

## 1. Scope and methodology

### 1.1 What was reviewed

Static review of the SystemVerilog/Verilog RTL in this repository at commit `1be12f4`, organised into 16 parallel domains:

| Domain | Principal files |
|---|---|
| SCE access control | `rtl/modules/crypto_top/rtl/sce_sec.sv`, `sce.sv`, `sce_glbsfra.sv` |
| SCE DMA | `scedma*.sv`, `sce_dmachnl.sv`, `sce_memc.sv` |
| AES | `rtl/modules/crypto_aes/rtl/*`, `crypto_top/rtl/aes.sv`, `core/rtl/qfc_aes.sv` |
| Hash | `rtl/modules/crypto_hash/rtl/*`, `crypto_top/rtl/combohasha.sv` |
| PKE / ALU | `rtl/modules/crypto_pke/rtl/*`, `crypto_alu/rtl/*` |
| TRNG | `rtl/modules/crypto_trng/rtl/*`, `crypto_top/rtl/trng.sv` |
| ReRAM / NVM | `rtl/modules/rrc/rtl/*` |
| CPU (VexRiscv) | `VexRiscv/*`, `rtl/modules/vexriscv/rtl/cram_axi.sv`, `core/rtl/vexsys.sv` |
| CPU / memory / DMA (CM7) | `rtl/modules/core/rtl/cm7sys*.sv`, `mdma.sv`, `qfc.sv`, `bmxcore.sv` |
| BIO / BDMA | `rtl/modules/bio_bdma/rtl/*` |
| Mailbox and AMBA fabric | `rtl/modules/mbox/rtl/*`, `rtl/modules/amba/rtl/*` |
| System control / clock / reset | `rtl/modules/sysctrl/rtl/*` |
| Always-on domain | `rtl/modules/ao/rtl/*` |
| Tamper / security sensors | `rtl/modules/sec/rtl/*` |
| JTAG / DFT / BIST | `rtl/modules/dft/rtl/*`, `rtl/modules/rbist/rtl/*` |
| External peripherals | `rtl/modules/ifsub/rtl/*`, `rtl/ips/udma/*` |

Integration was traced at `rtl/asic_top/rtl/soc_top.sv`, `daric_top.sv`, `rtl/modules/soc_coresub/rtl/soc_coresub.sv`, `rtl/modules/ifsub/rtl/soc_ifsub.sv` and `rtl/asic_top/rtl/pad_frame_arm.sv`. Where the vendor documentation under `docs/src/` makes an explicit behavioural guarantee, the RTL was compared against it; several findings below are documentation-versus-implementation mismatches.

### 1.2 Threat model

| | Capability assumed |
|---|---|
| **T1** | Unprivileged software execution on either CPU (CM7 or VexRiscv). The primary realistic attacker. |
| **T2** | Physical access: JTAG probing, clock/voltage/EM glitching, decapsulation, laser fault injection, power/EM side-channel measurement, cold-boot / memory remanence. |
| **T3** | Control of external peripherals: SPI slave, USB device, SCIF (smart card), ADC inputs, external flash on the QFC/XIP interface, GPIO. |
| **T4** | Ability to reset, power-cycle, brown-out, or manipulate clocks and power domains. |

Assets: private keys and key material in the SCE and crypto RAM; ReRAM contents; secure-boot integrity; isolation between the two CPUs and between `coreuser` privilege levels; TRNG entropy quality; tamper-detection integrity; debug lockout state.

### 1.3 How findings were verified

Each candidate finding went through three stages:

1. **Discovery** — a domain reviewer reading the RTL end-to-end and tracing each security-decision signal to its drivers and consumers.
2. **Independent verification** — a second reviewer re-derived the mechanism from the RTL without relying on the finder's chain, re-quoted every cited line, recomputed all address and segment arithmetic, and searched for compensating controls (lock bits, redundant checks, upstream filters, parameter overrides, dead-code / emulation-only paths). Seven candidate findings were refuted at this stage and are listed in §4. Many surviving findings had their severity, preconditions or mechanism corrected; those corrections are recorded in each finding's *Verification notes*.
3. **Adversarial refutation panel** — every critical and high finding was additionally reviewed by two independent refuters working from opposing lenses (one attempting to break the mechanism, one attempting to break the exploitability). One finding was dismissed at this stage (§4). Where the two refuters disagreed on severity or exploitability, the dissent is reported verbatim in the finding's *Verification notes* rather than resolved silently.

Findings marked **(verifier-surfaced)** were discovered during stage 2 rather than stage 1; they received the same verification and, where critical or high, the same panel review.

### 1.4 Limitations — please read

- **RTL-only static review.** No simulation, formal verification, synthesis, gate-level analysis, netlist inspection, or silicon testing was performed. Cycle-level claims are hand-derived from the RTL and should be confirmed against your own regressions before you act on them.
- **Closed-source and absent IP received no review, or targeted review only.** The following are referenced by the build but are not present in this repository and could not be read: the NIC-400 (`nic400_1`), `ahb_bmx33_intf`, `ahb_bmxif_intf`, `CM7AAB`, the Cortex-M7 core and CoreSight blocks, `cmsdk_ahb_to_apb` / `cmsdk_ahb_master_mux` / `cmsdk_ahb_to_ahb_sync`, the `rbist` MBIST engine, the ReRAM macro controller `trcx1r32_*_trc_top` and its JTAG TAPs, `sdvt_spi_master_core` (the QFC XIP cipher), `xhci_top` (the entire USB device controller), the Tessent MBIST collateral, all SRAM/ReRAM macros, the PMU and all analog cells (`RNG_CELL`, `OSC_32M`, `ip_gluecell`, `ip_lightdet`, voltage comparators), and the ARM watchdog/timer IP. Several findings are stated at reduced confidence solely because a signal disappears into one of these blocks; each such case is called out explicitly.
- **The VexRiscv generated netlist received targeted, not exhaustive, review.** `VexRiscv_CramSoC.v` (12 430 lines) and `cram_axi.sv` (23 156 lines) were read in the security-relevant regions (CSR privilege logic, MMU, coreuser generation, AES Zkn, debug plugin, address decode). The cache controllers, page-table walker refill/eviction FSM, LR/SC and AMO logic, branch predictor and hazard network were not audited.
- **The A1 metal-mask ECO commit (`86d5293`) was not read during the audit.** It is the vendor's own written statement of six previously-known security defects and their fixes, touching `cm7sys.sv`, `rrc.sv` and `cms.sv` — exactly the files behind several findings below. See §5, item 2: this is the single highest-priority cross-check before acting on the ReRAM findings.
- **`rtl/modules/sysctrl/rtl/cms.sv:34-39` declares all four 128-bit chip-mode unlock patterns as `'0`.** Four identical values in one enumeration is not legal SystemVerilog, and `docs/src/ch00-00-rtl-overview.md:5` states the release redacts closed-source components, so these are treated as redaction placeholders rather than silicon values. One candidate critical finding built on them was refuted for that reason (§4). Please confirm the real constants are non-trivial and mutually distinct.
- **No firmware was available.** Findings whose exploitability depends on what firmware does (which registers boot code locks, which CPU owns the SCE, whether the CM7 MPU or Vex page tables are configured) are stated with that dependency made explicit rather than assumed away.

---

## 2. Executive summary

### 2.1 Bottom line for an engineering lead

The chip's security architecture is coherent on paper — a `coreuser` privilege tag derived from the executing code region, a per-slot ReRAM access-control table, an owner-locked crypto engine, a tamper subsystem — but in this RTL each of those mechanisms has at least one path that bypasses it, and in several cases the bypass is a single unprivileged store instruction. The most serious defect (BAO-001) lets ordinary firmware-stage code rewrite the live ReRAM key-slot access-control table even when the controller's own check has just denied the write, yielding plaintext key material; it is software-only, deterministic, silent, and unpatchable in this silicon.

Two structural patterns account for the bulk of the remaining findings and are worth treating as single systemic items rather than as ~40 separate bugs. First, **register write-protection is effectively absent chip-wide**: the `sfrlock` mechanism exists in the AMBA SFR primitives and is honoured correctly, but it is hard-tied to zero in roughly 25 blocks, left as an undriven net at `soc_top.sv:217` for the whole system-control block, and tied to `'0` at the one place it was routed to the top (`soc_top.sv:772`). There is therefore no point in the boot flow at which any stage can freeze the clock tree, the PMU trims, the pinmux, the tamper masks or the BDMA whitelist before handing off. Second, **there is no bus-level identity filter anywhere**: `coreuser` and `hauser` are consumed only by the SCE and the ReRAM controller, and the ReRAM controller's master decode has no deny-by-default arm, so any master it does not recognise silently inherits the CM7's identity.

The crypto engines have real countermeasures that do not function as integrated: the AES first-order mask is cancelled before the round state is registered *and* is generated by a fixed-IV LFSR whose dedicated TRNG input port is tied to zero; the TRNG's default post-processing publishes its own LFSR state as the random output with no entropy compression; and the health test is wired such that it fires on healthy data in the reset configuration. Finally, several of these are timing-window or fault-injection issues, but the majority are ordinary load/store reachable, which is the category that matters most for a part that cannot be respun.

Because the part is taped out, §3 splits every mitigation into an RTL fix for a future die revision and, separately, what firmware can and cannot do on existing silicon. For a substantial number of findings the honest answer is that no software mitigation exists; those are marked as such.

### 2.2 Findings index

| ID | Sev | Title | Location |
|---|---|---|---|
| [BAO-001](#bao-001) | Critical | ACRAM access-control table rewritten despite denial | `rrc.sv:360` |
| [BAO-002](#bao-002) | High | Unbounded hash segment pointer reads any SCERAM word | `combohasha.sv:629` |
| [BAO-003](#bao-003) | High | BDMA tagged AMBAID4_MDMA; matches no RRC master decode branch | `bio_bdma.sv:122` |
| [BAO-004](#bao-004) | High | SCE RAM wipe skips the TRNG output pool | `sce.sv:417` |
| [BAO-005](#bao-005) | High | SCE DMA pointer bounds-checked one cycle too late | `sce_memc.sv:212` |
| [BAO-006](#bao-006) | High | SCERAM AHB slave: ACL segid from next address phase | `scedma_amba.sv:99` |
| [BAO-007](#bao-007) | High | Segment start pointer clamp applied to stale value | `sce_dmachnl.sv:123` |
| [BAO-008](#bao-008) | High | AES DPA mask is a fixed-IV LFSR; TRNG port tied to zero | `aes.sv:283` |
| [BAO-009](#bao-009) | High | AES first-order masking cancelled before the round register | `AesDataPath.v:171` |
| [BAO-010](#bao-010) | High | AES engine SCERAM read pointer escapes its segment | `aes.sv:341` |
| [BAO-011](#bao-011) | High | Montgomery final reduction is data-dependent in time | `mimm.sv:338` |
| [BAO-012](#bao-012) | High | SCE trust state (ReRAM key unlock) is forgeable | `combohasha.sv:490` |
| [BAO-013](#bao-013) | High | HMAC trust check completes on a shared DMA done pulse | `combohasha.sv:484` |
| [BAO-014](#bao-014) | High | Default TRNG post-processing publishes raw LFSR state | `lfsr129.v:100` |
| [BAO-015](#bao-015) | High | LFSR zero-state guard reloads a compile-time constant | `lfsr129.v:88` |
| [BAO-016](#bao-016) | High | Raw entropy and live DRBG seed readable over APB | `trng.sv:278` |
| [BAO-017](#bao-017) | High | Every TRNG control register permanently unlocked | `trng.sv:52` |
| [BAO-018](#bao-018) | High | TRNG excluded from the SCE reset; seed survives mode change | `sce.sv:534` |
| [BAO-019](#bao-019) | High | Voltage-tamper reset mask used as a scalar; resets to disabled | `sensorc.sv:93` |
| [BAO-020](#bao-020) | High | Mesh arming lost on warm reset; mesh clock software-gateable | `soc_top.sv:702` |
| [BAO-021](#bao-021) | High | Sticky USER-mode latch cleared by the external reset pad | `ao_top.sv:144` |
| [BAO-022](#bao-022) | High | AO SRAM never zeroized, contradicting documented behaviour | `ao_top.sv:248` |
| [BAO-023](#bao-023) | High | PMU regulator enables and trims unlocked; brown-out reset masked | `ao_sysctrl.sv:433` |
| [BAO-024](#bao-024) | High | DISABLE_FILTER_PERI is a dead net; MEM bit disables both filters | `bio_bdma.sv:1478` |
| [BAO-025](#bao-025) | High | RRC master decode has no deny-by-default arm | `rrc.sv:670` |
| [BAO-026](#bao-026) | High | ReRAM mass erase triggered by one unprivileged store | `rrc.sv:286` |
| [BAO-027](#bao-027) | High | All RRC access checks qualified by `data_op`; ifetch bypasses | `rrc.sv:679` |
| [BAO-028](#bao-028) | High | Vex fabric identity selected by software-written satp.ASID | `cram_axi.sv:5816` |
| [BAO-029](#bao-029) | High | `vex_mm` privilege signal is invertible and non-CPU-derived | `cram_axi.sv:20923` |
| [BAO-030](#bao-030) | High | Coreuser configuration bank unqualified on the CPU data bus | `cram_axi.sv:13121` |
| [BAO-031](#bao-031) | High | Vex instruction fetch bypasses all RRC checks (AxPROT[2]=1) | `VexRiscv_CramSoC.v:7484` |
| [BAO-032](#bao-032) | Medium | Modular inverse is an unblinded binary EEA | `PkeCtrl.sv:1933` |
| [BAO-033](#bao-033) | Medium | Unbounded hash output pointer defeats the ifsob/ifskey guard | `combohasha.sv:740` |
| [BAO-034](#bao-034) | Medium | Two ReRAM config bits disable the SCE mode lock and wipe | `sce.sv:131` |
| [BAO-035](#bao-035) | Medium | SCE trust state on system reset, not SCE reset; MSB hardwired | `sce.sv:298` |
| [BAO-036](#bao-036) | Medium | One ReRAM byte replaces the entire SCE DMA access-rule table | `sce.sv:376` |
| [BAO-037](#bao-037) | Medium | `acerr` violation reporting is structurally tied to zero | `scedma_ac.sv:61` |
| [BAO-038](#bao-038) | Medium | ReRAM key credentials are plain unlocked SCE DMA registers | `scedma.sv:106` |
| [BAO-039](#bao-039) | Medium | Unbounded array index in ich segment and AC rule lookup | `scedma.sv:277` |
| [BAO-040](#bao-040) | Medium | `transsize == 0` decodes as 2^30 transfers with no abort | `sce_dmachnl.sv:110` |
| [BAO-041](#bao-041) | Medium | AES has no fault detection; round count is one comparison | `AesCtrl.v:846` |
| [BAO-042](#bao-042) | Medium | CTR_DRBG never reseeds when `reseed_interval == 0` | `ctr_aes.v:187` |
| [BAO-043](#bao-043) | Medium | PKE countermeasure off by default, fixed IV, 1-bit reseed | `pke.sv:788` |
| [BAO-044](#bao-044) | Medium | ALU divider leaks the quotient's Hamming weight in cycles | `aludiv.sv:100` |
| [BAO-045](#bao-045) | Medium | Detected PKE RAM parity errors do not abort the operation | `pke.sv:1552` |
| [BAO-046](#bao-046) | Medium | mimm round count truncates; top words silently dropped | `mimm.sv:121` |
| [BAO-047](#bao-047) | Medium | Divide-by-zero guard tests the wrong index; ALU deadlocks | `aludiv.sv:120` |
| [BAO-048](#bao-048) | Medium | Parity-filter mode forces `digi_data_vld` high regardless of enables | `digitalization.v:83` |
| [BAO-049](#bao-049) | Medium | `apb_buf` decode aliases the seed buffer over adjacent registers | `trng.sv:432` |
| [BAO-050](#bao-050) | Medium | BIST port gives full RAM read/write; no zeroization on entry | `ram_1rw_s.sv:128` |
| [BAO-051](#bao-051) | Medium | RAM margin-trim registers unlocked and unprivileged | `rbist_wrp.sv:161` |
| [BAO-052](#bao-052) | Medium | CMS data register powers up holding the VIRGIN pattern | `cms.sv:107` |
| [BAO-053](#bao-053) | Medium | Mesh integrity check is a static, readable DC level | `mesh.sv:68` |
| [BAO-054](#bao-054) | Medium | Glue chain held in reset out of reset; state clearable by software | `gluechain.sv:58` |
| [BAO-055](#bao-055) | Medium | Every tamper event terminates in a maskable interrupt, disabled at reset | `soc_top.sv:480` |
| [BAO-056](#bao-056) | Medium | `sfr_vdip_ena` disables the voltage detectors at the source | `sensorc.sv:78` |
| [BAO-057](#bao-057) | Medium | Mesh tamper indications are never latched | `mesh.sv:55` |
| [BAO-058](#bao-058) | Medium | Keypad (PIN entry) pads mirrored into main-domain GPIO | `ao_sysctrl.sv:562` |
| [BAO-059](#bao-059) | Medium | AO timebase source is a software mux with no lock | `ao_sysctrl.sv:379` |
| [BAO-060](#bao-060) | Medium | Software can power down the SoC domain with no wake path | `ao_sysctrl.sv:588` |
| [BAO-061](#bao-061) | Medium | No AO configuration register is cleared by any warm reset | `ao_sysctrl.sv:434` |
| [BAO-062](#bao-062) | Medium | sysctrl `sfrlock` is an undriven net at the top level | `soc_top.sv:217` |
| [BAO-063](#bao-063) | Medium | Mesh clock is behind an unlocked software clock gate | `sysctrl.sv:867` |
| [BAO-064](#bao-064) | Medium | PLL, OSC trim and all dividers unbounded and unlocked (CLKSCREW) | `sysctrl.sv:881` |
| [BAO-065](#bao-065) | Medium | Clock cipher: fixed IV, 1-bit seed, inverted level semantics | `sysctrl.sv:667` |
| [BAO-066](#bao-066) | Medium | WDT_LOCKCR bypassable via the unlocked PCLK divider | `sysctrl.sv:839` |
| [BAO-067](#bao-067) | Medium | BDMA whitelist has no lock bit and no privilege check | `bio_bdma.sv:459` |
| [BAO-068](#bao-068) | Medium | Filter misses are re-addressed to a filter-exempt gutter | `bio_bdma.sv:2562` |
| [BAO-069](#bao-069) | Medium | Whitelist and gutter registers are write-only; policy unauditable | `bio_bdma.sv:461` |
| [BAO-070](#bao-070) | Medium | Inter-CPU mailbox endpoint has no access control | `mbox.sv:104` |
| [BAO-071](#bao-071) | Medium | `ahb_ar` ignores its `sfrlock` input | `ahb_sfr.sv:340` |
| [BAO-072](#bao-072) | Medium | ReRAM one-way counters incrementable with no access check | `rrc.sv:576` |
| [BAO-073](#bao-073) | Medium | Event-driven counter burn converts an access into an unchecked RMW | `rrc.sv:541` |
| [BAO-074](#bao-074) | Medium | MDMA is an unauthenticated bus master reaching the CM7 TCMs | `mdma.sv:100` |
| [BAO-075](#bao-075) | Medium | One unlocked bit permanently disables ITCM/DTCM parity | `cm7sys_tcm.sv:105` |
| [BAO-076](#bao-076) | Medium | Coreuser debounce holds the previous, higher-privilege identity | `cm7sys.sv:776` |
| [BAO-077](#bao-077) | Medium | No PMP; S-mode has unrestricted physical access | `GenCramSoC.scala:96` |
| [BAO-078](#bao-078) | Medium | `sstatus` exposes and permits writing `mstatus.MPRV` | `VexRiscv_CramSoC.v:8271` |
| [BAO-079](#bao-079) | Medium | ReRAM is cacheable; RRC checks only on fill | `VexRiscv_CramSoC.v:6801` |
| [BAO-080](#bao-080) | Medium | Coreuser encoder has no "no identity" value; default is boot0 | `cram_axi.sv:5851` |
| [BAO-081](#bao-081) | Medium | uDMA APB decoder deadlocks the bridge on unmapped slots | `udma_apb4k_if.sv:68` |
| [BAO-082](#bao-082) | Medium | Pinmux write-protect routed to the top and tied to zero | `soc_top.sv:772` |
| [BAO-083](#bao-083) | Medium | SCIF external clock ORed with internal clock, not muxed | `udma_scif.sv:217` |
| [BAO-084](#bao-084) | Medium | External SPI chip-select used as an unsynchronized FIFO reset | `udma_spis.sv:220` |
| [BAO-085](#bao-085) | Medium | SCIF SCC clock can latch stuck-at-1, freezing the interface | `udma_scif.sv:236` |
| [BAO-086](#bao-086) | Low | SCE ownership can never be granted to the VexRiscv | `sce_sec.sv:62` |
| [BAO-087](#bao-087) | Low | QFC XIP AES key and enable are unlocked control registers | `qfc.sv:202` |
| [BAO-088](#bao-088) | Low | Hash constants loaded from bus-writable RAM, excluded from wipe | `combohasha.sv:580` |
| [BAO-089](#bao-089) | Low | SCE ownership latched from the last transfer, not the mode writer | `sce_sec.sv:64` |
| [BAO-090](#bao-090) | Low | `sfrlock` declared but never driven in the SCE global SFR block | `sce_glbsfra.sv:65` |
| [BAO-091](#bao-091) | Low | Single ReRAM byte compare replaces the crypto DMA ACL | `scedma_ac.sv:40` |
| [BAO-092](#bao-092) | Low | AES CTR increments one 32-bit word with no carry or wrap flag | `aes.sv:463` |
| [BAO-093](#bao-093) | Low | Undefined `cr_func` permanently latches the AES SFR lock | `aes.sv:135` |
| [BAO-094](#bao-094) | Low | PKE exposes an exact per-operation cycle counter | `pke.sv:313` |
| [BAO-095](#bao-095) | Low | Montgomery intermediate RAM has no clear path | `PkeCore.sv:403` |
| [BAO-096](#bao-096) | Low | Undefined `cr_func` permanently latches the hash SFR lock | `combohasha.sv:203` |
| [BAO-097](#bao-097) | Low | `vdresetn` output flop has no reset; response is clock-dependent | `sensorc.sv:94` |
| [BAO-098](#bao-098) | Low | Light-detector debounce of 0xF disables all light detection | `sensorc.sv:110` |
| [BAO-099](#bao-099) | Low | AO backup registers have no lock, no owner tag, no tamper erase | `aobureg.sv:30` |
| [BAO-100](#bao-100) | Low | Security-error NMI escalation disabled at reset and re-maskable | `evc.sv:158` |
| [BAO-101](#bao-101) | Low | `cgucore` POR and warm reset tied together; CLKSYS select lost | `sysctrl.sv:415` |
| [BAO-102](#bao-102) | Low | CGUOWR, the only write-once primitive, is inert | `sysctrl.sv:977` |
| [BAO-103](#bao-103) | Low | Host reads of a running BIO's imem return its private RAM data | `bio_bdma.sv:1735` |
| [BAO-104](#bao-104) | Low | Mailbox `rx_err` / `tx_err` reported swapped | `mbox.sv:96` |
| [BAO-105](#bao-105) | Low | Mailbox TX word is a live tap; a second write is swallowed | `mbox_client.v:265` |
| [BAO-106](#bao-106) | Low | APB/AHB SFR banks ignore write byte strobes | `apb_sfr.sv:339` |
| [BAO-107](#bao-107) | Low | Mailbox PREADY is constant; gating its clock discards messages | `mbox.sv:105` |
| [BAO-108](#bao-108) | Low | ReRAM ECC and controller errors reach only a status register | `rrc.sv:289` |
| [BAO-109](#bao-109) | Low | ReRAM code-region protection disabled at reset (`rrccr[12]`) | `rrc.sv:778` |
| [BAO-110](#bao-110) | Low | Program-only slot attribute evaluated from the previous descriptor | `rrc.sv:535` |
| [BAO-111](#bao-111) | Low | Debug UART enabled at reset, unlocked, on a dedicated pad | `duart.sv:45` |
| [BAO-112](#bao-112) | Low | `mcounteren`/`scounteren` not implemented | `VexRiscv_CramSoC.v:6266` |
| [BAO-113](#bao-113) | Info | `healthtest_err` not qualified by `healthtest_en` | `healthtest.v:38` |
| [BAO-114](#bao-114) | Info | BIST read-data port driven with live functional RAM data | `ram_1rw_s.sv:140` |
| [BAO-115](#bao-115) | Info | RAM-trim write pulse synchronised on the wrong launch clock | `rbist_wrp.sv:186` |
| [BAO-116](#bao-116) | Info | JTAG TAP does not fall back to BYPASS for undefined instructions | `tap_top.sv:542` |
| [BAO-117](#bao-117) | Info | `ahb_gate` drops the AHB user tag at the SCE security boundary | `amba_components.sv:1028` |

---

## 3. Findings

Findings BAO-001 through BAO-031 (the critical and high severities) carry full narrative
analysis, including mitigations split into an RTL fix and what firmware can do on fabricated
silicon. BAO-032 onward are rendered from the structured reviewer record: the same evidence,
attack scenario and verification verdict, in a more compact form.

<a id="bao-001"></a>

### BAO-001 — Live ReRAM access-control table (ACRAM) is rewritten by an unprivileged master even when the RRC's own check denies the write

**Severity: Critical | CWE-1220 (Insufficient Granularity of Access Control) | Threat actor: T1 | Confidence: High**

**Location:** `rtl/modules/rrc/rtl/rrc.sv:360-365`, `:393`, contrasted with `:853`

**Description.** The RRC holds the per-slot access-control descriptors for all 2048 ReRAM key/data slots in a volatile SRAM shadow (`acram2kx64`, `rrc.sv:424`), loaded at boot from the ReRAM CFG region and re-writable at runtime by writing `0x603D_C000`–`0x603D_FFFF`. The non-volatile programming of those CFG words is correctly gated on `cmd_user_write_dis` (`rrc.sv:853`). The volatile shadow update is not: it fires on `rram_write_run & rramcfg_vld` alone. When `cfg_access_error` denies the write — for example because the requester's `coreuser` is not boot0/boot1 (`cfg_prev_dis`, `rrc.sv:815-816`) — the ReRAM itself is protected but the SRAM table that actually enforces key/data-slot access control is overwritten with attacker data anyway. The write address `{haddr_reg[13:5],acram_idx}` is attacker-chosen and spans the entire 2048-entry ACRAM, i.e. every key and data slot descriptor: `core_rd_dis_k`, `core_wr_dis_k`, `sce_rd_dis_k`, `sce_wr_dis_k`, `keytype_k`, `userid_k`, `akeyid`. Because every key/data check is terminated by `& (userid_k[7:4] != 4'h0)` (`rrc.sv:717`) / `& (userid_d[7:4] != 4'h0)` (`rrc.sv:726`), a descriptor written with a zero owner nibble disables that slot's access control entirely.

**Evidence.**
```systemverilog
// rrc.sv:358-365 — volatile ACRAM shadow update, NO cmd_user_write_dis term
assign rramcfg_vld = (hwaddr_reg[31:14] == {16'h603D, 2'b11});

`theregfull(clktop, sysresetn, acram_wrbuf, '0) <= trc_dout_ready_sdone & ( brfsm == 4 ) ? {trc_dout_s1[127:0],trc_dout_s0[127:0]} :
                                                rram_write_run & rramcfg_vld ? ahb_wr_buf : acram_wrbuf;
assign acram_wrbusy_pre = ( acram_idx == 2'b11 ) ? 1'b0 :
                              trc_dout_ready_sdone & ( brfsm == 4 ) | (rram_write_run & rramcfg_vld) ? 1'b1 : acram_wrbusy;

// rrc.sv:393 — attacker-chosen ACRAM write index
                        acram_wrbusy ? {haddr_reg[13:5],acram_idx} :

// rrc.sv:853 — the NON-VOLATILE path IS gated. The asymmetry is the defect.
        ( rrcfsm == 0 ) & rram_write_run & (!cmd_user_write_dis) ? 4 :

// rrc.sv:815-816, :827 — the denial being bypassed
assign cfg_prev_dis = (((!(coreuser_in[5] | coreuser_in[4])) & (cm7sel|vexsel)) | cm7sel&(!pri_op) | vexsel&(!vex_mm_reg) | scesel)
                         & ((haddr_reg[31:14] == PM_CFGD_REGION) | (haddr_reg[31:14] == PM_CFGK_REGION));
assign cmd_user_write_dis = (key_access_error | data_access_error | info_access_error | code_access_error | cfg_access_error) & ahb_write_flag;
```

**Preconditions.** (a) Write access to the RRC SFR window at `0x4000_0000` — available to CM7 AHB-P (`hauser` 0x8), Vex AHB-P (0xD), BDMA AHB (0x0) and MDMA (0x7); none of those ports is filtered. (b) Write access to the ReRAM AXI slave at `0x603D_C000`–`0x603D_FFFF`, which both CPUs have by construction. No `coreuser` or boot-stage privilege is required — the finding is interesting precisely when the attacker *lacks* boot0/boot1.

**Attack scenario.** Attacker is unprivileged firmware-stage code on the CM7 (`coreuser_in[5:4] == 2'b00`), exactly the identity `cfg_prev_dis` exists to keep out of the CFG region.

1. Write `0x0` to `RRC_SFR_RRCCR` at `0x4000_0000` to clear `rrccr[1]`. The register is instantiated `.sfrlock(1'b0)` (`rrc.sv:274`) on a bus with no `hauser`/`coreuser` filter (`soc_coresub.sv:823-824`).
2. Issue eight 32-bit writes to `0x603D_Cnnn` carrying the forged descriptor with `userid_k[7:4] = 4'h0` and `core_rd_dis_k = 0`. With `rrccr[1] == 0` these land in `ahb_wr_buf` (`rrc.sv:568-571`, which has no access check at all) and go no further.
3. Write `0x2` to `0x4000_0000` to set `rrccr[1]`.
4. Write the magic `0x0000_9528` (`PM_RRAM_WRITE`) to the same `0x603D_Cnnn` address. `cfg_prev_dis` → `cfg_access_error` → `cmd_user_write_dis = 1`, so `rrcfsm` never enters state 4 and the ReRAM CFG word is correctly *not* programmed. But `rrc.sv:361/365` fire regardless: `acram_wrbuf <= ahb_wr_buf`, `acram_wrbusy` asserts, and over the next four `clktop` cycles the forged 4×64-bit descriptor is written into ACRAM.
5. Read the ReRAM key slot at `0x603F_xxxx`. `keycfg`/`userid_k` now come from the forged entry, `key_access_error` evaluates to 0, and `ahbarray.hrdata` returns the raw key material instead of `64'h0`.

The denial is silent: `ahbarray.hresp` is tied to `2'h0` (`rrc.sv:583`) and `rrccr[15]` (the NMI enable) resets to 0. Repeating steps 2–4 unlocks every key and data slot. The compromise persists until the next `sysresetn` re-runs the boot read.

**Impact.** Complete bypass of the ReRAM key/data-slot access control from unprivileged software, yielding plaintext key material — including keys marked CPU-read-disabled and intended for SCE-only use — plus write access to those slots. No physical access, no glitching, no race window. This is the primary asset the device exists to protect.

**Mitigation (a) — RTL, future die revision.** Gate the ACRAM shadow update with the same term as the NV write: change `rrc.sv:361` and `:365` to `rram_write_run & rramcfg_vld & (!cmd_user_write_dis)`. Better, drive the shadow update strictly from the completion of a successful NV program (the `rrcfsm == 4 → 0` transition) so the volatile table can never diverge from its backing store. Additionally give the RRC SFR port at `0x4000_0000` a `coreuser`/`hauser` filter, or at minimum a real `sfrlock` instead of the hardwired `.sfrlock(1'b0)` at `rrc.sv:274-286`.

**Mitigation (b) — fabricated silicon.** Partial only, and weak. `rrccr` has no lock, so boot0/boot1 cannot prevent later stages clearing `rrccr[1]`. The only effective containment is to prevent any code that is not boot0/boot1 from reaching `0x4000_0000` at all — on the CM7 this requires enabling the MPU, on the Vex an MMU/PMP region excluding `0x4000_0000` and `0x603D_C000`–`0x603D_FFFF`; note BAO-077 (no PMP on the Vex) makes the second impossible. Boot code should additionally re-verify the ACRAM against the CFG region before any key-slot access and set `rrccr[15]` so violations at least raise an NMI. **There is no firmware action that closes this defect.**

**Verification notes.** The independent verifier re-derived the asymmetry from the RTL: `cmd_user_write_dis` appears at `rrc.sv:576, 577, 827, 850, 853` and nowhere in the `acram_wrbuf`/`acram_wrbusy`/`acram_addr` path. Compensating controls were searched for and not found — the write-data buffer load is unqualified, the RRC SFR bus carries no identity filter (`ahb_demux.sv:114` passes `hauser` through; `bmxcore.sv` contains no filtering logic), denial is silent, and the module is instantiated in the real silicon path (`daric_top.sv:362` → `soc_top.sv:555` → `soc_coresub.sv:809`), not the FPGA `rrc_emu` variant. Address arithmetic was independently confirmed: the 11-bit write index reaches the key-descriptor half of the ACRAM via CFG addresses `0x603D_E000`–`0x603D_FFFF`.

Both refuters confirmed independently and neither dissented on severity or exploitability. Refuter 1 added corroborating evidence that the ACRAM update was never intended to run standalone: in the legitimate case `rrcfsm` enters state 4 so `ahbarray.hready` stalls the bus for the burst, whereas in the denied case `hready` stays high and `haddr_reg` can be re-latched mid-burst — the missing term is an omission, not a design choice. Refuter 2 independently confirmed the CFG address `0x603D_E000 + n*32` maps onto key descriptors using the testbench image loader's own layout (`daric_rv32_tb.sv:717`), and confirmed that code executing from SRAM receives the fw1 catch-all `coreuser` and therefore provably cannot read a boot0-owned key without the forge.

Two cosmetic errors in the original write-up were corrected and are reflected above: step 1 writes `0x0`, not `0x2`, to clear `rrccr[1]` (and note `ahb_sfr2_ECO` at `rrc.sv:1258` ORs `32'h0000_1000` into every `rrccr` write, so bit 12 is set as a side effect); and the `rrccr` reset value comes from the default `parameter IV=32'h0` at `rrc.sv:1144`, not from `rrc.sv:292`.

---

<a id="bao-002"></a>

### BAO-002 — Unbounded software segment pointer lets the hash engine read any SCERAM word, defeating write-only protection on SKEY / AKEY / PKB / SCRT

**Severity: High | CWE-1262 (Improper Access Control for Register Interface) | Threat actor: T1 | Confidence: High**

**Location:** `rtl/modules/crypto_top/rtl/combohasha.sv:629` (also `:593, 602, 611, 638, 647, 664`)

**Description.** `COMBOHASH_SFR_SEGPTR` (`0x4002_B020`–`0x4002_B03C`) is a bank of eight raw 12-bit pointers with no range check. `combohasha.sv:629` uses `cr_segptrstart[SEGID_MSG]` as the DMA read-pointer start for the message load, with `rpsegcfg = SEG_MSG` (segaddr 256, segsize 128). The range clamp in `sce_dmachnl.sv:123-125` is evaluated against the *previous* value of `rpptr`, so the loaded start value is used verbatim for the first read of every transfer; only from the second beat is it clamped. `sce_memc.sv:212` then forms the RAM address as a bare 12-bit add with no bound check. Crucially, the hash engine is wired to `ramreq[8]`/`ramres[8]` (`sce.sv:454-455`), outside the `chnlreq[0:CHNLACCNT-1]` range that `scedma_ac` filters, so the per-segment access rules never see this port. The first word of every hash-engine transfer is therefore fetched from SCERAM word `(256 + cr_segptrstart[SEGID_MSG]) mod 4096` — an arbitrary word of the crypto RAM, including every write-only `ST_KI` key segment.

**Evidence.**
```systemverilog
// combohasha.sv:223 — eight raw 12-bit pointers, no range check
apb_cr #(.A('h20), .DW(scedma_pkg::AW), .SFRCNT(SEGCNT+1) )      sfr_segptr    (.cr(cr_segptrstart), .prdata32(),.*);

// combohasha.sv:629
                    chnli_cfg.rpptr_start = cr_segptrstart[SEGID_MSG] + segptrdyna;

// sce_dmachnl.sv:123-125 — clamp tests the CURRENT register, so the load is unchecked
`theregrn( rpptr ) <= ( rpptr > therpsegcfg.segsize ) ? 0 :
                      chnlstart ? thecfg.rpptr_start :
                      transdone ? (( rpptr == therpsegcfg.segsize - 1 ) ? 0 : rpptr + 1 ) : rpptr;

// sce_memc.sv:212 — bare 12-bit add, wraps mod 4096
    assign ramm_addr[gvk] = arbm_dat[gvk].segaddr + arbm_dat[gvk].segptr;

// sce.sv:377-380 vs :454-457 — the hash port is OUTSIDE the access-controlled range
        .chnlinreq          ( chnlreq[0:CHNLACCNT-1]  ),
        .chnloutreq         ( ramreq[0:CHNLACCNT-1]   ),
...
            .chnl_rpreq     (ramreq[8]),
            .chnl_wpreq     (ramreq[9]),

// scedma_pkg.sv:294 — the guarantee being broken: key segments are read-denied on every channel
        '{ segid:SEGID_SKEY , accessrule: 8'b01_01_01_01 },
```

**Preconditions.** Write access to the COMBOHASH APB page at `0x4002_B000` and read access to `SEG_SOB` at `0x4002_0700`. In secure mode both are available to whichever `coreuser` owns the SCE — which is precisely the party the `ST_KI` write-only rule exists to constrain. In `scemode == 0` the whole SCE aperture is open (`sce_sec.sv:72`) but the access rules are disabled anyway, so the finding is only meaningful in secure mode.

**Attack scenario.** The attacker owns the SCE in `mode_sec` and wants to read AKEY, PKB or SKEY, all nominally write-only.

1. Write `COMBOHASH_SFR_SEGPTR[SEGID_MSG]` (`0x4002_B030`) = 1536. `SEG_MSG.segaddr` is 256, so the first read is issued at SCERAM word 1792 = AKEY[0]. (SKEY[0] at word 128 is reached with 3968, wrapping mod 4096; PKB[0] at 512 with 256.)
2. Fill `SEG_MSG` with chosen data, program `CRFUNC = HF_SHA3`, set `ifsob = 1`, `ifskey = 0`.
3. Start the operation. The first beat reads word 1792 — the clamp only fires the following cycle — and the key word lands at HRAM word `RAMSEG_MSG+0`, i.e. Keccak lane A[0][0]. The remaining 49 words are attacker-supplied.
4. `MFSM_HF` runs the permutation; `MFSM_WB_SOB` copies all 50 words of the final state into `SEG_SOB`.
5. Read `SEG_SOB` over AHB (permitted, rule `8'b10_00_10_00`). Keccak-f[1600] is a bijection, so the leaked word is recovered exactly by offline inversion. With HF_SHA256, a 2^32 offline search recovers it instead.
6. Increment and repeat: 64 iterations dump AKEY, 256 dump PKB, 64 dump SKEY/SCRT.

**Impact.** Complete defeat of the write-only property of the SCE key segments, from software, deterministically, with no fault injection. This converts a "may use the key" capability into "may clone the key", breaking device binding for keys that the DMA/key-store path loads from ReRAM without software ever seeing them.

**Mitigation (a) — RTL.** Clamp the pointer at load time — `chnlstart ? ((thecfg.rpptr_start >= therpsegcfg.segsize) ? '0 : thecfg.rpptr_start) : ...` in `sce_dmachnl.sv:123-129` — and saturate `ramm_addr` in `sce_memc.sv:212` against the segment size rather than relying on 12-bit truncation. Route `ramreq[8]`/`[9]` through `scedma_ac` like channels 0–7, and replicate the ALU's `ST_KI` guard (`alu.sv:512-517`) in the hash engine so a bus-programmed pointer can never select a key segment.

**Mitigation (b) — fabricated silicon.** No register can bound the pointer, so the `ST_KI` write-only guarantee must be treated as void. Firmware must: never let untrusted code reach `0x4002_B000` (the SCE owner must be the most-privileged code, and ownership must be claimed by boot ROM before third-party code runs); never keep a long-lived key resident in SEG_SKEY/SEG_AKEY/SEG_PKB across a window in which less-trusted code can execute — load, use, then immediately issue `sfr_arclr` (write `0xa5` to `0x4002_801C`); and treat "can program COMBOHASH" as equivalent to "can read all SCE keys" in the threat model.

**Verification notes.** The verifier confirmed all quoted lines verbatim and re-derived the cycle sequence: `chnlstart` and `transstart` are both high at cycle 0, so `rpptr <= rpptr_start` and `rprdvld <= 1` on the same edge; at cycle 1 `rprd` is asserted with `rpptr` still at the raw value; the clamp fires only at the end of cycle 1. Exactly one arbitrary word per transfer, repeatable. The AC bypass is structural: `scedma_ac.sv:43-53` gates only indices `0..CHNLCNT-1`. Segment arithmetic (SEGADDR_MSG 256, AKEY 1792, PKB 512, SKEY 128) was recomputed. `SEG_MSG` has `isfifo:'1`, but the FIFO pointer override only applies when `ffen` is set, and `cr_ffen` is an attacker-writable register resetting to 0.

Both refuters confirmed. **Dissent on severity:** refuter 1 argued for critical, on the grounds that the design's own ALU implements exactly the missing `ST_KI` guard (`alu.sv:512-523`) so the omission is demonstrably an oversight, and that the leak is a deterministic one-word-per-run primitive against the chip's primary asset. Refuter 2 held it at high, on the grounds that the attacker must already hold SCE ownership rather than being arbitrary unprivileged code, and that in non-secure mode the keys are directly readable anyway so the bug gains nothing there. We report **high** and record the dissent. Two evidence corrections were applied: the ACRULEs table spans `scedma_pkg.sv:290-310` (not 250-255), and the leak is one word per `scedma_chnl` transfer, not per 512-bit message block. The verifier additionally confirmed the same defect on the write side (`combohasha.sv:740`) — reported separately as BAO-033.

---

<a id="bao-003"></a>

### BAO-003 — BDMA AXI master is tagged `AMBAID4_MDMA`, matching no branch of the ReRAM master decode; it inherits the CM7's coreuser while bypassing every per-slot and privileged-mode check

**Severity: High | CWE-1259 (Improper Restriction of Security Identifier Assignment) | Threat actor: T1 | Confidence: High**

**Location:** `rtl/modules/bio_bdma/rtl/bio_bdma.sv:122`, `:1360`, `:1373`; `rtl/modules/ifsub/rtl/soc_ifsub.sv:344`; consumed at `rtl/modules/rrc/rtl/rrc.sv:666-672`

**Description.** `bio_bdma`'s AXI master identity parameter defaults to `daric_cfg::AMBAID4_MDMA` (`4'h7`) and `soc_ifsub` instantiates the block with no parameter override, so the BDMA emits `awuser`/`aruser = 0x7`, colliding with the MDMA. The RRC identifies its requester with exactly three comparisons covering 0x2 (CM7 AXI), 0x3/0x4 (Vex I/D) and 0x5/0x6 (SCE), then selects the `coreuser` bundle with a ternary chain that has **no default branch**: any unrecognised master falls through to `coreuser_cm7`. In that same case `cm7sel`, `vexsel` and `scesel` are all 0, which annihilates every other term in all five RRC access-check expressions, because each is ANDed with `(cm7sel|vexsel)` or `scesel`. The MDMA — whose ID the BDMA re-uses — is deliberately address-excluded from ReRAM (`bmxcore.sv:162-165`, comment `// to nic_1, but no ReRAM`), which is plausibly why the RRC has no case for 0x7; the BDMA's AXI master has no such exclusion and reaches NIC-400 port m0 = `rrc_axi64` directly.

**Evidence.**
```systemverilog
// bio_bdma.sv:122 — default never overridden
    parameter AHBMID4 = daric_cfg::AMBAID4_MDMA
// bio_bdma.sv:1360, :1373
    assign axim.awuser = AHBMID4|'0;
    assign axim.aruser = AHBMID4|'0;
// soc_ifsub.sv:344 — no override
    bio_bdma #() bio (

// rrc.sv:666-672 — no deny-by-default arm
assign cm7sel = ( hauser_reg == AMBAID4_CM7A );
assign vexsel = ( hauser_reg == AMBAID4_VEXI ) | ( hauser_reg == AMBAID4_VEXD );
assign scesel = ( hauser_reg == AMBAID4_SCEA ) | ( hauser_reg == AMBAID4_SCES );
assign coreuser_mux = scesel ? sceuser :
                        vexsel ? coreuser_vex : coreuser_cm7;

// rrc.sv:815-819 — with cm7sel=vexsel=scesel=0 this collapses to a constant 0
assign cfg_prev_dis = (((!(coreuser_in[5] | coreuser_in[4])) & (cm7sel|vexsel)) | cm7sel&(!pri_op) | vexsel&(!vex_mm_reg) | scesel)
                         & ((haddr_reg[31:14] == PM_CFGD_REGION) | (haddr_reg[31:14] == PM_CFGK_REGION));
assign cfg_access_error_pre = (((cfg_rd_dis & (cm7sel|vexsel)) | cfg_prev_dis) & ahb_read_flag |
                                ((cfg_wr_dis  & (cm7sel|vexsel)) | cfg_prev_dis) & ahb_write_flag ) & data_op;

// bmxcore.sv:162-165 — the exclusion applied to the MDMA but not the BDMA
localparam rule32_t [1:0] mdma_ahb_demux_map = '{
    '{idx: 32'd1 , start_addr: 32'h0000_0000, end_addr: 32'h6000_0000}, // to ahb_bmx33
    '{idx: 32'd0 , start_addr: 32'h6100_0000, end_addr: 32'ha000_0000}  // to nic_1, but no ReRAM
};
```

**Preconditions.** A BIO program with memory-path reach into `0x6000_0000`–`0x603F_FFFF`, obtained either by a firmware-granted whitelist window overlapping ReRAM or by setting `DISABLE_FILTER_MEM` (see BAO-024). Writing the BIO SFR block at `0x5012_4000` requires MMIO access, not necessarily boot privilege. AxUSER propagation through the NIC-400 was verified at the port map only; the NIC itself is a hard macro.

**Attack scenario.**
1. Attacker obtains a BIO program with a memory window covering ReRAM. The BDMA memory path is decoded to `0x6000_0000`–`0x7FFF_FFFF` internally and lands on NIC-400 m0 = the RRC.
2. BIO reads a ReRAM DATA slot at `0x603E_xxxx` whose descriptor has `core_rd_dis_d = 1` — the explicit "CPU cores may not read this, only the SCE may" control. With `hauser_reg = 0x7`, the `core_rd_dis_d & (cm7sel|vexsel)` term is 0, the `cm7sel&(!pri_op)` privileged-mode term is 0, and the SCE terms are 0. The only surviving condition is the CM7's live `coreuser` nibble overlapping the slot owner — which it does, because the CM7 is running the firmware that set the BIO up. The same read issued by the CM7 itself would be denied.
3. Escalation: the BDMA reads and writes the ReRAM CFG/ACRAM region at `0x603D_C000`–`0x603D_FFFF`, for which `cfg_access_error_pre` is *identically zero* for this master — the boot0/boot1 requirement and the privileged-mode requirement are both gated away. Writes reprogram the ACRAM through the same path as BAO-001, letting the attacker rewrite `userid_k`, `core_rd_dis_k` and `akeyid` for every slot and then read the key material out.
4. Denials are silent throughout (`rrc.sv:583` ties `hresp` to `2'h0`), so probing is free.

**Impact.** A privilege escalation across a boundary the RRC explicitly implements: firmware running with fw0/fw1 `coreuser` cannot write the ACRAM directly, cannot read a `core_rd_dis_d` slot, and cannot touch the CFG region — but it can whitelist a ReRAM window for the BDMA and have the BDMA do all three on its behalf, inheriting the CM7's own nibble for the one surviving check. End state is full ReRAM key extraction.

**Mitigation (a) — RTL.** Two parts, both required. (1) Allocate a distinct AMBAID for the BDMA and override it at instantiation, so it no longer aliases the MDMA. (2) Close `rrc.sv:670-671` with an explicit deny-by-default: add `assign othersel = ~(cm7sel|vexsel|scesel);` and OR it into every access-error expression, so an unrecognised master is denied rather than inheriting `coreuser_cm7`. Mirror the MDMA's ReRAM address exclusion onto `bdma_axi32` in `bmxcore.sv`.

**Mitigation (b) — fabricated silicon.** Never grant the BDMA a whitelist window overlapping `0x6000_0000`–`0x60FF_FFFF`; never set `DISABLE_FILTER_MEM` (which, per BAO-024, also disables the peripheral filter); keep `0x5012_4000` out of every untrusted address space; and hold the BIO in reset or clock-gated whenever key material is resident in ReRAM. There is no way to make the RRC check correct from software.

**Verification notes.** The verifier confirmed the parameter default, the absence of any override at either instantiation site, the constants (`AMBAID4_MDMA = 4'h7` at `daric_cfg_pkg.sv:77`), and the full routing path `soc_ifsub.sv:370 → axi_thru → bmxcore.sv:199 → axi_mux_dma → axi_mux → nic .s2 → .m0(rrc_axi64)`, with `ARUSER` carried at `nic1_intf.sv:157/362` and landed on `ahbarray.hauser` at `aab_intf.sv:116`. The collapse of `cfg_access_error_pre` to a constant zero was independently re-derived in the live `#eco16` version of the code, not the commented-out copy.

Both refuters confirmed. **Dissent on severity:** refuter 2 argued for critical, noting that `ts[255]` is hardwired to 1 (`sce_sec.sv:123`) so an attacker who rewrites `akeyid` to 255 needs no HMAC unlock at all, and that `cm7sys.sv:761` gives SRAM-resident code the fw1 tag so the owner-nibble race is not needed for fw1-owned slots. Refuter 1 held it at high on the grounds that the attack is not reachable from a bare unprivileged context — it needs BIO SFR write access plus a ReRAM window or `DISABLE_FILTER_MEM`. We report **high**. One correction from verification: step 2 alone is a bypass of the per-slot `core_rd_dis`/`core_wr_dis` and privileged-mode controls, not of the owner check, which still applies; step 3 (the CFG/ACRAM region, where the check is identically zero) is the decisive part.

---

<a id="bao-004"></a>

### BAO-004 — SCE crypto-RAM sanitisation deliberately skips the TRNG output pool, leaving used nonces and generated keys readable by the next owner

**Severity: High | CWE-226 (Sensitive Information in Resource Not Removed Before Reuse) | Threat actor: T1, optionally T4 | Confidence: High**

**Location:** `rtl/modules/crypto_top/rtl/sce.sv:414-418`

**Description.** `sceramclr` is the SCE's only sanitisation primitive: asserted three cycles after every SCE reset release and on the `ar_clrram` action register. For the SCERAM instance — the single 2560×32 RAM holding every SCE segment — the wipe end address is overridden from the default `WCNT-1` (2559) to `SEGADDR_RNGA-1` (1983). Words 1984–2495 are the RNGA and RNGB segments, i.e. the 2 KB pool into which the TRNG writes its conditioned output. Those words are never cleared by any software-visible operation: not by `ar_clrram`, not by `ar_reset`, not by the `modequit` reset on a mode downgrade, and not by a system reset (the SRAM macro has no reset, and scrambling is disabled — `cryptoram.sv:112-113` ties `.scmben('0), .scmbkey('0)`). They remain bus-readable: RNGA's rule `8'b10_11_10_10` permits AHB read, and in `mode_non` the rule table is bypassed entirely while the ownership gate is unconditionally open.

**Evidence.**
```systemverilog
// sce.sv:414-418 — the wipe stops at word 1983
            cryptoram #(
                .ramname    ("SCERAM"),
                .thecfg     (RAMCFGS[gvk]),
                .clrend     (scedma_pkg::SEGADDR_RNGA-1)
            )m(

// cryptoram.sv:61-64
    assign ramclrdone = ( ramclrfsm == clrend );
    `theregrn( ramclrfsm ) <= ramclr ? clrstart : ramclrdone ? '0 : ramclrfsm + ramclren;

// sce_sec.sv:87 — the only sanitisation trigger in the design
	assign sceramclr = ( initregs == 4'h7 ) | ar_clrram ;

// trng.sv:366 — the TRNG writes exactly there
    assign chnlo_cfg.wpsegcfg = ~opt_segsel ? scedma_pkg::SEG_RNGA : scedma_pkg::SEG_RNGB;

// sce_sec.sv:72 and sce.sv:370 — and it is readable afterwards
    assign ahben =  mode_non ? 1'b1 :
    assign acenable = mode_sec;
```

**Preconditions.** Code execution on either CPU, or control of any AHB master reaching `0x4002_0000` (the BIO/BDMA qualifies), plus the ability to observe the SCE after a secure session ends — which is the normal steady state after boot, or can be forced with a warm reset. No physical access required. Only firmware that explicitly overwrites RNGA/RNGB before relinquishing the SCE is protected.

**Attack scenario.**
1. Secure boot or trusted firmware takes SCE ownership and generates key material — ECDSA/EdDSA per-signature nonces, ECDH ephemeral scalars, symmetric session keys, PKE blinding factors. All of it is delivered through the pool at SCERAM words 1984–2495 (`0x4002_1F00`–`0x4002_26FF`).
2. The session ends: `ar_clrram`, `ar_reset`, a handoff, or a warm reset. In every case `sceramclr` pulses and the wipe runs — stopping at word 1983.
3. The SCE is now in `mode_non` (the mode register is reset by any SCE reset), so `ahben` is unconditionally 1 and `acenable` is 0. Every AHB master has unrestricted access.
4. The attacker issues 512 word loads from `0x4002_1F00`–`0x4002_26FF` and recovers verbatim the random values the previous secure session consumed. A single recovered ECDSA nonce yields the long-term private key by simple algebra.
5. Nothing is logged: `scedma_ac` raises `acerr` only for denials, and this access is permitted.

**Impact.** Recovery of prior-session secret randomness — nonces, ephemeral scalars, generated symmetric keys — by any bus master, after the operation the design offers as its sanitisation primitive has apparently succeeded. For ECDSA this is equivalent to private-key recovery.

**Mitigation (a) — RTL.** Remove the `.clrend` override at `sce.sv:417` so the wipe covers all 2560 words; clear the RNGA/RNGB FIFO pointers on `sceramclr` rather than only on system reset (`sce_memc` currently takes `resetn`, `sce.sv:397`); and consider making the pool destructive-on-read so consumed randomness cannot be re-read.

**Mitigation (b) — fabricated silicon.** Fully mitigable in firmware but requires discipline. Before any secure session terminates, before any `ar_clrram`/`ar_reset`, and as the first action of secure boot, the owning code must itself write 512 words of zeros to `0x4002_1F00`–`0x4002_26FF` while it still holds ownership. Note that in `mode_sec` the RNGA/RNGB rule denies AHB *writes*, so the overwrite must be done via a SCEDMA AXI write channel (axi-write is permitted) — this is non-obvious and undocumented. The scrub must be repeated in the reset path, because the attacker can force the reset asynchronously.

**Verification notes.** The segment map was recomputed from `scedma_pkg.sv:211-230`, confirming RNGA starts at word 1984 and the wipe covers 0–1983. `sceramclr` was confirmed as the only sanitisation trigger in the tree. Readability was confirmed on both the `mode_non` path (rule table bypassed) and the `mode_sec` path (RNGA's rule index 0 is 1). No compensating control exists: no scrambling, no destructive read, and `sce_memc` is on the system reset so the FIFO pointers survive too. Two minor corrections: the unwiped range is words 1984–2559 (2496–2559 are unallocated tail), and with `segfifoen` clear the TRNG writes only words 1984–1987, so the residue set is smaller in that configuration but is still bus-readable and still never wiped.

Both refuters confirmed at high with no dissent. Refuter 1 contributed evidence the original reviewers missed: RNGA's rule permits the SCE's internal DMA to copy RNGA into SKEY/AKEY/PKB, and those destinations lie below word 1983 and *are* wiped — so the hardware demonstrably erases generated key material from one location while leaving a byte-identical copy in another. Refuter 2 noted an aggravating factor: in `mode_sec` the RNGA/RNGB rule has AHB-write = 0, so the owning secure firmware cannot even zero the pool over AHB; the hardware provides no convenient sanitisation for exactly the region its sanitisation primitive skips.

---

<a id="bao-005"></a>

### BAO-005 — SCE DMA segment pointer bounds-checked one cycle too late and `sce_memc` never clamps, giving a software-programmable arbitrary-word read of SCERAM

**Severity: High | CWE-1285 (Improper Validation of Specified Index) | Threat actor: T1 (SCE owner in mode_sec) | Confidence: High** *(verifier-surfaced)*

**Location:** `rtl/modules/crypto_top/rtl/sce_memc.sv:212`, `rtl/modules/crypto_top/rtl/sce_dmachnl.sv:123-125`

**Description.** `scedma_ac` enforces confidentiality per **segment ID only** — it never checks that the address the channel presents lies inside that segment. `sce_memc.sv:212` forms the RAM address as a bare modular 12-bit add of segment base and channel pointer, with no comparison against `segcfg.segsize`. The only bound check in the design lives in `scedma_chnl` and is applied one cycle *after* the pointer is used, because the out-of-range term is a branch of the same flop that loads the software-supplied start value. Exactly one read per channel start is therefore issued at `segaddr + arbitrary_12-bit_offset`, its data is captured and forwarded to the write port, and `scedma_ac` approves it because the *segid* was legitimately permitted. The design clearly knows about range checking here — `scedma_amba.sv:426` bounds-checks the segid — it simply never bounds-checks the pointer.

**Evidence.**
```systemverilog
// sce_memc.sv:212 — no segsize compare, no clamp; adr_t is 12 bits so this wraps mod 4096
        assign ramm_addr[gvk] = arbm_dat[gvk].segaddr + arbm_dat[gvk].segptr;

// sce_dmachnl.sv:123-125 — the clamp tests the OLD rpptr, so the load is unchecked
`theregrn( rpptr ) <= ( rpptr > therpsegcfg.segsize ) ? 0 :
                      chnlstart ? thecfg.rpptr_start :
                      transdone ? (( rpptr == therpsegcfg.segsize - 1 ) ? 0 : rpptr + 1 ) : rpptr;

// scedma_ac.sv:45-53 — decision is segid-only; segaddr/segptr forwarded untouched
    assign chnlinsegid[i] = chnlinreq[i].segcfg.segid;
    assign chnlacrule = chnlacrules[chnlinsegid[i]][i] ;
    assign chnlac[i] = acenable ? chnlacrule : '1;
    assign chnloutreq[i].segaddr   = chnlinreq[i].segaddr   ;
    assign chnloutreq[i].segptr    = chnlinreq[i].segptr    ;

// scedma.sv:91, :102 — the pointer source is an unlocked SFR
    assign sfrlock = 0;
    apb_cr #(.A('h20 ), .DW(AW)   ) sfr_xch_segstart (.cr( xchcr.segstart ), .prdata32(),.*);
```

**Preconditions.** SCE ownership in `mode_sec` — the state in which the write-only key segments are supposed to be unreadable, because `acenable = mode_sec` makes `scedma_ac` enforce rule `8'b01_01_01_01` (read denied on every channel) for LKEY/KEY/SKEY/SCRT/PKB/AKEY. The pointer SFRs have no lock (`scedma.sv:91`).

**Attack scenario.** The attacker holds SCE ownership; secure boot has loaded a ReRAM key slot into SKEY (words 128–191), material the owner is explicitly not supposed to read back. For `k = 0..63`:

1. Write `sfr_sch_segid` = `SEGID_SOB` (or AOB / PSOB — any segment whose rule permits a read on the chosen channel). SOB's base is word 448 and it is not a FIFO segment.
2. Write `sfr_sch_segstart` = `(128 + k - 448) mod 4096 = 3776 + k`. This exceeds SOB's segsize of 64, so the clamp will fire — one cycle too late.
3. Write `transize = 1` and `axstart` = an attacker-owned SRAM buffer; start the channel.
4. On the cycle after the start pulse the channel presents `segaddr = 448`, `segptr = 3776+k` with `segrd` asserted. `scedma_ac` approves on the segid; `sce_memc` computes `448 + 3776 + k = 4224 + k`, wrapping to `128 + k` — inside SKEY. The word is read, captured, and DMA'd out to the attacker's buffer over the SCE AXI master.

Sixty-four iterations recover the full 256-bit key. The same primitive reaches SCRT, KEY, LKEY, PKB and AKEY. `scedma_ac` raises no `acerr` because the access was permitted; the wrap is silent.

**Impact.** Complete bypass of the crypto-RAM access-control table from the SCE-owning context — the exact boundary that separates "use a ReRAM-bound key" from "read it out". Deterministic, software-only, one word per DMA start.

**Mitigation (a) — RTL.** Clamp the value being loaded, not the resident value: `rpptr <= chnlstart ? ((thecfg.rpptr_start >= therpsegcfg.segsize) ? '0 : thecfg.rpptr_start) : ...`. Note the existing comparison is `>` rather than `>=`, which additionally admits `segptr == segsize`. `sce_memc.sv:212` should saturate or drop the request when `segptr >= segsize`, and `scedma_ac` should validate `segaddr + segptr` against the segment it authorised rather than trusting the `segid` field.

**Mitigation (b) — fabricated silicon.** The scedma SFR block has no lock bit, so firmware cannot prevent this from a lower privilege level. The only field mitigation is to never leave key material in SCERAM across any window in which untrusted code can reach `0x4002_9xxx` — clear the crypto RAM via `sfr_arclr` immediately after every operation, noting that this does *not* clear RNGA/RNGB (BAO-004).

**Verification notes.** Surfaced by the independent verifier rather than the domain reviewer. Cycle-accurate re-derivation confirms the single out-of-range beat: `theregrn` is a plain async-reset flop, so the clamp reads the current `rpptr` (0 after reset and after every clamped run); `rprd = rprdvld` is asserted the cycle after `chnlstart`; the arbiter grant is combinational with `arbm_gnt` tied to 1, so the address is consumed in the same cycle it is presented and is not re-sampled after the clamp.

Both refuters confirmed at high, no dissent. Refuter 1 corrected the vehicle: `SEG_AOB` has `isfifo:'1`, so that specific path first requires clearing `cr_ffen[3]`; `SEG_SOB` (segid 6) and `SEG_PSOB` (segid 12) are non-FIFO and cleaner. Refuter 2 independently established that the bypassed rule is genuinely load-bearing, tracing `rrc.sv:674` (`keytype_in` from the AXI ID) and the `keytype_k` match, which bind a keytype-0 ReRAM key to SCERAM segids 0–3 — all of which are write-permitted and read-denied on every channel. Both noted the honest scope limit: the attacker must already own the SCE, and SCERAM is cleared on mode entry, so only secrets loaded during the attacker's own session are reachable — but that is precisely the boundary the rule table exists to enforce.

---

<a id="bao-006"></a>

### BAO-006 — SCERAM AHB slave takes its access-control segment ID from the next address phase while the RAM address comes from the current one

**Severity: High | CWE-1264 (Insecure De-Synchronization between Control and Data Channels) | Threat actor: T1 (SCE owner) | Confidence: Medium**

**Location:** `rtl/modules/crypto_top/rtl/scedma_amba.sv:94-109`, `:144`

**Description.** `scedmachnl_ahbs` builds the segment descriptor from two different pipeline stages. The `segid` field — the only thing `scedma_ac` uses for its allow/deny decision — is computed combinationally from the live `ahbs.haddr`, i.e. the address phase of the *next* transfer during the data phase of the current one. The `segaddr` field — the value that actually reaches the SCERAM address pins — is `ahbshaddr_dp`, the registered address of the *current* transfer. The read channel is wired to the combinational descriptor. Because `scedma_ac` gates only on segid and forwards `segaddr`/`segptr` untouched, an attacker who arranges for the next address phase to name a read-permitted segment gets a read of any address in the 2560-word SCERAM, including the key segments. This is invisible in normal operation because sequential accesses land in the same segment, so directed functional tests pass while the property is void.

**Evidence.**
```systemverilog
// scedma_amba.sv:94-97 — the segid decoder is fed the LIVE address; only segaddr is registered
    assign ahbshaddr_local = ( ahbs.haddr - BA ) >> 2;
    `theregrn( ahbshaddr_dp ) <= ahbs_cpvld ? ahbshaddr_local : ahbshaddr_dp;
    scedmachnl_addr2seg #(.SEGCNT(SEGCNT),.SEGCFGS(SEGCFGS)) ut( .addr(ahbshaddr_local), .segvld( ahbs_segvld ), .segid( ahbs_segid ));

// scedma_amba.sv:99-105 — mixed-stage descriptor
    assign ahbs_segcfg = '{
                            segid:          ahbs_segid,
                            ...
                            segaddr:        ( SEGCFGS[ahbs_segid].isfifo & segfifoen[SEGCFGS[ahbs_segid].fifoid] ) ? SEGCFGS[ahbs_segid].segaddr : ahbshaddr_dp,

// scedma_amba.sv:144 — the read channel takes the combinational descriptor
    assign chnlo_thecfg.rpsegcfg = ahbs_segcfg;
```

**Preconditions.** SCE in `mode_sec` (so `acenable = 1` and the rules are enforced), attacker is the SCE AHB owner, and the master issues two back-to-back AHB reads — standard for any CPU load pair. The one assumption not provable from this repository is that the fabric presents the next address during the SCE's wait state; every in-repo element on the path is a combinational HADDR pass-through, and AHB pipelining mandates it, but `cmsdk_ahb_to_ahb_sync` is not present.

**Attack scenario.** SKEY (segid 2, words 128–191) has rule `8'b01_01_01_01`, so `0x4002_0200` must read back as zero. SOB (segid 6, words 448–511) has rule `8'b10_00_10_00` — AHB read permitted, `isfifo = 0`.

1. The attacker executes two back-to-back loads: `ldr r0,[0x4002_0200]` (SKEY word 0) immediately followed by `ldr r1,[0x4002_0700]` (SOB word 0).
2. Cycle 0 is the address phase of A0; `ahbshaddr_dp` latches word index 128.
3. Cycle 1 is the data phase; `hready` is driven low, so the master holds A1 on HADDR. `addr2seg` therefore outputs segid 6 (SOB), while `segaddr` remains 128.
4. `scedma_ac` looks up SOB's rule, permits the read, and does not zero the return data.
5. `sce_memc` computes `128 + 0 = 128` and reads SKEY[0]; `ahbs.hrdata` returns it.

Stepping A0 across `0x4002_0200`–`0x4002_02FF` dumps the 256-bit secret key; the same trick reaches AKEY, PKB, LKEY and KEY. No error, no interrupt (see BAO-037).

**Impact.** Defeat of the write-only property of every key segment in the only mode where the ACL exists at all, using two ordinary load instructions.

**Mitigation (a) — RTL.** Derive both fields from the same pipeline stage: move the `addr2seg` lookup onto the registered `ahbshaddr_dp`, or latch `ahbs_segid` with `ahbs_cpvld` exactly as `ahbshaddr_dp` is latched. Better, have `scedma_ac` re-derive the segment from `segaddr + segptr` rather than trusting the `segid` field, so the decision and the address are provably about the same word.

**Mitigation (b) — fabricated silicon.** No firmware action restores the property in general. Partial mitigation is to keep the SCE crypto-RAM window unreachable from all masters including the `mode_sec` owner and move all key transport onto the AXI DMA channels — but note BAO-005 and BAO-007 defeat that too.

**Verification notes.** All quoted lines were confirmed verbatim and the cycle timing independently walked. Nothing in the path registers HADDR: `ahb_demux.sv:106` and `amba_components.sv:1038` are pure combinational pass-throughs. The rule-table bit ordering was re-derived (`bit [0:CHNLACCNT-1]`, ascending, so index 0 is the leftmost literal bit), confirming SKEY read-denied and SOB read-permitted. `sce.sv:203-204` confirms the AHB read port is AC channel index 0. Severity was lowered from the finder's critical to **high** because the AHB window is only reachable by the SCE owner in `mode_sec` — this is a bypass of the ACL that constrains an already-privileged context, not a path from arbitrary unprivileged software.

Both refuters confirmed at high with no dissent. Both independently corrected the finder's claim that the write channel is unaffected: `ahbs_segcfgreg` at `scedma_amba.sv:111` is a *free-running* register, not one qualified by `ahbs_cpvld`, so the write path carries the same desync one cycle later. The fix is to derive segid from `ahbshaddr_dp`, not to mirror the write path. Refuter 1 flagged the residual uncertainty honestly: the ARM sync bridge is absent from the repository, so HADDR advancement during the wait state is inferred from the AHB protocol and from the fact that the design's own `ahbshaddr_dp` register would be dead logic if HADDR were stable. Confidence is therefore **medium**, and the vendor should settle it with one directed simulation.

---

<a id="bao-007"></a>

### BAO-007 — Segment start pointer is bounds-clamped one cycle too late: every SCE DMA start performs one access at an unchecked 12-bit SCERAM address

**Severity: High | CWE-1285 | Threat actor: T1 (software reaching the SCE APB at `0x4002_9000`) | Confidence: High**

**Location:** `rtl/modules/crypto_top/rtl/sce_dmachnl.sv:123-125`; consumed at `sce_memc.sv:212`

**Description.** The same stale-comparison defect as BAO-005, exercised through the general and secure AXI DMA channels rather than an engine port. `rpptr_start` is a raw APB register (`scedma.sv:102`, `DW(AW)` = 12 bits, `sfrlock` tied to 0) routed straight into the channel (`scedma_amba.sv:447`). The clamp tests the resident `rpptr`, which is 0 after reset and after every completed transfer, so the software value loads unchecked; `rprd` is armed on the same edge, so the first read is issued while `rpptr` still holds it. `scedma_ac` never sees the pointer — it inspects only `segcfg.segid` — so the resulting access is fully authorised. The same defect exists on the write pointer but is not exploitable there, because `wpwr` asserts two cycles after `chnlstart`, by which time the clamp has fired.

**Evidence.**
```systemverilog
// sce_dmachnl.sv:120-129
    `theregrn( rpptr ) <= ( rpptr > therpsegcfg.segsize ) ? 0 :
                          chnlstart ? thecfg.rpptr_start :
                          transdone ? (( rpptr == therpsegcfg.segsize - 1 ) ? 0 : rpptr + 1 ) : rpptr;
// sce_dmachnl.sv:104, :114, :134, :139 — the read is issued the cycle after the load
    assign chnlstart = start & ~busy;
    assign transstart = ~busy ? start : ~lasttrans & transdone;
    `theregrn( rprdvld ) <= transstart ? 1'b1 : rprdvld & rpready ? 1'b0 : rprdvld;
    assign rprd = rprdvld;
// scedma.sv:91, :110 — unlocked, full-width pointer SFR
    assign sfrlock = 0;
    apb_cr #(.A('h40 ), .DW(AW)   ) sfr_sch_segstart (.cr( schcr.segstart ), .prdata32(),.*);
// scedma_pkg.sv:23
    parameter AW = 12;
```

**Preconditions.** Write access to the scedma SFRs (`0x4002_9010`–`0x4002_9044`); no write protection exists. The chosen cover segment must be non-FIFO or have `segfifoen` clear for its `fifoid` (the reset value). The channel must win the `sce_memc` round-robin on the first request cycle — automatic when no other channel is active.

**Attack scenario.** Target SKEY (word 128, rule read-denied on every channel). Cover segment AOB (segid 15, base 1920, rule `8'b10_10_10_10`, axi-read permitted on the general channel).

1. Write `sfr_xch_segid` = 15, `sfr_xch_segstart` = 2304 (`1920 + 2304 = 4224 → 128`), `sfr_xch_axstart` = attacker SRAM buffer, `sfr_xch_func` = 1 (SCERAM → AXI), `sfr_xch_transize` = 1.
2. Write the start magic to the channel's action register.
3. Cycle 0: `chnlstart` loads `rpptr = 2304` (not `> 64`, because the resident value is 0). Cycle 1: `rprd` asserts with `rpptr = 2304`; `scedma_ac` approves on segid 15; `sce_memc` drives word 128 = SKEY[0]. The word is emitted on AXI into the attacker's buffer.
4. Repeat across the pointer range to dump all 2560 words including LKEY, KEY, SCRT, PKB (PKE private key buffer) and AKEY (live AES key and IV). A variant needs no wrap at all: PSOB (base 1408) with segstart 256 lands directly on AKEY[0] at word 1664.

**Impact.** Full crypto-RAM read from the SCE-owning context, ~2–3 register writes plus one load per word.

**Mitigation (a) — RTL.** As BAO-005: clamp the loaded value, use `>=` rather than `>`, saturate in `sce_memc`, and have `scedma_ac` validate the resulting address.

**Mitigation (b) — fabricated silicon.** None that closes it — `scedma.sv:91` hard-ties `sfrlock` to 0, so firmware cannot write-protect the pointer registers. Minimise residency: clear SCERAM with `sfr_arclr` immediately after each operation and never expose `0x4002_9xxx` to code not already trusted with the crypto RAM.

**Verification notes.** The clamp priority, the cycle sequence, the absence of any downstream bound, and the SFR widths were all re-derived independently. `SOB` rule bit 4 (axi-secure read) = 1 and `sce.sv:344-345` confirms `schrpreq` is `chnlreq[4]`. Severity was lowered from the finder's critical to **high** on the same basis as BAO-005/BAO-006: reachable only by the SCE owner in `mode_sec`, and moot in `mode_non` where the ACL is disabled anyway.

Both refuters confirmed at high, no dissent. Refuter 1 ruled out the most plausible refutation by reading `rr_arb_tree` (`rtl/ips/common_cells/src/rr_arb_tree.sv:148-149`) and `sce_memc.sv:211` (`arbm_gnt` tied 1): the address is consumed combinationally in the presented cycle, not re-sampled later. Refuter 2 established the boundary's real meaning from `rrc.sv:620-634` and `:712-717`, which implement an explicit split between `core_rd_dis_k` (CPU read denied) and `sce_rd_dis_k` (SCE read allowed) — i.e. a slot can be provisioned "this coreuser may USE this key but may never READ it", and the ACRULEs are the sole enforcement of that. Both noted the engine ports `ramreq[8..16]` bypass `scedma_ac` entirely and feed the same `scedma_chnl` from raw SFRs, so the same primitive exists on several engines (see BAO-002, BAO-010).

---

<a id="bao-008"></a>

### BAO-008 — AES DPA countermeasure mask is a fixed-IV deterministic LFSR; the dedicated random-mask input port is tied to zero

**Severity: High | CWE-1241 (Use of Predictable Algorithm in RNG) | Threat actor: T2, with T1 to trigger operations | Confidence: High**

**Location:** `rtl/modules/crypto_top/rtl/aes.sv:282-283`, `:35`; `rtl/modules/crypto_top/rtl/sce.sv:507-508`, `:524`

**Description.** The SCE AES engine's first-order Boolean mask, which feeds every `AesSbox` instance via `AesCore.MaskIn`, is produced by a single `drng_lfsr` whose initial state is a compile-time constant, whose shift enable is tied to `'1`, and whose only reseed path injects exactly one bit. The engine also has a dedicated 32-bit `maskin` port evidently intended for TRNG entropy: it is declared but referenced nowhere inside the module, and at the integration point `sce.sv` drives it with a hard-wired zero. The mask stream is therefore a deterministic function of (fixed IV, number of `clksub[3]` edges since `sysresetn`), plus at most one attacker-visible bit per `sfr_maskseedar` write. It can be recomputed offline, reducing the masked S-box to an unmasked S-box for differential power/EM analysis. Two aggravating details: `sfr_maskseed` is in the APB read-back OR-list, and the LFSR's reset is the SoC `sysresetn` rather than `sceresetn`, so an SCE reset or mode quit does not perturb the mask state.

**Evidence.**
```systemverilog
// sce.sv:507-508, :524 — the TRNG-intended port is tied to zero
    logic [31:0] aesmask;
    assign aesmask = '0;
            .maskin         (aesmask),
// aes.sv:35 — declared, never referenced again in module aes (lines 20-536)
    input  logic [31:0]    maskin,
// aes.sv:282-283 — compile-time IV, sen tied high, reset is the SoC reset
    drng_lfsr #( .LFSR_W(229),.LFSR_NODE({ 10'd228, 10'd225, 10'd219 }), .LFSR_OW(32), .LFSR_IW(32), .LFSR_IV('h5a5a_a5a5) )
        ua( .clk(clk), .sen('1), .resetn(sysresetn), .swr(maskseedupd), .sdin(maskseed), .sdout(aesmaskdat) );
// insauth.v:38 — the reseed XORs only sdin[31], one bit, into a 229-bit state
    `theregfull( clk, resetn, sdata, LFSR_IV ) <= sen ? ( swr ? ( sdin[LFSR_IW-1] ^ sdata ) : sdatapre ) : sdata ;
```

**Preconditions.** Power or EM measurement while the SCE AES processes data under a secret key, and the ability to observe or bound the number of AES-clock cycles between reset and the operation (T1 software makes this exact). Standard ChipWhisperer-class equipment; no decapsulation, glitching or JTAG required.

**Attack scenario.** The attacker profiles one sacrificial part: after `sysresetn` release the 229-bit state is exactly `'h5a5a_a5a5`, and it advances one step per `clksub[3]` edge, which is ICG-gated by `cr_suben[3]` — itself software-visible. Because the IV is a compile-time constant with no per-device diversification, the mask sequence is identical on every device and every power-up. The attacker triggers AES operations under the victim key at a controlled time after reset, records power/EM traces, and un-masks their own hypothesis: `AesDataPath.v:101` computes `DataIn_tmp = DataIn ^ MaskIn` with a `MaskIn` the attacker reproduces, so for each key-byte guess `k` they predict `(P^k)^MaskIn[byte]` and correlate. Order 10^3–10^4 traces recovers the full 128/192/256-bit key from the AKEY segment.

**Impact.** The intended first-order DPA countermeasure provides no protection. The AES key is sourced from the SCE AKEY segment, which the ACRULEs make unreadable to software (`8'b01_01_01_01`) — so this converts a "may use, may not read" key oracle into key recovery for a physical attacker.

**Mitigation (a) — RTL.** Drive `maskin` from a live TRNG tap instead of `assign aesmask = '0;`, and actually use it inside `aes.sv`. Fix `insauth.v:38` so the whole `sdin` word is XORed into the state rather than only bit 31. Tie `sen` to `1` so the generator free-runs and does not restart from a known state when the countermeasure is toggled. Reset the mask generator on `sceresetn` so a context switch forces re-randomisation. Note this fix alone is insufficient — see BAO-009.

**Mitigation (b) — fabricated silicon.** Partial. Firmware can write `sfr_maskseed` (`0x4002_D020`) with a TRNG word and pulse `sfr_maskseedar` (`0x4002_D024`) before every operation, but only one bit per pulse is injected, so meaningful entropy requires ~229 pulses with independent TRNG bits in bit 31, repeated after every system reset. Firmware must also randomise the number of AES-clock cycles between reset and each operation. This raises the DPA cost but does not restore the countermeasure. There is no documentation of `AES_MASKSEEDAR` anywhere in the repository, so this is unlikely to be happening today.

**Verification notes.** The verifier confirmed `maskin` appears only at the port declaration inside `module aes` (line 547 is inside the separate `dummytb_aes` module), and confirmed `aesmaskdat` is the only driver of `AesCore.MaskIn`. Two facts strengthen rather than weaken the finding: `clksub[3]` is ICG-gated by `cr_suben[3]`, making the state a function of software-visible enable windows and therefore *easier* to reproduce; and `sce.sv:513` passes `.sysresetn(resetn)` so the mask generator is not reset by the SCE-local reset. The comparable `pke.sv:800/805` instances gate their LFSRs with `sen(optsec)` and CDC-sync the reseed, evidence that the AES connection is an integration oversight.

Both refuters confirmed at high with no dissent on severity. Refuter 1 noted a genuine but undocumented firmware mitigation (because `swr` XORs one bit and the LFSR shifts between writes, ~229 writes would randomise the state) and confirmed by grep that nothing in `docs/` or the repository references the register. Refuter 2 emphasised that the masking is structurally incomplete even with perfect entropy — see BAO-009 — so the two findings collapse to one silicon fix but remain independently valid.

---

<a id="bao-009"></a>

### BAO-009 — AES first-order masking is nullified at the round boundary: the round state is un-masked before it is registered, and the first AddRoundKey is entirely unmasked

**Severity: High | CWE-1300 (Improper Protection of Physical Side Channels) | Threat actor: T2 | Confidence: High**

**Location:** `rtl/modules/crypto_aes/rtl/AesDataPath.v:162-178`; consumed at `AesCore.v:94`, `AesCtrl.v:693`

**Description.** `AesDataPath` re-combines the mask into the datapath output on every round: each active branch of the `DataOut` mux XORs the S-box/MixColumns result with `MaskOut` or `MixMaskOut`, cancelling it. That un-masked value is returned to `AesCtrl` and clocked directly into the sixteen state flip-flops `SReg00..SReg33`. Masking therefore covers only the combinational S-box/MixColumns cone; every sequential element in the cipher — where CMOS switching energy is largest and Hamming-distance leakage cleanest — holds plain, unmasked AES round state. Worse, the `FirstRound` branch has no mask term at all: `DataIn ^ RoundKeyIn` computes plaintext XOR round-key-0 with the raw key word out of ARAM and registers it, the textbook first-order DPA target. The key-expansion branch likewise unmasks before the expanded round-key word is written back to ARAM, so the whole round-key schedule is stored unmasked. This is independent of BAO-008: even with a perfect TRNG mask, the register-level leakage remains.

**Evidence.**
```systemverilog
// AesDataPath.v:162-178 — every active arm cancels the mask; FirstRound has no mask term
assign DataOut =
                Enc & FirstRound   ? DataIn ^ RoundKeyIn  	:
                Enc & LastRound    ? SboxDataOut ^ RoundKeyIn  	 ^ MaskOut:
                Enc                ? MixColDataOut ^ RoundKeyIn  ^ MixMaskOut:
                Dec & FirstRound   ? DataIn ^ RoundKeyIn  	 :
                Dec & LastRound    ? SboxDataOut ^ RoundKeyIn    ^ MaskOut:
                Dec                ? MixColDataOut ^ RoundKeyOut ^ MixMaskOut:
	        KeyEn              ? SboxDataOut                 ^ MaskOut:
	         	                                  32'h00;
// AesCore.v:94 — the unmasked value is what the control block registers
        .DataPathCtrlDat    (DataOut	),
// AesCtrl.v:693, :663 — clocked into the state registers; FirstRound is EN_ROUND0
	SReg00 <= NextSReg00;
assign FirstRound = EnState == EN_ROUND0;
```

**Preconditions.** Power or EM measurement during SCE AES operations under a secret key, plus the ability to supply or observe plaintext/ciphertext — T1 software access to the AIB/AOB segments suffices, and those are a free unlimited chosen-plaintext oracle.

**Attack scenario.**
1. The attacker writes a chosen 128-bit plaintext into AIB (`0x4002_1D00`) and issues `AF_ENC`, or simply observes the victim.
2. During `EN_ROUND0` the datapath evaluates `DataIn ^ RoundKeyIn` with no mask term and the result is latched into `SReg00..SReg33`. The Hamming weight of `P[i]^K[i]` is directly in the trace, per key byte, with no randomisation.
3. Correlating trace samples against `HW(P[i] ^ k)` for `k` in 0..255 recovers round key 0 byte by byte — for AES-128 that is the full cipher key.
4. Alternatively target the round-boundary Hamming distance `HD(SReg_r, SReg_{r+1})`: because lines 171-176 explicitly XOR the mask back out before the value reaches the register, both endpoints of the transition are unmasked, so the classic HD model applies unmodified.
5. During `AF_KS`, the unmasked expanded round key is written into ARAM one word per cycle, a second key-only leakage point requiring no chosen plaintext.

**Impact.** The AES masking countermeasure delivers approximately zero first-order protection. Full key recovery with commodity equipment against a locked-down production part.

**Mitigation (a) — RTL.** Keep the state masked across the register boundary: do not XOR `MaskOut`/`MixMaskOut` back in at `AesDataPath.v:171-176`; instead carry a per-round mask register alongside `SReg00..SReg33`, re-mask each round with a fresh TRNG word, and unmask once, at `EN_STORE`, when ciphertext leaves the engine. Mask the FirstRound AddRoundKey as well. Mask the key-expansion writeback so the schedule is stored masked.

**Mitigation (b) — fabricated silicon.** No firmware action restores the countermeasure. Operational mitigations only: randomise operation timing, insert dummy AES operations with random keys, limit the number of encryptions under any one long-term key (frequent rotation via `AF_KS`), and avoid the SCE AES engine for long-term secrets in physically exposed deployments. The opt-in clock cipher (`docs/src/clock-generation.md:115`) raises the required trace count via misalignment but is defeatable by realignment — and see BAO-065.

**Verification notes.** All quoted lines confirmed. `AesDataPath.v:101` applies the mask at the *input* of the combinational cone, proving the incoming state is unmasked; `AesSbox.v:145` confirms `MaskOut` is the true output mask; `AesMixCol` is GF(2)-linear so `MixMaskOut` is the propagated mask; every active arm re-XORs it. The commented-out block at `AesDataPath.v:165-170`, dated 20221011, shows the mask terms were added on top of an originally unmasked design, consistent with the mask never having been carried through the sequential elements. One line-number correction: the key-expansion writeback `{KReg03,KReg02,KReg01,KReg00}` is the default arm of `AesRamDat` at `AesCtrl.v:997`, not 986.

Both refuters confirmed at high, no dissent. Refuter 1 additionally verified the block is live in the taped-out hierarchy (`daric_top.sv:362 → soc_top.sv:555 → soc_coresub.sv:518 → sce.sv:510 → aes.sv:251 → AesCore.v:102`) and that `AesCore_dummy.sv` is commented out of the build. Refuter 2 established that the compromised boundary is hardware-enforced: `scedma_pkg.sv:305` gives AKEY `8'b01_01_01_01` (AHB write permitted, read denied), and the expanded schedule lives in the AES-private ARAM which software cannot address — so DPA converts a genuine use-but-never-read oracle into key recovery. Refuter 2 corrected one detail of the attack narrative: the `SReg` transition in `EN_ROUND0` is `P → P^K0`, whose Hamming *distance* is `HW(K0)`, constant across traces; the exploitable leakage is the combinational cone and output bus settling to `P^K0`, plus the step-4 round-boundary HD, which is the robust target.

---

<a id="bao-010"></a>

### BAO-010 — AES engine's SCERAM read pointer is loaded from an unbounded software register one cycle before the range clamp, on a port that bypasses `scedma_ac`

**Severity: High | CWE-1285 | Threat actor: T1 (SCE-owning software) | Confidence: High** *(verifier-surfaced)*

**Location:** `rtl/modules/crypto_top/rtl/aes.sv:157`, `:341-342` (also `:323`, `:332`)

**Description.** The third instance of the stale-clamp family, this time on the AES engine's private RAM port. `aes.sv` hands the raw software-written 12-bit segment pointers straight to the DMA channel as the transfer start pointer: `MFSM_LD_IV` uses `chnli_cfg.rpptr_start = cr_segptrstart[PTRID_IV]` with `rpsegcfg = SEG_AKEY`. `cr_segptrstart` is a plain unlocked APB register of full address width. Because the AES channel is wired to `ramreq[12]`/`ramreq[13]`, outside the range `scedma_ac` policies, the AKEY/SKEY/SCRT/PKB read-deny rules never see the request. All segments share one flat address space, so a 12-bit pointer covers the entire crypto RAM.

**Evidence.**
```systemverilog
// aes.sv:157 — full-width, unlocked pointer SFR
    apb_cr #(.A('h30), .DW(scedma_pkg::AW), .SFRCNT(4) )      sfr_segptr    (.cr(cr_segptrstart), .prdata32(),.*);
// aes.sv:338-345 — the raw pointer becomes a SEG_AKEY read start
            MFSM_LD_IV      :
                begin
                    chnli_cfg.wpsegcfg = ld_iv_to_i ? AESSEG_I : AESSEG_IV;
                    chnli_cfg.rpptr_start = cr_segptrstart[PTRID_IV];
                    chnli_cfg.rpsegcfg =    SEG_AKEY;
// sce.sv:377-380 vs :520-522 — the AES port is outside the access-controlled range
        .chnloutreq         ( ramreq[0:CHNLACCNT-1]   ),
            .chnl_rpreq     (ramreq[12]),
            .chnl_wpreq     (ramreq[13]),
```

**Preconditions.** SCE ownership in `mode_sec`. `sfrlock` (`aes.sv:135`) blocks writes only while an operation is in flight, so the pointer is freely programmable between operations.

**Attack scenario.**
1. Load a key the attacker knows into AKEY and run `AF_KS` normally.
2. Select `MODE_CTR`, which sets `ld_iv_to_i = 1` so `MFSM_LD_IV` loads the counter block into `AESSEG_I` from `SEG_AKEY` at `cr_segptrstart[PTRID_IV]`.
3. Write `cr_segptrstart[PTRID_IV]` (`0x4002_D030`) far outside `SEGSIZE_AKEY` — e.g. 2304, so `1792 + 2304` wraps in 12 bits to word 0 (LKEY base). Any word of the crypto RAM is reachable, including SKEY (128–191), SCRT (192–255) and PKB (512–767).
4. Start. The first word of the transfer is read from the wrapped address and becomes word 0 of the AES input block; the clamp then forces the pointer to 0 so words 1–3 come from AKEY.
5. In CTR mode the engine encrypts `AESSEG_I` and XORs the result with the AIB data into AOB. With a known key and chosen plaintext, the attacker computes `AES^-1` and recovers the 32-bit secret word verbatim.
6. Sweep the pointer to dump every key segment. AOB is read-permitted (`8'b10_10_10_10`); the key segments are not.

**Impact.** Repeatable, software-only, 32-bit-at-a-time dump of the entire crypto RAM including SKEY, SCRT, LKEY, KEY and PKB, from the SCE-owning context — defeating the central write-only-key guarantee.

**Mitigation (a) — RTL.** Fix at the source: clamp the loaded value in `sce_dmachnl.sv:123` and `:127` (and use `>=`), which fixes BAO-002, BAO-005, BAO-007 and BAO-010 together. Additionally route the engine ports `ramreq[8..16]` through `scedma_ac`, and bound `segaddr + segptr` in `sce_memc`.

**Mitigation (b) — fabricated silicon.** No lock exists on `cr_segptrstart`. Firmware must treat access to the AES APB page as equivalent to access to all SCE keys, and must not leave key material resident across any window in which less-trusted code can reach `0x4002_D000`.

**Verification notes.** Surfaced by the verifier. Confirmed: `theregrn` is a real async-reset flop so the guard reads the old value; the request is accepted in the presented cycle (`SEG_AKEY.isfifo = '0` so no FIFO pointer substitution; `arbm_gnt` tied 1; `rr_arb_tree` grant combinational; `segrdatvld` hardwired 1); no masking anywhere in `sce_memc` or `cryptoram`; the segment map arithmetic checks out. The block is live in silicon — `aes` is inside `` `ifdef FULL_CHIP `` (`sce.sv:475`), the only occurrence of that macro in the tree, annotated as present in the full chip and excluded only from Verilator.

Both refuters confirmed at high, no dissent. Both independently observed that the defect is broader than `aes.sv`: the scedma `ich` channel takes a software segid *and* a software `rpptr_start`, so the same stale clamp lets an AC-covered channel declare a read-allowed segid while the pointer wraps into SKEY/SCRT/PKB — `scedma_ac.sv:45-46` keys only off `segcfg.segid` and never off the resulting address. The correct fix therefore belongs in `sce_dmachnl.sv`, not in the engines. Refuter 2 narrowed the attacker correctly: not generic unprivileged software, but the SCE-owning `coreuser` domain in secure mode — which is precisely the party ACRULEs exists to constrain.

---

<a id="bao-011"></a>

### BAO-011 — Montgomery multiplier's final reduction is data-dependent in time: a per-multiplication extra-reduction timing oracle on RSA/ECC private operations

**Severity: High | CWE-208 (Observable Timing Discrepancy) | Threat actor: T1 (timing) or T2 (power/EM) | Confidence: High**

**Location:** `rtl/modules/crypto_pke/rtl/mimm.sv:338-342`, `:347-357`

**Description.** `mimm_sub` implements the conditional final subtraction of the Montgomery product as a two-phase FSM, and both phases are data-dependent. `MFSM_SUB0` compares the accumulator against the modulus MSW-first and terminates at the first differing word. `MFSM_SUB1` is skipped entirely when the accumulator is less than the modulus; when not skipped it runs `dblen` cycles (33 words for a 2048-bit modulus, 65 for 4096-bit) and then loops *back* to `SUB0` for a second full compare. A single Montgomery multiplication therefore takes either `T` or roughly `T + dblen + 2·compare` cycles depending purely on whether the un-reduced product exceeded the modulus. `done` propagates to `ModMulDone`/`MpcDone`, which every state of the RSA exponentiation ladder and the ECC point-multiply waits on. The total exponentiation time is the sum of hundreds of one-bit "did an extra reduction happen" events — precisely the Walter/Schindler extra-reduction oracle.

**Evidence.**
```systemverilog
// mimm.sv:319-320 — the operation being timed
    // if da >= db, dy = da - db;
    // if da <  db, no change
// mimm.sv:338-342 — SUB1 is skipped on one branch and loops back to SUB0 on the other
    assign mfsmnext = start ? MFSM_SUB0 :
                         (( mfsm == MFSM_SUB0 ) &&  mfsm_sub0done ) ? MFSM_SUB1:
                         (( mfsm == MFSM_SUB1 ) &&  mfsm_sub1done ) ? MFSM_SUB0:
                         (( mfsm == MFSM_SUB1 ) &&  sub1skip ) ? MFSM_DONE :
                         ( mfsm == MFSM_DONE ) ? MFSM_IDLE : mfsm;
// mimm.sv:348-354 — early exit at the first differing word; skip flag is the comparison result
    assign sub0cmpdone = ( mfsm_sub0cycpl2 == dblen - 1 ) |
                         ( areg != breg ) & mfsm_sub0pl2;
    `theregrn( sub1skip ) <= start | done? 0 :
                             ( areg < breg ) & mfsm_sub0pl2 & mfsm_sub0 ? '1 :
                             ( mfsm_sub0cycpl2 == dblen - 1 ) & ( areg == breg ) ? '1 : sub1skip ;
// PkeCore.sv:373, :343 — done reaches the ladder
        . done(ModMulDone_s1),
assign ModMulDone = ModMulDone_s0 | ModMulDone_s1;
```

**Preconditions.** Firmware must select the parallel Montgomery multiplier by setting `mimmcr[8]` (`sfr_mimmcr` at `0x4002_C024`, a plain unlocked CR resetting to 0). The alternative `mgmr_mul` path does **not** have this defect. The attacker must observe operation duration — `sfr_tickcnt` (BAO-094) provides this with zero noise.

**Attack scenario.** The victim performs an RSA-CRT signature or ECDSA scalar multiply with `mimmcr[8] = 1`. The attacker issues chosen ciphertexts and, for each, reads the exact operation duration from `sfr_tickcnt` at `0x4002_C054` or by polling `sfr_srmfsm`. Each ladder multiplication either performs the final subtraction (~+35 cycles at 2048-bit, ~+67 at 4096-bit) or does not, and the probability is a known monotone function of how close the operand is to the modulus. Submitting inputs clustered just below multiples of the secret CRT prime `p` produces a sharp drop in measured time at the multiples of `p`; a binary search recovers `p`, factoring `N`. For ECC the equivalent per-multiplication timing yields the scalar.

**Impact.** RSA private-key recovery by factoring `N`, or ECDSA scalar recovery, from a chosen-input signing oracle plus timing — no fault injection and no physical access. Unpatchable in silicon.

**Mitigation (a) — RTL.** Make the final reduction unconditional and constant-time: always perform the full `dblen`-word subtraction and select between the subtracted and unsubtracted result with a borrow-driven mask, rather than skipping `SUB1`. Remove the early-exit term from `sub0cmpdone` so the compare always scans all words. This is exactly what the design's own `mgmr_mul` already does (`mgmr_mul.v:464` always launches a `com_alg` operation, and `com_alg.v:153-168` runs the full word count for every mode) — `mimm_sub` is a regression against the team's own in-repo pattern.

**Mitigation (b) — fabricated silicon.** Fully mitigable in firmware. Either (a) leave `mimmcr[8] = 0` so the constant-time `mgmr_mul` path is used for all private-key operations, accepting the throughput loss; and/or (b) apply base blinding (multiply the input by `r^e mod N` before, `r^-1` after) and exponent blinding (`d + k·φ(N)`) with fresh randomness per operation, so the extra-reduction pattern is decorrelated from both input and exponent. For ECC use scalar blinding and projective-coordinate randomisation.

**Verification notes.** All quoted lines confirmed verbatim. The FSM was independently traced: `mimm.sv:116-117` routes to `MFSM_SUB` only after `lastrnd`, so this is the single conditional reduction per multiply; with `sub1skip` set the FSM falls through in one cycle, without it, it runs the full borrow subtract and then a second compare pass. The contrast with `mgmr_mul` was verified. `mmsel = mimmcr[8]` is a plain `apb_cr` resetting to 0, so the exposure requires firmware opt-in.

Both refuters confirmed. **Dissent on exploitability:** refuter 1 rated it *difficult*, solely because the vulnerable multiplier is not the reset default and the attacker does not choose that bit; refuter 2 rated it *practical*, arguing that `mimm` is the PL=4 parallel datapath and therefore the only performance-viable choice for RSA-2048/4096, that there is no lock bit and no documentation warning, and that `sfr_tickcnt` gives a cycle-exact noise-free oracle. Both agreed on high severity. We report **high**, and the vendor should determine empirically whether shipped firmware sets `mimmcr[8]`. Refuter 1 also verified that `opt_sec`/`db_rnd` (`mac_cell.sv:49-53`) is a power/EM dummy-activity measure inside the multiplier array and cannot influence reduction timing — `mimm_sub`'s port list has no such input.

---

<a id="bao-012"></a>

### BAO-012 — SCE trust state (and therefore ReRAM key-slot unlock) is forgeable: the HMAC key, the expected digest and the unlocked key index are all attacker-chosen unlocked registers with no binding

**Severity: High | CWE-807 (Reliance on Untrusted Inputs in a Security Decision) | Threat actor: T1 (SCE-owning software); glitch variant T2 | Confidence: High**

**Location:** `rtl/modules/crypto_top/rtl/combohasha.sv:218`, `:221`, `:477`, `:490`, `:645`; consumed at `sce_sec.sv:117`, `rrc.sv:717`

**Description.** The `HF_HMAC*_PASS2` + `scrtchk` flow produces `hmac_pass`/`hmac_kid`, which `sce_sec.sv:117` turns into `tsreg[hmac_kid]`, which becomes `truststate`, which `rrc.sv:717` consumes as the `!trustkey[akeyid]` term authorising access to a ReRAM key slot. The intended property is "a ReRAM key slot only unlocks after the hardware verifies an HMAC computed with a secret the CPU cannot forge". Every input to that decision is software-controlled and none are bound to each other:

- **which key is used** is the software bit `opt_ifskey`, selecting SEG_SKEY (unreadable) or SEG_KEY (freely bus-writable);
- **where the expected digest comes from** is the software bit `tsmode`, selecting the ReRAM key store or the bus-writable SEG_SCRT;
- **which trust bit is set** is the 10-bit software CR `sfr_keyidx`, forwarded verbatim as `hmac_kid` with nothing correlating it to the key actually hashed;
- `sce_sec.sv:117` accepts `hmac_pass` identically regardless of `tsmode`/`ifskey`, and `sce_ts` is reset by the **system** reset rather than `sceresetn`, so a forged bit survives `sfr_arrst`, `sfr_arclr` and mode-quit.

The comparison itself is a single non-redundant bit initialised to PASS, with no re-check.

**Evidence.**
```systemverilog
// combohasha.sv:218, :221 — tsmode, ifskey and the trust index are plain unlocked CR bits
    apb_cr #(.A('h14), .DW(7))       sfr_opt2       (.cr({cr_opt.ifskey,tsmode,opt_schnr[1:0],cr_opt.ifstart,cr_opt.ifsob,cr_opt.scrtchk}), .prdata32(),.*);
    apb_cr #(.A('h60), .DW(10))       sfr_keyidx     (.cr(kid), .prdata32(),.*);
// combohasha.sv:645 — software picks whether the SECRET key is used at all
                    chnli_cfg.rpsegcfg = opt_ifskey ? SEG_SKEY : SEG_KEY;
// combohasha.sv:477 — software picks ReRAM key store vs bus-writable SEG_SCRT
    assign chnlscrt_wpreq = tsmode ? chnlis_wpreq : chnli_wpreq;
// combohasha.sv:480-490 — one non-redundant bit seeded to PASS; kid forwarded verbatim
    `theregrn( chkprepass ) <=  ~mfsmcheckscrt ? '0 :
                                mfsmtog & mfsmcheckscrt ? '1 :
                                schxwpreq.segwr | chnli_wpreq.segwr ? chkprepass && ( chnlscrt_wpreq.segwdat == '0 ) : chkprepass;
    assign hmac_kid = kid;
// sce_sec.sv:117, :123 — no check of tsmode/ifskey; MSB hardwired trusted
    `theregrn( tsreg[i] ) <= ((hmac_kid==i)&mode_sec & hmac_pass) ? 'b1 : ((hmac_kid==i)&mode_sec & hmac_fail) ? 'b0 : tsreg[i];
    assign ts = { 1'b1, tsreg };
```

**Preconditions.** The attacker must be the SCE owner in `mode_sec`. `scemode` is write-once-from-zero (reset 0) and the owning `coreuser` is latched from whichever master last did an AHB address phase before the transition, so the first code to program `scemode` after any `sysresetn` wins. No physical access and no knowledge of any real secret is required.

**Attack scenario.**
1. Pick an arbitrary HMAC key K and message M; compute `T = HMAC-SHA256_K(M)` on the CPU.
2. Write K into SEG_KEY (`0x4002_0100`) and T into SEG_SCRT (`0x4002_0300`) — both AHB-writable per ACRULEs `8'b01_01_01_01`.
3. Program `SFR_OPT2` (`0x4002_B014`) with `ifskey = 0` (use the bus-writable key, not the unreadable SKEY), `tsmode = 0` (compare against SEG_SCRT, not the ReRAM key store), `scrtchk = 1`.
4. Write `SFR_KEYIDX` (`0x4002_B060`) = N, the `akeyid` of the target ReRAM slot.
5. Run `HF_HMAC256_PASS1` then `PASS2`. PASS2 reaches `MFSM_LD_SECRET`, XORs the computed tag against SEG_SCRT, finds all zero, and `chkpass` asserts.
6. `hmac_pass` with `hmac_kid = N` sets `tsreg[N] = 1`; confirm via `sfr_ts` at `0x4002_80e0`.
7. `truststate[N]` now feeds `rrc.sv:717`, removing the trustkey gate on every ReRAM slot whose descriptor carries `akeyid == N`.
8. Because `sce_ts` is on the system reset, the forged bit survives `sfr_arrst`/`sfr_arclr`/mode-quit — the attacker can drop the SCE back to a non-secure mode and the unlock persists.

**Impact.** The device's cryptographic attestation gate is bypassed with attacker-chosen key, message and expected tag, in software, with no secret knowledge. Note the trustkey term is one of several OR'd error terms for key slots — the `coreuser`/`userid_k` match, per-slot disables and keytype match still apply — so for key slots this defeats a *second factor*. Where trustkey is the **sole** gate is `rrc.sv:761-763`: forging `trustkey[3]`/`[5]`/`[7]` fully removes ReRAM code-region blocking for boot1/fw0/fw1 when `tkey_en` is set, i.e. it defeats an attest-before-execute control.

**Mitigation (a) — RTL.** (1) Qualify `hmac_pass` with the mode that produced it — export `tsmode`/`opt_ifskey` alongside it and have `sce_sec.sv:117` set `tsreg` only when the compare was against the ReRAM key store **and** the key came from SEG_SKEY. (2) Derive `hmac_kid` from the same `kid` that generated `schcrx.axstart` rather than from a live CR, and lock `sfr_keyidx` for the operation. (3) Make the comparison redundant — keep a complemented pass bit and a compared-word counter and require `chkpass && ~chkfail && (words == STSIZE)`. (4) Move `sce_ts` onto `sceresetn`. (5) Drop the hardwired `1'b1` MSB.

**Mitigation (b) — fabricated silicon.** Do not rely on `truststate` for any authorisation. Give every sensitive ReRAM key slot a non-zero `userid_k[7:4]` and rely on the `coreuser` check rather than the trustkey term. Choose `akeyid` values only from indices you can prove are never set — note `akeyid` 255 is permanently trusted by construction, so never use it. The boot ROM must claim SCE ownership by writing `scemode` before any other code runs, and must never hand ownership to code not already entitled to every key slot.

**Verification notes.** All quoted lines confirmed verbatim, including `sce.sv:298` where `sce_ts` is instantiated with a bare `.resetn,` while every sibling block uses `.resetn(sceresetn)`. Both SEG_KEY and SEG_SCRT carry `accessrule 8'b01_01_01_01` — AHB-writable, not readable — so the attack materials can be planted as described. `soc_coresub.sv:546/836` confirms `truststate` reaches the RRC. Line-number corrections: the ACRULEs entries are `scedma_pkg.sv:293` and `:295`. The finder's "unlock a ReRAM key slot" framing was corrected as above; severity was lowered from critical to **high** on that basis plus the SCE-ownership precondition.

Both refuters confirmed at high, no dissent. Refuter 1 established that the ownership precondition is *weaker* than stated: `sfr_arrst` drives `sceresetn`, clearing `scemode` to 0 and re-opening the claim, so this is not a one-shot boot race. Refuter 2 verified the `tsmode = 1` path is genuinely bound (the compare source is the ReRAM key store at `PM_KS_BA + kid*32`, so `kid` does bind there) and that only the `tsmode = 0` path is forgeable — which is why the fix must qualify on `tsmode`. Refuter 2 also confirmed `rrc.sv:719-720` shows the `rrccr[10]` enable was removed by ECO, so the trustkey term is always in force for key slots ≥ 2.

---

<a id="bao-013"></a>

### BAO-013 — HMAC trust check completes on a shared, software-startable DMA done pulse while the compare accumulator is still seeded to PASS

**Severity: High | CWE-1264 / CWE-1245 | Threat actor: T1 (SCE-owning software) | Confidence: High** *(verifier-surfaced)*

**Location:** `rtl/modules/crypto_top/rtl/combohasha.sv:479-490`, `:456-457`; `sce.sv:441`; `scedma.sv:226-228`; `scedma_amba.sv:379-380`

**Description.** The completion condition for the HMAC/secret comparison that drives `truststate` is `chkdone <= mfsmcheckscrt & (schdonex|chnli_done)`, while the compare accumulator is seeded to PASS on entry to `MFSM_LD_SECRET` and only ever degraded by a write strobe. **Nothing counts how many words were actually compared.** `schdonex` is not private to the hash engine: `sce.sv:441` drives it from `sdma_done[1]`, the shared secure DMA channel's done, which is directly startable from software. Worse, the takeover is not exclusive: `scedma.sv:226-228` mux the channel combinationally on `schcrxsel`, while `scedma_amba.sv:379` gates the channel start with `chnli_start = startr & ~busy`. If a software-initiated `sch` transfer is still in flight when combohash raises `schcrxsel`/`schstartx`, combohash's start is silently swallowed while the in-flight transfer keeps running — and its completion pulses `done`, which reaches combohash as `schdonex`, sets `chkdone` with `chkprepass` still at its seeded `'1`, and sets `tsreg[hmac_kid]` for the attacker-chosen kid. The trust decision is reached without a single word of the expected digest being compared, and this holds in the `tsmode = 1` configuration that is supposed to be the trustworthy one.

**Evidence.**
```systemverilog
// combohasha.sv:479-490 — accumulator seeded to PASS; done has no compared-word count
    assign mfsmcheckscrt = ( mfsm == MFSM_LD_SECRET );
    `theregrn( chkprepass ) <=  ~mfsmcheckscrt ? '0 :
                                mfsmtog & mfsmcheckscrt ? '1 :
                                schxwpreq.segwr | chnli_wpreq.segwr ? chkprepass && ( chnlscrt_wpreq.segwdat == '0 ) : chkprepass;
    `theregrn( chkdone ) <= mfsmcheckscrt & (schdonex|chnli_done) ;
    assign chkpass = chkdone && chkprepass;
// combohasha.sv:456-457 — takeover is combinational, start is one cycle later
    assign schcrxsel = tsmode & mfsmcheckscrt;
    `theregrn( schstartx ) <= mfsmtog & mfsmcheckscrt & tsmode;
// sce.sv:441 and scedma.sv:123 — schdonex is the SHARED channel's done
    assign hash_schdonex = sdma_done[1];
    assign fr_sdma = { xchdone, schdone, ichdone };
// scedma_amba.sv:379, :484 — combohash's start is dropped if busy, but done still propagates
    assign chnli_start = startr & ~busy;
    assign done = chnli_done | chnlo_done;
```

**Preconditions.** SCE ownership in `mode_sec`. The scedma SFRs have no lock (`scedma.sv:91`, `assign sfrlock = 0;`) and no busy interlock exists on either the DMA start or the hash start.

**Attack scenario.**
1. Program the scedma secure channel (`sch`) for a long outbound transfer — `cr_func = 1` (SCERAM → AXI) is the reliable variant, because for an outbound transfer the module's external `wpreq` is `chnli`'s and an idle `chnli` never asserts `segwr`, so `chkprepass` can never be degraded. Start it; `schbusy` goes high.
2. Write `COMBOHASH_SFR_KEYIDX` = N, `SFR_OPT2` with `tsmode = 1` and `scrtchk = 1`, and run `HF_HMAC256_PASS1` then `PASS2` over any message with any key.
3. PASS2 reaches `MFSM_LD_SECRET`. `schcrxsel` asserts combinationally, swapping the in-flight transfer's config to combohash's (including `transsize = STSIZE`); `schstartx` asserts one cycle later and is dropped because the channel is busy — so the real trust-check DMA never starts and no ReRAM word is ever fetched.
4. The in-flight transfer's next completed beat pulses `done` → `schdonex` → `chkdone = 1` with `chkprepass` still `'1`. `chkpass` asserts.
5. `hmac_pass` with `hmac_kid = N` sets `tsreg[N]`. Confirm by reading `sfr_ts`. On a miss, the hash FSM stalls in `LD_SECRET` (no `chkfail`, no error, no attempt counter); clear with `sfr_arrst` and retry with a different delay. The hardware is synchronous and deterministic, so sweeping the inter-write delay over a few hundred cycles is a guaranteed hit.
6. Because `sce_ts` is on the system reset, the forged bit outlives the attacker's ownership.

**Impact.** As BAO-012, but in the configuration the design treats as authoritative, and without needing control of SEG_SCRT or SEG_KEY. Defeats the "prove you hold the authentication key" factor for ReRAM key slots and for the boot1/fw0/fw1 code-region trustkey gates.

**Mitigation (a) — RTL.** `chkdone` must require a compared-word count equal to `STSIZE`. The trust check must own the `sch` channel exclusively — reject or defer `schcrxsel` while `schbusy`, and fail *closed* if `schstartx` is swallowed by `startr & ~busy`. Latch `transsize`/`opt`/`axstart` at takeover rather than muxing them live.

**Mitigation (b) — fabricated silicon.** Firmware must never leave the `sch` channel busy across an HMAC trust check, and must not expose the scedma or combohash APB pages to code that is not already fully trusted. Because there is no attempt counter and no error, firmware cannot detect attempts. As with BAO-012, do not rely on `truststate` for authorisation.

**Verification notes.** Surfaced by the verifier. All lines confirmed verbatim, including that `cmd`-style qualification is absent from `chkdone`, that `sfrlock` is 0 in scedma, and that `truststate` reaches `rrc.sv:717` and `:761-763`.

Both refuters confirmed at high, no dissent — but both independently **refuted the original inbound (`cr_func = 0`) attack narrative** and supplied the corrected outbound variant used above. For an inbound transfer, `done` always coincides with a `wpwr` beat, which asserts `segwr` and folds a keystore word into `chkprepass`, so the attacker cannot force a pass that way. Refuter 1 additionally identified a second working variant: because the `mfsmtog` seed at line 481 has *priority* over the compare at line 482, a software `sch` done landing in cycle 0 of `MFSM_LD_SECRET` force-seeds `chkprepass` to `'1` even if that beat's data is non-zero, while `chkdone` is set the same cycle — zero effective compares. Refuter 2 also corrected the finder's claim about the live `transsize` mux widening the window: `TRANSCNTW = 30`, so once `transcnt > 7` the wrap requires 2^30 beats; the window is one beat wide, not wide open, but is freely retryable.

---

<a id="bao-014"></a>

### BAO-014 — Default TRNG post-processing is a bare 129-bit LFSR that publishes its entire internal state as the random output, with no entropy compression

**Severity: High | CWE-338 (Weak PRNG) | Threat actor: T1 | Confidence: High**

**Location:** `rtl/modules/crypto_trng/rtl/lfsr129.v:88-107`; selected at `postprocess.v:156`; default set by `trng.sv:110`

**Description.** `cr_postproc` is an `apb_cr` with default `IV = '0`, so at reset `postprocess_opt == 0` and `postprocess.v:156` selects `lfsr_dataout[127:0]` as the SoC's random output — which is literally the LFSR state (`assign lfsr_dataout = lfsr_chain[127:0];`). Three consequences follow directly. **(1) State disclosure:** a single 128-bit word publishes 128 of the 129 state bits. **(2) No entropy compression:** `lfsr_cnt` advances one step per `digi_data_vld` and the word is declared valid at count 128, so exactly 128 raw digitised bits are absorbed per 128 output bits, and the mixing `{lfsr_chain[127:0], lfsr_out^digi_data_out}` is a bijective GF(2)-affine map. A conditioner that is invertible and 1:1 cannot increase entropy density: the min-entropy of a "128-bit random word" equals that of 128 raw ring-oscillator samples, typically well under 1 bit/sample. SP 800-90B requires a vetted conditioning function with compression; there is none. **(3) No reseed in the default config:** `reseed_interval` is 0 at reset and the reseed counter is gated on `(reseed_interval != 2'h0)`, so the LFSR is seeded once and never re-seeded.

**Evidence.**
```systemverilog
// lfsr129.v:100 — the output IS the state
assign lfsr_dataout     = lfsr_chain[127:0];
// lfsr129.v:91 — invertible 1:1 mixing, one raw bit absorbed per shift
                          (rngcore_en_lfsr&   lfsr_stable  &  (~lfsr_dataout_vld) & (~trng_drng_sel) & digi_data_vld) ? {lfsr_chain[127:0],lfsr_out^digi_data_out}:
// lfsr129.v:96-98, :102 — 128 raw bits per 128 output bits
assign lfsr_cnt_pre     = (~rngcore_en_lfsr| ~lfsr_stable |rngcore_rddone) ? 8'h0 :
                          ((lfsr_cnt<8'd129)&(~trng_drng_sel)&digi_data_vld) ? (lfsr_cnt +1'b1):lfsr_cnt;
// lfsr129.v:105-107 — reseed disabled when reseed_interval == 0, its reset value
assign reseed_cnt_pre       = (~rngcore_en_lfsr)|(buf_ready & post_read_lfsr) ? 14'd0 :
	                      (lfsr_dataout_vld & ~lfsr_dataout_vld_pre & (reseed_interval!=2'h0)& ...
// postprocess.v:156 — mode 0 is the reset default
assign rngcore_dataout    =(postprocess_opt==2'd0)? lfsr_dataout[127:0]  :
```

**Preconditions.** Firmware uses the reset default `postprocess_opt = 0` — the state of an uninitialised or partially-initialised boot path. Reading the RNG pool needs bus access to SCERAM, unrestricted while `scemode == 0`. Even with no attacker, the 1:1 no-compression property alone caps every generated key's real entropy at the raw min-entropy of 128 oscillator samples.

**Attack scenario.** Firmware leaves `cr_postproc` at its reset value and issues `ar_start`. Generated words are DMA'd into SEG_RNGA/RNGB at `0x4002_1F00`–`0x4002_26FF`, which permit AHB read and which the crypto-RAM wipe explicitly excludes (BAO-004). An unprivileged attacker reads one word and obtains 128 of the 129 state bits, i.e. the exact linear evolution of the generator. Every subsequent output differs from the predicted pure-LFSR word only by the 128 raw entropy bits absorbed; with a source at, say, 0.1 bit/sample, the next word carries ~12.8 bits of entropy and is brute-forceable in ~10^4 tries. The victim's next draw is used to generate a key; the attacker enumerates candidates offline and tests each against any public artefact. Combined with a stalled noise source (BAO-015, BAO-017), the residual is zero and the next key is computed deterministically.

**Impact.** Key material generated in the default configuration carries far less entropy than its width implies, and the generator's state is directly readable from the output pool.

**Mitigation (a) — RTL.** Never emit the raw LFSR state: remove `postprocess_opt = 0`, or make `lfsr_dataout` the output of a one-way compression over at least twice as many raw bits as output bits. Make CTR_DRBG (`postprocess_opt = 2`) the reset default and the only non-debug mode; hardwire a minimum 2:1 compression ratio; and force a re-seed from a freshly filled 256-bit `buf_data` before every output word rather than gating the reseed on a software field that defaults to "disabled".

**Mitigation (b) — fabricated silicon.** (1) The boot ROM must write `cr_postproc` with `cr_postproc_opt = 2'd2` and a non-zero `cr_reseed_intval` **before** the first `ar_start`, and verify the read-back. (2) Treat every 128-bit word from RNGA/RNGB as raw entropy worth far less than 128 bits — collect at least eight words and compress through a software SHA-256/SHA-3 before using any of it as key material. (3) Zeroise RNGA/RNGB in software after every draw (BAO-004).

**Verification notes.** All quoted lines confirmed. The 128:128 absorption ratio and the reseed-disabled behaviour were re-derived from the counter equations. `cr_postproc` was confirmed to be an `apb_cr` with `parameter IV=32'h0`. The read-back path was confirmed: RNGA/RNGB rule `8'b10_11_10_10` grants AHB read, and `acenable = mode_sec` means the rule table is not even applied unless `scemode[1]` is set. One mechanism claim in the original was **corrected**: the assertion that two consecutive words reveal all 129 bits is wrong in TRNG mode — after the 128 shifts producing word N+1, bit[128] equals word N's bit[0], a bit already known, and the unknown bit remains entangled with an unknown entropy bit. That claim holds only in DRNG mode. This does not change the finding: one word already publishes 128 of 129 bits, and the 1:1 absorption caps the min-entropy of every output at (raw min-entropy of 128 samples + 1 bit). Severity was lowered from critical to **high** because mode 0 is firmware-selectable (albeit the reset default) and the strongest consequence needs both a low-entropy source and pool read access.

---

<a id="bao-015"></a>

### BAO-015 — LFSR zero-state guard reloads a hard-coded compile-time constant, converting a dead or software-zeroed entropy source into a fixed, publicly computable random sequence

**Severity: High | CWE-1241 | Threat actor: T1 for the active variant, T2 or plain firmware error for the passive | Confidence: High**

**Location:** `rtl/modules/crypto_trng/rtl/lfsr129.v:88`; enabling register at `rtl/modules/crypto_top/rtl/trng.sv:120`, `:52`

**Description.** `lfsr129.v:88` handles the all-zero LFSR state by reloading a constant that is also the reset value: `129'h1_A39A8864_5DF3BECE_074EC5D3_BAF39D18`. This is a silent known-answer fallback, not an error. It is reachable in normal operation because the seed is `buf_data[255:127]`, and `buf_data` is all zeros whenever the digitised bit stream is stuck at 0 — `data_buf.v:79` shifts `digi_data_out` in, so 256 zero bits produce a zero seed while `buf_cnt` still reaches 256 and `buf_ready` still asserts. The sampled datum is trivially forced to 0: `trng.sv:228` ANDs the 128 buffer-chain taps with `rngchainen`, which is `sfr_chain`, an `apb_cr` at offset 0x40 whose default IV is `'0` and whose `sfrlock` is hardwired to `'0`. With `rngchainen == 0` the XOR reduction is over an all-zero vector, so every sampled bit is 0 and `digi_data_out` is constant. Result: zero seed → guard fires → LFSR loaded with the constant → 128 shifts with a constant-0 entropy input → a 128-bit "random" word identical on every chip and every boot, computable offline from this source file.

**Evidence.**
```systemverilog
// lfsr129.v:88-89 — zero-state fallback is the same constant as the reset value (line 66)
assign lfsr_chain_pre   = (|lfsr_chain==1'b0) ? 129'h1_A39A8864_5DF3BECE_074EC5D3_BAF39D18:
	                  (rngcore_en_lfsr& (~lfsr_stable) &  buf_ready & post_read_lfsr) ? buf_data[255:127]:
// trng.sv:228 — the entropy sample is ANDed with a software register
    assign rngclkhfxor = ^( {rngchain0[CHAINW/2:1],rngchain1[CHAINW/2:1]} & rngchainen[CHAINW-1:0] );
// trng.sv:120, :52 — that register is unlocked and defaults to zero
    apb_cr #(.A('h40), .DW(32), .REVY(1), .SFRCNT(CHAINW/32) )      sfr_chain       (.cr(rngchainen), .prdata32(),.*);
    `theregrn( sfrlock ) <= '0;
// data_buf.v:79, :101 — an all-zero stream still produces a "ready" seed
        buf_data_pre[255:0] = {buf_data[254:0],digi_data_out};
```

**Preconditions.** Active variant: any bus write to `0x4005_E040`… (correctly, `0x4002_E040`–`0x4002_E04C`), unrestricted while `scemode == 0`. Passive variants: a dead source, or firmware that enables the oscillators but never writes `sfr_chain`. No attacker needed for the latter.

**Attack scenario.** An unprivileged task writes `0x0000_0000` to the four words of `sfr_chain` at `0x4002_E040`. `rngclkhfxor` becomes constant 0, every sampling flop latches 0, and `digi_data_out` is constant. The victim then generates keys: `data_buf` fills with 256 zeros, `buf_ready` asserts, the LFSR is seeded with 0, the zero-state guard reloads the constant, and the output word is one the attacker computed offline from this file. Every key derived from it is known before it is generated. The passive variant — ring oscillators failing, or frozen by EM/thermal attack, or firmware simply never writing `sfr_chain` — produces the identical fixed sequence silently, with no error indication anywhere.

**Impact.** Fully predictable key material, on every unit, with no alarm. The guard's real harm is that it *masks* the dead-source condition behind a plausible-looking but publicly computable sequence rather than producing an obvious all-zero tell.

**Mitigation (a) — RTL.** An all-zero LFSR state must be a fatal error, not a reload: replace the fallback with an error latch that forces `rngcore_dataout_vld` and `chnlo_start` low and asserts `err`. Refuse to seed at all if `buf_data` is all-zeros or all-ones, and require the startup health test to pass before `buf_ready` may assert. `rngchainen` must not be able to zero the source — hardware-force a minimum tap count by ORing a non-zero constant mask — and the TRNG needs a real `sfrlock` so boot code can lock the entropy configuration.

**Mitigation (b) — fabricated silicon.** The boot ROM must (1) program `sfr_chain` with a validated non-zero tap mask, (2) read back and verify `sfr_chain`, `cr_src` and `cr_ana` before every key generation, (3) compare the first generated word against the known constant sequence derived from `129'h1_A39A8864_...` and hard-fault on a match, and (4) because the registers cannot be locked, re-verify immediately before and after each draw and discard the batch on change.

**Verification notes.** All lines confirmed verbatim, including that `(|lfsr_chain==1'b0)` parses as `(|lfsr_chain) == 1'b0` and is the highest-priority mux term. The forcing path and the "ready with a zero seed" behaviour were traced end to end. Address correction: `sfr_chain` has `SFRCNT = 4`, so it occupies `0x4002_E040`–`0x4002_E04C`. Two framing corrections: without the guard a zero seed would produce an all-zero output, which is equally predictable — the guard's harm is concealment, not creation; and the "active variant" is the same root cause as BAO-017 rather than an independent primitive. Severity lowered from critical to **high** accordingly.

---

<a id="bao-016"></a>

### BAO-016 — Raw pre-conditioning entropy and the live DRBG seed are directly readable over an unlocked APB register

**Severity: High | CWE-200 (Exposure of Sensitive Information) | Threat actor: T1 | Confidence: High**

**Location:** `rtl/modules/crypto_top/rtl/trng.sv:278`, `:58`, `:432-443`

**Description.** `data_buf`'s `buf_data` register is simultaneously (a) the shift register into which every unconditioned digitised entropy bit is clocked and (b) the seed material for all three post-processing modes — loaded into the LFSR state, used directly as the AES key and plaintext in mode 1, and XORed into the CTR_DRBG's initial key and counter in mode 2. `trng.sv:278` exposes it through `apb_buf` at offset 0x30 and `trng.sv:58` ORs its read data into the module's `prdata`, so eight reads return the full 256 bits. The read path has no privilege or lock check (`sfrlock` is hardwired 0). There is no separation between a "raw entropy debug tap" and normal operation: the window is live at all times, in USER mode, with no lifecycle gate. SP 800-90B forbids outputting raw entropy from a validated source.

**Evidence.**
```systemverilog
// trng.sv:278, :58 — the window and its read-back
    apb_buf  #(.BAW(3), .A(12'h30), .DW(32) ) sfr_buf (.prdata32(),.*);
                        | sfr_buf.prdata32
// trng.sv:434, :439, :443 — no lock on the read path; auto-incrementing address
    assign apbrd = ~sfrlock & apbs.psel & apbs.penable & ~apbs.pwrite;
    `theregrn( buf_addr ) <= buf_addr + buf_write + buf_read;
    assign prdata32 = sfrsel ? buf_dataout : '0;
// data_buf.v:79 — this is the unconditioned entropy shift register
        buf_data_pre[255:0] = {buf_data[254:0],digi_data_out};
// ctr_aes.v:163, :171 — the same register is the CTR_DRBG seed
assign aes_key_pre    =((ctr_state==IDLE  )&(ctr_state_nxt==RESEED)) ? K0                   ^buf_data[255:128]^personalization_string[255:128]:
assign aes_text_in_pre=((ctr_state==IDLE  )&(ctr_state_nxt==RESEED)) ?(M0                   ^buf_data[127:0]  ^personalization_string[127:0])+1'b1:
```

**Preconditions.** Any bus read of `0x4002_E020`–`0x4002_E03F`, unrestricted while `scemode == 0`. No lifecycle/CMS gate exists in any mode.

**Attack scenario.** An unprivileged task polls the window while a victim generates a key. `buf_addr` auto-increments per read, so eight reads recover the full 256-bit seed. In `postprocess_opt = 2` the attacker now knows `buf_data`; `K0`/`M0` are compile-time constants in this file and `personalization_string`/`additional_input_*` are themselves software registers, so the DRBG's initial key and counter are reconstructed exactly and every subsequent output computed offline. In mode 1 the exposure is total in one step — the output is `AES(buf_data[255:128], buf_data[127:0])`. In the default mode 0 the seed gives the complete initial LFSR state and, with the 1:1 mixing of BAO-014, the entire output stream. Independently, the same window is a raw-entropy oscilloscope for characterising the source's bias and its response to injected EM/clock — the calibration step for the physical attacks above.

**Impact.** Direct disclosure of the generator seed and of unconditioned entropy to any bus master, in production silicon, with no gate.

**Mitigation (a) — RTL.** Remove the raw-entropy read-back from production silicon, or gate `apb_buf`'s read path on a test-mode lifecycle signal so it is dead in USER mode; and separate the raw-entropy accumulator from the seed register so the seed is never software-visible. At minimum give the TRNG a real `sfrlock` so boot code can lock the whole page.

**Mitigation (b) — fabricated silicon.** No fully effective mitigation, because the window has no lock. Partial: (1) leave `scemode == 0` for the shortest possible window — enter a non-zero mode early so `sce_sec`'s `ahben` restricts the page to the owning core's `coreuser`; (2) generate all key material in a window in which no untrusted code is scheduled on either CPU; (3) derive keys by hashing TRNG output together with a ReRAM-resident device secret, so knowledge of `buf_data` alone does not yield the key.

**Verification notes.** All lines confirmed; `apb_buf` has no lock and no privilege term, and no `cmstest`/`cmsbist`/`devmode` gate exists anywhere in `trng.sv`. The exposure is **broader than reported**: `apb_buf` decodes `paddr[11:5] == 7'h01`, i.e. `0x4002_E020`–`0x4002_E03F` — twice the eight-word region it is sized for — overlaying the three `apb_shfin` registers at 0x20/0x24/0x28 (personalization string and additional inputs), which contribute no read data of their own. Reading any of those addresses therefore also returns `buf_data`. See BAO-049 for the write-side consequence. One claim was corrected: because `buf_addr` is a free-running counter incremented by every read *and* every write in the whole 0x20–0x3F window, its phase is not attacker-known a priori, so "seven reads without perturbing the ready handshake" is only conditionally true — eight reads recover all 256 bits regardless.

---

<a id="bao-017"></a>

### BAO-017 — Every TRNG control register is permanently unlocked, letting unprivileged software switch the generator into deterministic DRNG mode with an attacker-chosen 256-bit seed

**Severity: High | CWE-1233 (Missing Lock Bit Protection) | Threat actor: T1 | Confidence: High**

**Location:** `rtl/modules/crypto_top/rtl/trng.sv:52`, `:108-120`, `:433`

**Description.** `trng.sv:52` hardwires the module's `sfrlock` to `'0`. Because `apb_cr`/`apb_sfr2` derive their write strobe as `~sfrlock & psel & penable & pwrite`, **every** TRNG register is writable by any master that reaches the SCE APB page, at any time, including while a key generation is in flight. The reachable controls include `sfr_pp` (`cr_drng_en`, `cr_postproc_opt`, `cr_hlthtest_en`, `cr_healthtest_len`, `cr_pfilter_en`), `sfr_crsrc` (oscillator enables), `sfr_crana` (per-channel enable/valid), `sfr_chain` (the 128 tap enables) and `sfr_buf`, which in DRNG mode writes `buf_data` directly. Setting `cr_drng_en = 1` and writing eight words to `sfr_buf` installs a fully attacker-chosen 256-bit seed and asserts `buf_ready`, after which the generator is a pure deterministic function of that seed — in mode 1 the output is literally `AES(buf_data[255:128], buf_data[127:0])`, and in mode 0 the LFSR is loaded with `buf_data[255:127]` and shifted with **no entropy term at all** (`lfsr129.v:90`). There is no lock bit, no write-once behaviour, and no requirement that these registers be frozen while `rngcore_en` is asserted. Compare `aes.sv:135`, `pke.sv:287`, `alu.sv:131` and `combohasha.sv:203`, all of which implement an operational lock — the TRNG is the only one of the five with a dead lock.

**Evidence.**
```systemverilog
// trng.sv:52 — the lock is a constant
    `theregrn( sfrlock ) <= '0;
// trng.sv:108-120 — every control bound to that dead lock via .*
    apb_cr #(.A('h00), .DW(13) )      sfr_crsrc       (.cr(cr_src), .prdata32(),.*);
    apb_cr #(.A('h08), .DW(17) )      sfr_pp          (.cr(cr_postproc), .prdata32(),.*);
    apb_cr #(.A('h40), .DW(32), .REVY(1), .SFRCNT(CHAINW/32) )      sfr_chain       (.cr(rngchainen), .prdata32(),.*);
// trng.sv:433 — apb_buf write strobe, same dead lock
    assign apbwr = ~sfrlock & apbs.psel & apbs.penable & apbs.pwrite;
// data_buf.v:68-77, :101 — software-supplied 256-bit seed in DRNG mode
    if(trng_drng_sel&buf_write)begin
        buf_data_pre[31 :  0] = (buf_addr==3'd7) ? buf_datain: buf_data[31 :  0];
// lfsr129.v:90 — DRNG branch mixes in NO entropy
                          (rngcore_en_lfsr&   lfsr_stable  &  (~lfsr_dataout_vld) &   trng_drng_sel)                  ? {lfsr_chain[127:0],lfsr_out}:
```

**Preconditions.** Bus write access to `0x4002_E000`–`0x4002_E05C`. Unrestricted while `scemode == 0`; after mode lock, restricted to the owning `coreuser` — but note `sce_sec.sv` recognises only `AMBAID4_CM7P` and `AMBAID4_VEXD`, and the Vex peripheral port drives `AMBAID4_VEXP` (BAO-086).

**Attack scenario.** An unprivileged task writes `0x4002_E008` with `cr_drng_en = 1` and `cr_postproc_opt = 1` (or 0). It writes eight chosen words to `0x4002_E030`; on the write landing at `buf_addr == 7`, `buf_ready` asserts, `buf_data` is entirely attacker-chosen, and the entropy shift is disabled. It then writes `0x5a` to `ar_start`, or simply lets the victim's own start proceed. The victim's key-generation routine reads SEG_RNGA/RNGB and obtains exactly `AES(attacker_key, attacker_plaintext)` — a value the attacker computed beforehand. Because the registers are not frozen while `rngcore_en` is asserted, the attacker can also flip `cr_drng_en` between the victim's `ar_start` and the victim's read of the pool.

**Impact.** Complete, deterministic control of the random values a victim consumes, from unprivileged software, with no fault injection.

**Mitigation (a) — RTL.** Drive `sfrlock` properly — either an operational lock in the style of `aes.sv:135` so the configuration freezes while `rngcore_en` is asserted, or a boot-set one-way lock. Gate `cr_drng_en` and the software seed-write path on a lifecycle/test-mode signal so they are unreachable in a production USER-mode part, and make a change of `postprocess_opt`/`trng_drng_sel` force a full re-seed and invalidate pending output rather than being accepted mid-flight.

**Mitigation (b) — fabricated silicon.** (1) Leave `scemode == 0` for the shortest possible window. (2) Before every key draw, read back `sfr_crsrc`, `sfr_crana`, `sfr_pp`, `sfr_opt` and `sfr_chain` and verify them; read them back again after the draw and discard the batch on any change. (3) Do not schedule untrusted code on either CPU across a key-generation window. (4) Derive keys by hashing TRNG output with a device secret so a forced-DRNG output alone does not determine the key.

**Verification notes.** The write-strobe derivation, the DRNG seed-write path, the disabled entropy shift, and the absence of any lifecycle gate on `cr_drng_en` were all confirmed independently. One citation correction: the comparable operational lock in `combohasha.sv` is at line 203, not 159; `pke.sv:287` is a third instance the finder did not cite, which strengthens the point that the TRNG is the outlier. `sfr_chain` occupies `0x4002_E040`–`0x4C`.

---

<a id="bao-018"></a>

### BAO-018 — TRNG is the only SCE crypto engine excluded from `sceresetn`: its seed, generator state and configuration survive a security-mode change and the software SCE reset

**Severity: High | CWE-1272 (Sensitive Information Uncleared Before State Transition) | Threat actor: T1 | Confidence: High** *(verifier-surfaced)*

**Location:** `rtl/modules/crypto_top/rtl/sce.sv:531-536`; contrast `:511-513`, `:553-555`

**Description.** `sce_sec` derives a mode-quit reset that resets the entire SCE whenever the security mode changes from a previously programmed value, or when software issues `ar_reset`. Every other crypto engine and the whole DMA/AMBA fabric inside the SCE takes it: hash (`sce.sv:447`), pke (`:488`), aes (`:512`), alu (`:554`), scedma (`:334`), scedma_ac (`:374`), sce_sec itself (`:275`) and the AHB/APB infrastructure (`:154/166/173`). The `trng` instance alone is wired to the raw power-on reset. Every secret-bearing register inside the TRNG is therefore reset only by that raw reset: `buf_data` (the 256 raw entropy bits that are simultaneously the LFSR seed, the mode-1 AES key/plaintext, and the CTR_DRBG seed), `lfsr_chain` (the full generator state), the DRBG key and counter, and every `apb_cr` in `trng.sv` including `cr_postproc`, `rngchainen` and `dr_psz_str`.

**Evidence.**
```systemverilog
// sce.sv:531-536 — trng gets the raw reset
    trng trng(
            .ana_rng_0p1u(ana_rng_0p1u),
            .clk            (clk),
            .resetn         (resetn),
            .sysresetn      (sysresetn),
// sce.sv:511-513, :553-555 — every sibling gets sceresetn
    aes aes(
            .clk            (clksub[3]),
            .resetn         (sceresetn),
    alu alu(
            .clk            (clksub[0]),
            .resetn         (sceresetn),
// sce_sec.sv:81-83 — what sceresetn is for
    assign modequit = devmode[1] ? '0 : ~( scemodereg == 0 ) && ~( scemode == scemodereg ) ;
	assign sceresetnin = ~( modequit | ar_reset );
// trng.sv:293 — rstn is the raw resetn
    /*        input  logic              */ .rstn    (resetn),
```

**Preconditions.** A previous context ran the TRNG. The attacker needs bus access to the SCE APB page, which is unrestricted while `scemode == 0` — the state the SCE returns to after any mode-quit or `ar_reset`.

**Attack scenario.** A privileged context programs the SCE, runs the TRNG and generates a key; `buf_data` holds the 256 raw entropy bits that seeded that draw, and `lfsr_chain` (mode 0) or the DRBG key/counter (mode 2) holds the state that produced it. The context finishes and either writes a different `scemode` or issues `ar_reset`. Hash, pke, aes, alu and the whole DMA are wiped — the TRNG is not. The next owner, or an unprivileged task while `scemode` is back at 0, reads `0x4002_E020`–`0x4002_E03C` eight times (BAO-016) and recovers the previous context's complete 256-bit seed. In mode 1 the previous output was literally `AES(buf_data[255:128], buf_data[127:0])`, so the victim's random word is recomputed directly; in mode 0 the seed gives the initial LFSR state; in mode 2 it gives the DRBG seed material with `K0`/`M0` as file constants. The same gap lets a previous context's `cr_drng_en`/`rngchainen`/`cr_postproc` settings persist into the next context's key draw.

**Impact.** The security-mode transition — the design's own trust-domain boundary — does not sanitise the TRNG. Prior-context seeds and generator state, and prior-context entropy configuration, cross it intact.

**Mitigation (a) — RTL.** Connect the `trng` instance to `sceresetn` like every other engine, and additionally clear `buf_data`/`lfsr_chain`/the DRBG state on `sceramclr`.

**Mitigation (b) — fabricated silicon.** The owning context must, before relinquishing the SCE or issuing any reset, overwrite `buf_data` itself (writable in DRNG mode) with non-secret values and rewrite `cr_postproc`/`rngchainen` to a known-safe configuration. The next owner must not trust any TRNG configuration it did not itself write, and must re-verify every TRNG register before its first draw.

**Verification notes.** Surfaced by the verifier. The reset asymmetry was confirmed by reading all nine engine/infrastructure instantiations in `sce.sv`; `trng` is the only one not on `sceresetn`. The seed-consumption sites (`lfsr129.v:89`, `postprocess.v:179/182`, `ctr_aes.v:163/171`) were confirmed, as was the readability path of BAO-016.

---

<a id="bao-019"></a>

### BAO-019 — Voltage-tamper reset mask `cr_vdmask1` is used as a scalar condition and resets to all-ones, so the only autonomous hardware tamper response is disabled by default and cannot be selectively armed

**Severity: High | CWE-1221 (Incorrect Register Defaults) | Threat actor: T2/T4 for the glitch; T1 alone for the active bypass | Confidence: High**

**Location:** `rtl/modules/sec/rtl/sensorc.sv:93`, `:68`, `:57`

**Description.** `sensorc` has exactly one path that produces a hardware (non-software) reaction to a tamper event: `vdresetn`, which feeds `soc_top.sv:712 .vdresetn( secresetn )` and thence `sysctrl.sv:794`'s `sysresetgen`. That path is qualified by a 6-bit per-detector mask, and two defects compound.

**(a) Operator defect.** At line 93 the 6-bit vector `cr_vdmask1` is used as the *condition* of a ternary, not as a bitwise mask. SystemVerilog evaluates a multi-bit condition as `|cr_vdmask1`, so the expression reduces to `vdresetnreg <= (|cr_vdmask1) ? 6'b111111 : &(~vdflag)` — **any single set bit suppresses the tamper reset for all six voltage detectors** (VD09L/H, VD25L/H, VD33L/H). The sibling IRQ mask two lines above is correctly bitwise (`sr_vdsr = vdflag & ~cr_vdmask0`). The commented-out original at line 92 has the identical bug, so this is not a late typo.

**(b) Permissive reset default.** The register is instantiated with `.IV({VDC{1'b1}})` (all ones), so out of every reset `vdresetn` is stuck at 1 and no voltage-tamper event can ever assert a reset.

The register is at `0x4005_3004` with `sfrlock` hardwired to 0, and the `0x4005_xxxx` APB is reached with no `hauser`/`coreuser`/`pprot` check, so any bus master can re-mask it at any time with one 32-bit store.

**Evidence.**
```systemverilog
// sensorc.sv:67-68 — both masks default to all-ones
    apb_cr #(.A('h00), .DW(VDC), .IV({VDC{1'b1}}) )  		sfr_vdmask0   (.cr(cr_vdmask0), .prdata32(),.*); // irq mask
    apb_cr #(.A('h04), .DW(VDC), .IV({VDC{1'b1}}) )  		sfr_vdmask1   (.cr(cr_vdmask1), .prdata32(),.*); // reset mask
// sensorc.sv:91-94 — line 91 is correctly bitwise; line 93 uses the vector as a scalar condition
	assign sr_vdsr = vdflag & ~cr_vdmask0;
//	assign vdresetn = & ( cr_vdmask1 ? '1 : ~vdflag );
    `theregfull(clksys, resetn, vdresetnreg, '1 ) <= & ( cr_vdmask1 ? '1 : ~vdflag );
    always@(posedge clksys) vdresetn <= vdresetnreg;
// sensorc.sv:57 — no lock
    `theregrn( sfrlock ) <= '0;
// sysctrl.sv:789-795 — the consumer
    resetgen #(.ICNT(4),.EXTCNT(RCUEXTCNT))sysresetgen(
        .resetnin    ( { socresetn, vdresetn, secresetn, ~sysreset_sw } ),
```

**Preconditions.** Case 1: none — this is the post-reset state of the fabricated part. Case 2: any write access to `0x4005_3004`, i.e. unprivileged code on either CPU or any AHB master reaching `core_ahb32`.

**Attack scenario.** **Case 1 (default, no attacker action).** The chip powers up with `cr_vdmask1 = 6'b111111`, so `vdresetnreg` is unconditionally 1. The attacker applies a voltage glitch on the 0.9 V core rail to fault an SCE key comparison or a secure-boot branch. VD09L trips and `sr_vdsr` sets a status bit — but `secresetn` never deasserts, `sysresetgen` never fires, the SCE is never reset, and the crypto-RAM wipe that SCE reset release would trigger never runs. The glitch campaign proceeds; the only consequence is a status bit the attacker's own fault may have prevented firmware from reading.

**Case 2 (active bypass).** Suppose firmware correctly writes 0 to `0x4005_3004` during boot. Unprivileged software on either CPU — or the BDMA peripheral master, which drives `hauser = 0` and is subject to no `coreuser` check on this bus — stores `0x0000_0001`. Setting one bit of a six-bit mask disables the reset response for all six detectors, because the mask is consumed as a scalar. There is no lock bit and no privilege check, so this cannot be prevented and cannot be detected by hardware.

**Impact.** The chip's only autonomous hardware response to a voltage-tamper event is inert out of reset, and is re-disablable in its entirety by one unprivileged store. This directly enables fault-injection attacks on secure boot and on the SCE.

**Mitigation (a) — RTL.** (1) Make the mask bitwise: `vdresetnreg <= &( cr_vdmask1 | ~vdflag );`. (2) Change `.IV` to all-zeros so the response is armed out of reset and software must explicitly opt out. (3) Make `cr_vdmask1` write-once or lockable, or gate writes on `coreuser[5:4]` as `rrc.sv:815` does. (4) Route the tamper condition to an asynchronous reset/zeroise path that does not require `clksys` (see BAO-097).

**Mitigation (b) — fabricated silicon.** Partial and it does not fix the scalar bug. Immutable boot ROM/boot0 must write `0x0000_0000` to `0x4005_3004` as one of its first stores, and program a plausible debounce at `0x4005_3020`. Firmware should then periodically re-read `0x4005_3004` and `0x4005_3000` and treat any non-zero value as a tamper event itself. This works only while the CPU is running and trusted, cannot restore per-detector granularity, and is defeated by anything that gains a single 32-bit write.

**Verification notes.** The quotes are verbatim. `cr_vdmask1` is `logic [VDC-1:0]` with `VDC = SENSORVDC = 6`; a multi-bit ternary condition in SystemVerilog is a non-zero test, so one set bit suppresses all six. The consumer chain was traced to `sysresetgen`, whose `resetninx = &resetnin & resetn` is an async reset, confirming `secresetn` low really does assert `sysresetn`. Note `sysctrl`'s own `vdresetn` input is dead (`soc_top.sv:373` ties it to 1), so `secresetn` is the only live tamper-reset leg. The downstream impact holds: no reset means no SCE reset means no crypto-RAM wipe. One correction: the finder's claim that "apb_cr defaults elsewhere in this module use IV=0" is wrong — the sibling IRQ mask has the identical `.IV({VDC{1'b1}})`, so both masks booting masked is a deliberate "stay quiet until firmware programs thresholds" policy. Defect (b) is therefore a design-policy argument while defect (a) is the hard bug.

---

<a id="bao-020"></a>

### BAO-020 — Mesh and glue-chain arming is destroyed by every warm reset, and the mesh's only clock is a software-gateable ICG that feeds nothing else in the SoC

**Severity: High | CWE-1233 | Threat actor: T1 or T4 to disarm, T2 to exploit | Confidence: High**

**Location:** `rtl/asic_top/rtl/soc_top.sv:702-703`; `rtl/modules/sec/rtl/secsub.sv:55-56`, `:93`, `:73`; `rtl/modules/sysctrl/rtl/sysctrl.sv:634-636`, `:867`

**Description.** Two integration-level weaknesses let an attacker silence the mesh without touching the mesh's own registers.

**(a) Reset domain.** `secsub` passes `resetn` to both mesh and gluechain while giving `sensorc` `porresetn`. `soc_top.sv:702-703` binds `porresetn` to `socresetn` but `resetn` to `coreresetn`, which is asserted by the watchdog and by a plain APB action register `sfr_rcurst1` at `0x4004_0084`. Every such warm reset returns mesh `cr_mldrv`/`cr_mlie` and gluechain `gluerst`/`gluetest`/`cr_gcmask` to their `apb_cr` default of 0 — the fully disarmed state — while the secrets they protect remain in SRAM, TCM, IFRAM, AO-SRAM and ReRAM. The tamper subsystem is off during every warm reboot until firmware re-arms it, and the attacker can re-trigger the reset arbitrarily often to extend that window.

**(b) Clock domain.** The mesh runs on `pclksub[7]`, produced by a dedicated ICG whose enable is bit 7 of `pclksubgate`, an ordinary APB control register at `0x4004_006C`. Grepping the design, `pclksub[7]` is used by **nothing except the mesh**. Clearing bit 7 therefore stops the mesh's `aptreg` sampling flops and its `irq` flop and nothing else — a perfectly targeted, side-effect-free way to freeze mesh detection while the rest of the chip runs normally. There is no lock: `sysctrl`'s `sfrlock` input is an undriven net (BAO-062).

**Evidence.**
```systemverilog
// soc_top.sv:702-703 — mesh clock is pclksub[7]; secsub resetn is coreresetn
                           .pclkmesh (pclksub[7]),
/*        input logic  */  .porresetn   ( socresetn ),
/*        input logic  */  .resetn      ( coreresetn ),
// secsub.sv:56, :93 vs :73 — mesh and gluechain on the warm reset, sensorc on POR
	    .resetn,
	    .resetn \t( porresetn ),
// sysctrl.sv:634-636, :867 — a plain, unlocked control register gates the mesh clock
             ICG upclksub ( .CK (clktop   ), .EN ( pclken & pclksubgate[gvi] ), .SE(cmsatpg), .CKG ( pclksub_unmux[gvi] ));
    apb_cr #(.A('h6c), .DW(PCKCNT),   .IV('hff)) sfr_pclkgr     (.cr(pclksubgate),.prdata32(),.*);
// sysctrl.sv:871-872 — the software warm-reset trigger
    apb_ar #(.A('h80), .AR('h55aa))        sfr_rcurst0    (.ar(sysreset_sw),   .*);
    apb_ar #(.A('h84), .AR('h55aa))        sfr_rcurst1    (.ar(corereset_sw),  .*);
```

**Preconditions.** Vector (a): the ability to cause a watchdog timeout (any unprivileged code can simply stop servicing it) or one write of `0x55AA` to `0x4004_0084`. Vector (b): one write to `0x4004_006C`. Both are on the `0x4004_xxxx` APB, reached from `core_ahb32` with no identity or privilege check.

**Attack scenario.** **Vector (a):** unprivileged code stops kicking the watchdog. `coreresetn` asserts; mesh `cr_mldrv`/`cr_mlie` and gluechain `gluerst`/`gluetest`/`cr_gcmask` all return to 0, so the mesh drives all 64 lines to constant 0, `apterr` is force-zeroed, and the glue chain is held in cell reset. Memory contents survive. The attacker performs the physical intrusion during the boot window before firmware re-arms, and re-triggers the reset to extend it indefinitely.

**Vector (b), one store:** the attacker reads `0x4004_006C` (default `0xFF`) and writes `0x7F`. `pclksubgate[7]` goes to 0, the ICG stops `pclksub[7]`, and the mesh's sampling and interrupt flops stop clocking. The status registers freeze at their last (clean) values, the interrupt can never assert, and nothing else in the SoC is affected. Firmware polling `sr_mlsr` at `0x4005_2020` reads a stale all-zero value — the APB `pready` is combinational, so the read completes normally with a stale value even with the block's clock stopped. The attacker then cuts the mesh and probes.

**Impact.** Complete, targeted, single-store disarmament of the anti-tamper mesh, with no side effects and no error indication, plus a reset-window disarmament requiring no privilege at all.

**Mitigation (a) — RTL.** (1) Move mesh and gluechain to `porresetn` as `sensorc` already is, or make the arming state sticky in the always-on POR domain. (2) Default `cr_mlie` to the ARMED state. (3) Remove the mesh from the software-gateable `pclksub` tree — clock it from a free-running or AO clock — or hardwire `pclksubgate[7]` to 1 and expose no CR bit. (4) Drive the `sysctrl` `sfrlock` input and lock the clock-gate and reset action registers after boot. (5) Add a hardware check that the mesh clock is toggling and treat a stopped mesh clock as a tamper event.

**Mitigation (b) — fabricated silicon.** Firmware must re-arm the mesh (`0x4005_2000/04` pattern, `0x4005_2010/14 = 0xFFFF_FFFF`) and the glue chain as the very first action in the reset handler, before any secret is touched, and treat a reset whose `sfr_rcusrcfr` indicates a watchdog or software core reset as suspicious. Firmware should periodically confirm `0x4004_006C` bit 7 is set, and should confirm the mesh is alive by momentarily inverting `cr_mldrv` and checking that `sr_mlsr` responds — a frozen clock fails that liveness test.

**Verification notes.** Both vectors reproduced. Vector (b) is the stronger half and was verified three ways: the ICG enable expression, the exclusive-consumer grep (`pclksub[` appears only at `soc_top.sv:702` and the no-CM7 variant, both `.pclkmesh`), and the vendor's own documentation at `docs/src/clock-generation.md:405` which independently documents CGUPCLKGR bit [7] as "mesh | Mesh clock enable", reset `0x0000_00FF`. Note `sfr_pclkgr` is in the ASIC arm of an `` `ifdef FPGA ``; under FPGA it is a read-only alias, so vector (b) exists only in the ASIC build — worth stating explicitly. One supporting claim was dropped as unverified: "no SRAM, TCM, IFRAM, AO-SRAM or ReRAM content is cleared" was asserted without evidence and is not needed for either vector.

---

<a id="bao-021"></a>

### BAO-021 — Sticky USER-mode lifecycle latch in the AO domain is cleared by the external XRSTn pad, giving DFT/BIST access with all volatile memory intact

**Severity: High | CWE-1243 / CWE-1244 (Internal Asset Exposed to Unsafe Debug Access) | Threat actor: T2, optionally T4 | Confidence: High**

**Location:** `rtl/modules/ao/rtl/ao_top.sv:144`; `rtl/modules/ao/rtl/ao_sysctrl.sv:422-430`; `rtl/asic_top/rtl/pad_frame_arm.sv:218`

**Description.** `aocmsuser` is the one latch that makes the chip's USER lifecycle state sticky. Once the CMS controller resolves to `CMS_USER`, `aocmsuser` is set and forces every subsequent CMS evaluation to `CMS_USER` (`cms.sv:155`), which keeps the ReRAM BIST TAPs, the rbist/MBIST TAP, the IPT TAP and the PMU-trim JTAG path locked out. That latch lives in the AO domain and its only reset is `porresetn_undft`, derived from `por = ~pmu_POR & padresetn` — i.e. from the external `PAD_XRSTn` pin. Asserting XRSTn therefore clears the sticky latch **without removing power from the SoC domain**: the regulator enables come from `pmucrreg`, which resets to `IV_PMUCR = 8'b01111100` with VR25/VR85A/VR85D/IOUT/POC all still enabled, so VDD85D and VDDAO stay up and every SRAM in the chip retains its contents. On the way back up, the CMS controller re-samples the WMS pads and, with `aocmsuser` now 0, is free to resolve to `CMS_TEST` or `CMS_VRGN`, asserting `cmstest` and `cmsbist`. `cmsbist` hands the JTAG rbist master direct clock/address/enable control of every RAM macro through `rbspmux`, and `cmstest` un-gates the rbist and ReRAM JTAG TAP pins in the pad frame.

**Evidence.**
```systemverilog
// ao_top.sv:144 — the sticky latch, reset by porresetn_undft
    `theregfull( clksysao_undft, porresetn_undft, aocmsuser, '0) <= aocmsuser | cmsuser;
// ao_sysctrl.sv:422 — that reset is derived from the external pad
    assign por = ~pmu_POR & padresetn ;
// pad_frame_arm.sv:218 — padresetn is PAD_XRSTn
    padcell_i #(.H('0),.pu(1'b1)) u_xrstn  ( .pad( PAD_XRSTn ), .thecfg(padcfg_xrst), .pi( padresetn ), .rtosns(rtosnstest));
// cms.sv:155, :153 — with aocmsuser clear, the pads decide the mode again
    `theregfull( clk, resetn, cmscodereg, cms_pkg::CMS_NONE ) <= cmsdataregvld & cmspadlock ? ( aocmsuser ? cms_pkg::CMS_USER : cmscodepre) : cmscode;
        `theregrn( cmstestreg ) <=   cmscodereg == cms_pkg::CMS_TEST | cmscodereg == cms_pkg::CMS_VRGN;
// soc_top.sv:397 and pad_frame_arm.sv:244-246 — what that unlocks
    assign cmsbist = cmstest;
    assign jtagrb.trst = cmstest & jtagtrst;
```

**Preconditions.** Physical access to `PAD_XRSTn`, `PAD_WMS0`, `PAD_WMS1` and the JTAG pins. The board must not gate XRSTn behind a power sequencer that also drops VDD85D. **Important scoping caveat, see verification notes:** the incremental capability this grants is data remanence, not lifecycle downgrade.

**Attack scenario.** The attacker owns the board. The chip boots normally into `CMS_USER`; `aocmsuser` latches; the JTAG BIST/ReRAM TAPs are dead. Firmware runs and unwraps keys into the SCE crypto RAM, core SRAM and AO RAM. The attacker then drives PAD_WMS0/1 high and pulses PAD_XRSTn low for more than the reset-extension count, then releases. VDD, VDD25, VDD85A/D and VDDAO are never interrupted — only the reset pin moves — so **no SRAM loses state**. `por` goes low, `aocmsuser` clears, `cmscodereg` re-evaluates and resolves to `CMS_VRGN`, `cmstest`/`cmsbist` assert, and the pad frame feeds the real TMS/TDI/TRST pins to `jtagrb` (rbist) and to the raw ReRAM macro TAPs. `rbspmux` hands the rbist master the clock, address and enables of every RAM macro and returns live macro read data. The attacker walks the address space of `rbif_sce_sceram_10k` (SKEY/AKEY/PKB), `rbif_aoram1kx36` and `rbif_acram2kx64` over JTAG and reads out the key material the USER session left resident. Total cost: two pin holds and one reset pulse — no decapsulation, no glitching, no power cycle.

**Impact.** A USER session's live secrets in volatile memory are exposed to the memory-BIST JTAG path, because entering a non-USER CMS mode performs no zeroisation of any kind. The only wipe machinery in the design is the SCE's `sceramclr`, which is confined to the SCE's own RAMs, skips RNGA/RNGB, and is not connected to `cmstest`, `cmsbist` or any tamper input.

**Mitigation (a) — RTL.** `aocmsuser` must be reset only by a true power-on reset of the AO rail (`pmu_POR` alone), never by the external reset pin — change `ao_sysctrl.sv:422` so the `porresetn` used for the lifecycle latch excludes `padresetn`, and give the latch its own dedicated reset. Make the latch redundant (multi-bit or dual-rail) rather than a single flop. Independently and most importantly, **entry into any non-USER CMS mode must unconditionally trigger a wipe of all crypto RAMs, the AO RAM and the core SRAMs before the BIST/JTAG paths are enabled.**

**Mitigation (b) — fabricated silicon.** No hardware mitigation. Board-level only: do not bring PAD_WMS0/1 or the JTAG pins to accessible pads; tie PAD_WMS0 to ground in the package or substrate if possible. Firmware should scrub all key material from SRAM and AO RAM immediately after use to minimise the retention window, since it cannot observe or prevent the XRSTn event.

**Verification notes.** All quoted lines are verbatim. `theregfull` is an async active-low reset, so `aocmsuser` clears asynchronously. The `rbspmux` datapath was independently opened: `ram_1rw_s.sv:125-131` muxes clock, cen, gwen, wen, address and data from the BIST bus on `cmsbist`, and line 140 returns live macro read data; `rbspmux` is instantiated on the AO RAM, the crypto RAMs, the core SRAM banks, the TCMs and the RRC ACRAM. No compensating control exists: nothing wipes any RAM on entry to `cmstest`.

**Important framing correction (please read).** The RTL mechanism is exactly as quoted, but "lifecycle downgrade" is the wrong framing and must not go to the vendor that way. There is no persistent lifecycle state to downgrade: CMS mode is re-decided from the WMS pads on every reset **and on every cold power-on**, and `aocmsuser` only prevents a mode change while the AO domain stays reset-free. Moreover `nvrcfgs.sv:102-105` sets the ReRAM defaults to `CMSDAT_USERMODE`, and all four `CMSDAT_*` patterns are `'0` in this release (a redaction artefact — see §1.4), so the ReRAM half of the decision is degenerate in the source we have. The genuinely incremental capability is **data remanence**: PAD_XRSTn does not interrupt VDD85D/VDDAO, so USER-session secrets still resident in the SCE crypto RAMs, core SRAM and AO RAM survive into BIST mode. Report as a reset/remanence issue and as "entering a non-USER CMS mode does not wipe volatile memory". Severity **high** rather than critical: it requires sustained physical control of PAD_XRSTn, PAD_WMS0/1 and the JTAG pins.

---

<a id="bao-022"></a>

### BAO-022 — AO SRAM is never zeroised by any reset, contradicting the documented guarantee, and its bus window has no access control

**Severity: High | CWE-1266 / CWE-226 | Threat actor: T2 for remanence; T1/T3 for the bus window | Confidence: High**

**Location:** `rtl/modules/ao/rtl/ao_top.sv:243-266`; `rtl/modules/common/rtl/gnrl_sramc.sv:18-34`; `rtl/modules/ifsub/rtl/soc_ifsub.sv:128`, `:149`

**Description.** `docs/src/pmu.md:184` instructs firmware to "Store any important data to AO backup registers or AORAM before entry" to power-down, and `docs/src/pmu.md:140` guarantees that "Backup-registers, RTC and AORAM in the AO domain are preserved if the wake-up source is from the PF pins; if external reset is used, then these registers are cleared." That guarantee holds for the backup registers (`aobureg` is a flop array reset by `porresetn`) and for the RTC, but it is **false for AORAM**. The AORAM is two `aoram1kx36` SRAM macros instantiated bare with no clear logic, driven by a controller whose only backing block is `gnrl_sramc`, which has no `ramclr`/zeroise port at all. Nothing anywhere writes zeros into these macros on any reset, lifecycle change or tamper event. Separately, the AORAM's bus window at `0x5030_0000`–`0x5030_1FFF` sits behind `ahbsramc32` with no `coreuser`, `hauser` or `hprot` check, in the ifsub matrix reachable by both CPUs' peripheral ports, by the BIO/BDMA AHB master (which drives `hauser = 0`), by the uDMA and by the USB device controller. Scrambling is available in the config but disabled (`.scmben(1'b0)`, `.scmbkey('0)`), so contents are plaintext.

**Evidence.**
```systemverilog
// ao_top.sv:243-255 — bare macros, no clear port
    for (i = 0; i < 2; i++) begin:gaoram
    aoram1kx36  m (
         .clk         (aoram_clkb[i]),
         .q           (aoram_bq[i]),
         .cen         (aoram_bcen[i]|ao_iso_enable),
         .gwen        (aoram_bwen[i]|ao_iso_enable),
         .ret1n       (1'b1),
// gnrl_sramc.sv:18-34 — the only controller; no clear input exists (contrast cryptoram.sv:29 `input logic ramclr`)
module gnrl_sramc
(
    input logic        		clk,
    input logic       		resetn,
    ...
    ramif.slave  		ramslave,
    ramif.master 		rammaster
);
// aoram.sv:95 — scrambling disabled despite isSCMB:'1 in the config
        .scmben(1'b0),
// soc_ifsub.sv:128, :149 — unprotected bus window
        '{idx: 32'd4 , start_addr: 32'h5030_0000, end_addr: 32'h5030_1fff}, // aosram
    ahb_thru ubmxifmdemux4 ( .ahbslave(bmxifmdemux[4]), .ahbmaster( ahbaoram ));
```

**Preconditions.** Firmware uses AORAM to retain any secret across sleep/power-down — which is exactly what the vendor documentation tells it to do. For the bus path, any of: unprivileged code execution, a uDMA/BDMA descriptor, or a USB endpoint transfer.

**Attack scenario.** **Path A (physical, T2):** firmware follows `pmu.md:184` and stashes a session key or unwrapped PIN-derived secret in AORAM before deep sleep. The attacker asserts PAD_XRSTn believing, per `pmu.md:140`, that this clears AORAM — it does not. The 8 KB of AO SRAM comes back with the secret intact, reachable either over the ordinary bus at `0x5030_0000` by whatever code runs first after reset, or, chained with BAO-021, through the JTAG rbist path (`aoram.sv:148-166` wires `rbif_aoram1kx36` straight into `rbspmux`). Because `scmben` is tied 0, the readback is plaintext. **Path B (software/peripheral, T1/T3):** the AORAM window has no privilege gate, so unprivileged code on either CPU, the BIO/BDMA peripheral master, a uDMA descriptor, or an attacker-controlled USB transfer can read `0x5030_0000`–`0x5030_1FFF` directly and recover whatever secure firmware retained there.

**Impact.** A documented guarantee the silicon does not provide, over a region the documentation directs firmware to use for important data — with no access control on the bus window and no scrambling.

**Mitigation (a) — RTL.** Add a clear/zeroise FSM to the AORAM path exactly as `cryptoram.sv` does for the crypto RAMs (a `ramclr` input on `gnrl_sramc` that walks the address space writing zeros), triggered from `porresetn`, from any CMS mode change out of `CMS_USER`, and from a tamper event. Enable the scrambler that is already present in the config instead of tying `.scmben(1'b0)`, and feed `scmbkey` from a per-boot random value rather than the `'0` passed at `soc_top.sv:870`. Add a `coreuser`/`hauser` filter in front of `ahbaoram`. **Correct `docs/src/pmu.md:140`, which currently states a guarantee the silicon does not provide.**

**Mitigation (b) — fabricated silicon.** Firmware must explicitly overwrite the whole 8 KB AORAM window before any sleep or reset it can anticipate, and must never rely on reset to scrub it. Treat `0x5030_0000` as world-readable and therefore unsuitable for any secret; if retention across power-down is needed, store only a ciphertext blob whose key never leaves the SCE.

**Verification notes.** The bare macro instantiation, the absent `ramclr` on `gnrl_sramc` (asymmetric with `cryptoram.sv:29/39`), the disabled scrambler, and the unfiltered bus window were all confirmed. `coreuser` was confirmed by grep to be forwarded only to the SCE and the ReRAM controller and never used as an AHB/APB filter. `bio_bdma.sv:1579` and `:1670` both `assign ahbm.hauser = '0;`, and `bdma_ahb32` enters the core AHB matrix as a master, so the DMA path is real. Two additions from verification: `gnrl_sramc.sv:176-199` instantiates `gnrl_sramc_initprt`, which after every reset walks the array *reading* each word and rewriting it with recomputed parity — it preserves data rather than clearing it, so retained AORAM comes back after a warm reset with freshly valid parity. And `docs/src/system-control.md:17` claims AORAM is 16 KB at `0x5030_0000`–`0x5030_3FFF` while the RTL implements 8 KB — a second doc/RTL mismatch.

---

<a id="bao-023"></a>

### BAO-023 — PMU regulator enables and analog voltage trims are software-writable with no lock and no privilege check, while the regulator-ready reset sources are masked off by default

**Severity: High | CWE-1247 / CWE-1233 | Threat actor: T1, amplified by T4 | Confidence: High**

**Location:** `rtl/modules/ao/rtl/ao_sysctrl.sv:433`, `:443`, `:382`, `:362`, `:245-256`, `:391-394`

**Description.** Three defects compose.

**(a)** Every SFR in `ao_sysctrl` is unlockable — `assign sfrlock = '0;` — and the whole `0x4006_0000` AO window arrives over an `ahbasync` + `apb_bdg` bridge that carries no `coreuser`, `hauser` or `pprot` filtering, so any bus master including unprivileged code on either CPU and the BIO/BDMA AHB master can write it.

**(b)** Those registers drive the analog PMU directly. `sfr_pmucr`/`sfr_pmutrm0`/`sfr_pmutrm1` load `pmucrreg`/`pmutrmreg` whenever `ipflow_set` pulses, which is raised by writing `0x57` to `sfr_ipcaripflow` at `0x4004_0090`. `pmu_trm` fans out to `pmu_TRM_DP60_VDD85D` — the reference for the 0.85 V **digital core** regulator — and `pmu_VDDAO_VOLTAGE_CFG`; `pmu_ctrl` fans out to `pmu_VR85DENA`/`pmu_VR25ENA`. There is a second, shorter path: `pmu_trm` and `pmu_ctrl` are taken **directly** from the low-power shadow registers PMU_TRMLP0/1 and PMU_CRLP whenever `ipsleep` or `aopdreg` is asserted, and `ipsleep` is raised by two ordinary SFR writes followed by a WFI.

**(c)** The safety net that should catch the resulting brown-out is disabled at reset: `cr_rstcrmask` has `.IV(5'h1f)`, and `rstsrc` ORs that mask over the five PMU status bits, so `&rstsrc` is permanently 1 and `socresetnin` never de-asserts because a regulator dropped out. The chip keeps running through a software-induced undervoltage instead of resetting.

**Evidence.**
```systemverilog
// ao_sysctrl.sv:433, :443, :382 — the brown-out reset is masked off by its own reset default
    assign rstsrc = { pmu_BGRDY, pmu_VR25RDY, pmu_VR85ARDY, pmu_VR85DRDY, ~pmu_POR } | rstcrmask;
    assign socresetnin = cmsatpg ? 1'b1 : ~aopdreg & (&rstsrc) ;
    apb_cr #(.A('hc), .DW(5),  .IV(5'h1f))      cr_rstcrmask     (.cr( rstcrmask          ), .prdata32(),.*);
// ao_sysctrl.sv:362 — no lock anywhere in the AO block
    assign sfrlock = '0;
// ao_sysctrl.sv:245, :251 — the low-power shadow is applied directly on sleep
    assign pmu_ctrl  = cmsatpg ? pmucrreg : ipsleep ? sfrpmucrlp : aopdreg ? sfrpmucrpd : pmucrreg;
    assign pmu_trm  =  cmsatpg ? pmutrmreg : ipsleep | aopdreg ? sfrpmutrmlp : pmutrmreg;
// ao_top.sv:192-200 — the trim reaches the analog rails
    assign {
        pmu_TRM_CUR, pmu_TRM_CTAT, pmu_TRM_PTAT, pmu_TRM_DP60_VDD25,
        pmu_TRM_DP60_VDD85A, pmu_TRM_DP60_VDD85D, pmu_VDDAO_VOLTAGE_CFG
        } =  pmu_trm;
```

**Preconditions.** Any code execution able to issue bus transactions to `0x4006_0000`–`0x4006_0FFF` and `0x4004_0000`–`0x4004_0FFF`. No `coreuser`, `hauser`, `pprot`/`hprot` check and no `sfrlock` exists on either window (`ao_sysctrl.sv:362`; and in `sysctrl` the `sfrlock` port is fed by the undriven net of BAO-062).

**Attack scenario.** Unprivileged code on either CPU:
1. Leaves `AO_RSTCR_MASK` (`0x4006_000C`) at its reset value `0x1F` — all five PMU brown-out/ready reset sources are already masked, so a collapsing core rail will not reset the chip.
2. Writes `PMU_TRMLP0` (`0x4006_0028`) with an out-of-range VR85D bias trim so the 0.85 V core reference is driven far below nominal, and `PMU_CRLP` (`0x4006_0014`) to keep VR85D enabled at that trim.
3. Writes `CGULP` bit 1 and `IPCLPEN` bit 3, then executes WFI. `ipsleep[3]` asserts and `ao_sysctrl.sv:251` immediately switches `pmu_trm` to the attacker's shadow — the core supply reference changes on the fly. Per `docs/src/pmu.md:124`, "Crypto engines, peripherals, and memories remain operational" in sleep, so the SCE keeps executing while the rail is out of spec.
4. The attacker tunes the trim to the marginal point where the AES/PKE datapath produces faulty results without crashing, and harvests faulty ciphertexts for differential fault analysis.

The same registers permit a permanent denial of service (disable VR85D and pulse `0x4004_0090`), and step 1 guarantees the chip does not reset itself out of the condition.

**Impact.** A software-controlled undervoltage primitive with no hardware brown-out backstop — i.e. a T2-class fault-injection capability available to a T1 attacker with no physical access.

**Mitigation (a) — RTL.** (1) Drive `sfrlock` in `ao_sysctrl` from a write-once lock bit, and make the PMU_TRM*/PMU_CR*/PMU_TRMLP* group independently lockable so boot firmware can seal the analog trims before handing off. (2) Clamp the trims to a hardware-defined safe window rather than passing raw register bits to the analog macro. (3) Change `cr_rstcrmask`'s `.IV` to `5'h00` so the brown-out and POR reset sources are armed out of reset — a security-relevant default must be the restrictive one — and make the mask itself lockable. (4) Put a `coreuser`/`hauser` filter in front of the AO APB bridge.

**Mitigation (b) — fabricated silicon.** The earliest boot stage must write `AO_RSTCR_MASK = 0` to arm the brown-out reset, program the intended PMU_CR/TRM/CRLP/TRMLP values, and then prevent later code from reaching `0x4006_0000`. Since no bus-level filter exists and the CM7 MPU configuration is firmware's responsibility, this is only enforceable if the OS never maps the AO page into any untrusted address space — a software-only, bypassable control.

**Verification notes.** All cited lines verbatim at the cited numbers. With `rstcrmask = 5'h1f`, `&rstsrc` is identically 1 so `socresetnin` reduces to `~aopdreg` and no regulator dropout can assert `socresetn`. Both write paths were traced end to end, including the sync-pulse from `sysctrl` into the AO domain and the fan-out to the analog ports. `sysctrl`'s `sfrlock` was confirmed to be a completely undriven net. **One mitigation-supporting claim was dropped:** the assertion that "the CM7 MPU config in `daric_cfg_pkg.sv:117-127` is commented out" is not evidence the MPU is disabled — `soc_coresub.sv:317-325` references `daric_cfg::CM7CFG` fields, which could not elaborate if the struct were absent. **Confidence split:** the missing lock, the missing privilege gate and the permissive `.IV(5'h1f)` default are RTL facts reproduced by two reviewers; the specific differential-fault-analysis outcome depends on the analog trim DAC's response to out-of-range codes and cannot be established from RTL. Present the finding as "a software-controlled undervoltage primitive with no hardware brown-out backstop", not as a demonstrated DFA.

---

<a id="bao-024"></a>

### BAO-024 — Peripheral whitelist filter is wired to `DISABLE_FILTER_MEM`; `DISABLE_FILTER_PERI` is a dead net, so enabling memory DMA silently opens the entire peripheral space

**Severity: High | CWE-1262 | Threat actor: T1 | Confidence: High**

**Location:** `rtl/modules/bio_bdma/rtl/bio_bdma.sv:1478` (correct instance at `:1342`); documented at `docs/src/ch02-00-bio-overview.md:804-805`

**Description.** `bio_bdma` declares two independent filter-disable control bits and packs both into `SFR_CONFIG` at `0x5012_4008`, exactly as documented. The memory-side `axil_filter` is correctly wired to `disable_filter_mem`. The peripheral-side `axil_filter` is wired to `disable_filter_mem` as well — a copy-paste error. `disable_filter_peri` is consequently a dead net: a repo-wide grep returns only its declaration and its packing into the SFR. One control bit therefore disables **both** filters, and the documented peripheral-filter control bit does nothing at all. The two filters also share the same four `filter_base[]`/`filter_bounds[]` arrays, so there is no separate memory-versus-peripheral policy either.

**Evidence.**
```systemverilog
// bio_bdma.sv:324-325, :504-508 — both bits exist and are decoded
    logic disable_filter_mem;
    logic disable_filter_peri;
    apb_cr  #(.A('h08), .DW(10))     sfr_config           (.cr({
                                                            clocking_mode,
                                                            disable_filter_mem, disable_filter_peri, ...
// bio_bdma.sv:1341-1342 — mem_filter, correct
        .gutter         (mem_gutter),
        .disable_filter (disable_filter_mem)
// bio_bdma.sv:1477-1478 — peri_filter, WRONG SIGNAL
        .gutter         (peri_gutter),
        .disable_filter (disable_filter_mem)
// bio_bdma.sv:2555-2557 — one bit unconditionally opens both paths
        allow_write = |match_write | disable_filter;
        allow_read = |match_read | disable_filter;
```
Documentation (`docs/src/ch02-00-bio-overview.md:804-805`):
> `[6] DISABLE_FILTER_PERI — When 1, disables the host peripheral range whitelist filter.`
> `[7] DISABLE_FILTER_MEM — When 1, disables the host memory range whitelist filter.`

**Preconditions.** Firmware sets `SFR_CONFIG` bit [7] — an operation the documentation describes as affecting only the memory range. The attacker must be able to place a program in the BIO instruction RAM and start the BIO, which requires only APB write access to `0x5012_4000`/`0x5012_5000`–`0x5012_8FFF` (no lock bit, no privilege check).

**Attack scenario.** Firmware performs the documented, apparently memory-only operation of setting bit [7] to let a BIO program stream through main memory, deliberately leaving bit [6] clear and the whitelist windows empty, believing peripheral access remains blocked. Because of line 1478, `allow_write`/`allow_read` in the peripheral filter are now unconditionally 1. The attacker's BIO program issues loads/stores to any address in `0x4000_0000`–`0x5FFF_FFFF`; these are decoded to the peripheral port, pass the now-disabled filter unmodified, and are emitted onto the AHB matrix reaching the entire peripheral map. Concretely reachable: the SCE unified crypto RAM at `0x4002_0000`–`0x4002_27FF` (unconditionally open while `scemode == 0`); the ReRAM mass-erase action register at `0x4000_00F0` (BAO-026); the sysctrl software resets at `0x4004_0080/84`; the AO/PMU voltage trims at `0x4006_0000` (BAO-023); the RAM timing trims at `0x4004_5000` (BAO-051); and `0x5012_4000` itself — the BIO's own configuration block, letting the program rewrite its own whitelist and gutters. Symmetrically, an operator who sets only bit [6] expecting to relax the peripheral filter gets no effect and may conclude the filter is not enforcing anything.

**Impact.** The documented containment guarantee for the BDMA is void on the peripheral side. A single documented-as-memory-only concession hands four PicoRV32 cores unfiltered access to every security peripheral on the chip.

**Mitigation (a) — RTL.** One line: change `bio_bdma.sv:1478` to `.disable_filter (disable_filter_peri)`.

**Mitigation (b) — fabricated silicon.** **Never set `SFR_CONFIG` bit [7].** Grant memory access exclusively through the four whitelist windows at `0x501240E0`–`0x501240FC`, and treat `DISABLE_FILTER_MEM` as a bit that must remain 0 for the lifetime of the system. Note that `DISABLE_FILTER_PERI` (bit 6) can be set or cleared freely with no effect and must not be relied on for anything.

**Verification notes.** Reproduced independently: both instances read in full, and a repo-wide grep for `disable_filter_peri` (all file types) returns exactly two hits — the declaration and the SFR packing. The documentation was quoted verbatim and matches. No compensating control exists: there is no second peri-side gate, no lock, and no `hauser`/`pprot` check on the ifsub APB path. Downstream reachability was confirmed: peri path → `ahbm` → `soc_ifsub` `bdma_ahb32` → `bmxcore.sv:225` → `bmx33s[1]` → `ahb_bmx33` → `core_ahb32`/`bmxif_ahb32`. Severity was lowered from critical to **high** because the precondition is that firmware sets a bit the vendor's own documentation already labels "strongly discouraged in secure applications" — a system that sets it has already surrendered the BDMA's memory-side containment including ReRAM. The unambiguous, always-present half of the defect is that the documented `DISABLE_FILTER_PERI` control is a dead net that silently does nothing.

---

<a id="bao-025"></a>

### BAO-025 — RRC master decode has no deny-by-default arm: per-slot disables and privilege checks are applied only to four recognised master IDs

**Severity: High | CWE-1259 | Threat actor: T1 | Confidence: High**

**Location:** `rtl/modules/rrc/rtl/rrc.sv:666-672`, consumed at `:712-726`, `:772`, `:815-819`

**Description.** `coreuser_mux` is a two-level conditional with no default arm: any transfer whose latched `hauser_reg` is not 0x2 (CM7A), 0x3/0x4 (VEXI/VEXD) or 0x5/0x6 (SCEA/SCES) silently inherits `coreuser_cm7`, the CM7's live execution-region identity. Worse, in that case `cm7sel`, `vexsel` and `scesel` are all 0, which deletes almost the whole of the key- and data-slot checks — every `core_rd_dis_k & (cm7sel|vexsel)` term, every `cm7sel&(!pri_op)` / `vexsel&(!vex_mm_reg)` privilege term, and both `scesel` terms evaluate to 0. The same holds for the code-region check, the INFO check, and the CFG check, where both `cfg_rd_dis`/`cfg_wr_dis` are ANDed with `(cm7sel|vexsel)` and `cfg_prev_dis` requires one of the three selects. This is the structural root of BAO-003; it also applies to the uDMA (0xA), the USB device controller (0xB), the SDDC (0x0), and the BDMA's AHB peripheral master which drives `hauser = '0`, should any routing change ever give them a path to the ReRAM slave.

**Evidence.**
```systemverilog
// rrc.sv:666-672 — three comparisons, no deny-by-default
assign cm7sel = ( hauser_reg == AMBAID4_CM7A );
assign vexsel = ( hauser_reg == AMBAID4_VEXI ) | ( hauser_reg == AMBAID4_VEXD );
assign scesel = ( hauser_reg == AMBAID4_SCEA ) | ( hauser_reg == AMBAID4_SCES );
assign coreuser_mux = scesel ? sceuser :
                        vexsel ? coreuser_vex : coreuser_cm7;
assign coreuser_in = coreuser_mux;
// rrc.sv:712-717 — with all three selects low, only the owner-nibble term survives
assign key_access_error_pre = (((coreuser_in[7:4] & userid_k[7:4])==0) & (ahb_write_flag | ahb_read_flag) |
                            ahb_read_flag & ((core_rd_dis_k & (cm7sel|vexsel)) | cm7sel&(!pri_op) | vexsel&(!vex_mm_reg)) |
                            ...
                            (!trustkey[akeyid] & (haddr_reg[15:6] != 10'h0))) & data_op & keysel & (userid_k[7:4] != 4'h0);
```

**Preconditions.** A master presenting an unrecognised `hauser` that reaches the ReRAM slave. Today the only such master is the BDMA at `hauser = 0x7` (BAO-003), which requires a ReRAM-covering whitelist window or `DISABLE_FILTER_MEM`.

**Attack scenario.** As BAO-003. The decisive consequence is at the CFG/ACRAM region: substituting an unrecognised `hauser`, `cfg_access_error_pre` collapses to a constant 0, so the boot0/boot1 requirement and the privileged-mode requirement both vanish and `0x603D_C000`–`0x603D_FFFF` becomes unconditionally readable and (with `rrccr[1]` and the magic word) NV-programmable. The attacker rewrites `userid_k`, `core_rd_dis_k` and `akeyid` for every slot and reads the key material out.

**Impact.** The RRC's access-control model fails **open** for any master it does not enumerate, with the offending master inheriting the identity of a different CPU. This is a fail-open default in the enforcement point for the chip's primary asset.

**Mitigation (a) — RTL.** Give `coreuser_mux` an explicit fail-closed default — `assign coreuser_mux = scesel ? sceuser : vexsel ? coreuser_vex : cm7sel ? coreuser_cm7 : 8'h00;` — so an unrecognised master matches no slot owner and is denied. Additionally restructure `rrc.sv:713-716` and `:723-726` so the per-slot disable bits are applied unconditionally rather than being qualified by `(cm7sel|vexsel)`, and add an explicit `unknown_master = ~(cm7sel|vexsel|scesel)` term forcing every access error. Give the BDMA a distinct AMBAID and apply the MDMA's ReRAM address exclusion to `bdma_axi32`.

**Mitigation (b) — fabricated silicon.** Prevent any unrecognised master from reaching ReRAM: never grant the BDMA a whitelist window over `0x6000_0000`+, never set `DISABLE_FILTER_MEM`, and hold the BIO in reset or clock-gated when key material is resident. Provision key slots with `akeyid` values that require a real HMAC trust unlock, and never use `akeyid` 255 or key slots 0/1 for material that must be CPU-inaccessible.

**Verification notes.** The absence of a fail-closed arm was confirmed and the substitution independently re-derived. The AMBAID plumbing was verified end to end (`bio_bdma.sv:122/1360/1373`, `soc_ifsub.sv:344`, `daric_cfg_pkg.sv:72-77`) as was the routing to the ReRAM slave. `rrc.sv:722` tests `userid_k` rather than `userid_d`, but `keycfg` and `datacfg` are identical expressions (`rrc.sv:688-689`), so that is not an additional bug. Scope correction: the key-slot story is narrower than presented, because the `trustkey` term at `rrc.sv:717` is **not** master-qualified and still applies to slots other than 0/1; the finding is under-stated on the CFG region, where the check is identically zero. The permanently-trusted `truststate[255]` (`sce_sec.sv:123`) is confirmed.

---

<a id="bao-026"></a>

### BAO-026 — ReRAM mass erase ("suicide") is triggered by a single unlocked, unprivileged 32-bit store

**Severity: High | CWE-1233 | Threat actor: T1; glitch variant T2 | Confidence: High**

**Location:** `rtl/modules/rrc/rtl/rrc.sv:286`, `:256`, `:307`; primitive at `rtl/modules/amba/rtl/ahb_sfr.sv:340-344`

**Description.** `sfr_rrcar` is an action register at RRC SFR offset `0xF0` — documented as `RRC_SFR_RRCAR @ 0x400000f0` in the generated register documentation — instantiated with `.sfrlock(1'b0)`, i.e. hardwired unlocked. `ahb_ar` pulses `ar` on any write of the magic value; there is no key ladder, no two-phase arm/fire, no redundancy, and no reference to `coreuser`, `hauser`, `hprot` or any privilege input anywhere on the RRC's SFR AHB port. `rrcar_suicide` then starts the erase FSM, which sweeps the entire main array and the entire INFO/IFR block programming zeros. This destroys the secure-boot code, all key slots, all data slots, the ACRAM CFG backing store, the NVR config words and the one-way counters. Every other security control in the RRC is bypassed, because the suicide FSM feeds the array address and data directly and never consults `cmd_user_write_dis`.

**Evidence.**
```systemverilog
// rrc.sv:256, :286 — one magic value, no lock, no privilege
localparam PM_RRAM_SUICIDE = 16'h2468;
ahb_ar #(.A('hF0), .AR(PM_RRAM_SUICIDE))    sfr_rrcar       (.ar(rrcar_suicide), .resetn(coreresetn), .sfrlock(1'b0), .*);
// rrc.sv:307, :867 — and what it does
`theregfull(clktop, sysresetn, suicide_start, '0) <= ((cmscode == CMS_SCDE) | rrcar_suicide) & (!suicide_reg) & (!suicide_start) & (suicide_adr_main == 'h0) ? 1'b1 :
assign axi_din = suicide_reg ? 256'h0 :
// ahb_sfr.sv:340-342 — the entire trigger: one 32-bit compare
    assign reg_write_en = reg_write_en0 & sfrsel;
    `theregfull(hclk, resetn, ar, '0) <= reg_write_en & ( reg_wdata == AR );
// soc_coresub.sv:823-824 — the SFR port is the raw peripheral bus, no identity filter
   .ahbs           (coreahbmux[0]  ),
   .ahbx           (coreahbmux[0]  ),
```

**Preconditions.** One 32-bit write to `0x4000_00F0` from any master on the core peripheral bus. No privilege level, no `coreuser` value, no lifecycle mode.

**Attack scenario.** Any code able to store `0x0000_2468` to `0x4000_00F0` does so. `ahb_ar` compares and pulses `rrcar_suicide`. `suicide_reg` sets, `ahbarray.hready` drops so the entire ReRAM slave stalls, and the FSM programs zeros into every main-array word and then every IFR/INFO word. On completion the device has no boot code, no keys, no lifecycle configuration and no ACRAM backing store; `nvrcfgdata` reads all zeros on the next reset. The write is reachable from CM7 AHB-P, Vex AHB-P, the BIO/BDMA AHB master and the MDMA, none of which is filtered on the `0x4000_0000` window. It is also a single-point comparison against a 16-bit constant on a 32-bit bus, so it is a plausible fault-injection target as well as a software one: a fault forcing `reg_wdata == AR` true during any unrelated write to offset `0xF0`, or forcing `sfrsel`, destroys the part.

**Impact.** Permanent, unrecoverable bricking of the device by one unprivileged store, or by one well-placed glitch.

**Mitigation (a) — RTL.** (a) Drive a real `sfrlock` on `sfr_rrcar` — a write-once enable that boot0/boot1 sets and clears before handing off. (b) Require boot-stage `coreuser` (`coreuser_in[5]|coreuser_in[4]`) and `pri_op`/`vex_mm_reg` on the RRC SFR port generally, which today has no identity filter at all — `rrc.sv:274-286` shows every SFR in the module is `.sfrlock(1'b0)`, so this is a systemic pattern. (c) Make the trigger redundant and non-glitchable: a two-register arm/fire sequence with distinct magic values written in order, plus a recency counter. Independently, fix `ahb_ar` to honour its `sfrlock` input at all (BAO-071).

**Mitigation (b) — fabricated silicon.** None inside the RRC — the register cannot be locked. The only containment is to make `0x4000_0000`–`0x4000_0FFF` unreachable to all non-boot code: enable the CM7 MPU, configure Vex regions to exclude it (noting BAO-077), and keep the BIO/BDMA and MDMA held in reset or clock-gated whenever untrusted code is running.

**Verification notes.** All quotes verbatim; `ahb_sfr.sv:286-344` was read in full and the module has no `hauser`/`hprot`/`coreuser` port at all. The generated documentation independently confirms the register and the magic value. Bus reachability was re-verified through `ahb_demux_map` with no identity filter, and both `bdma_ahb32` and `mdma_ahb32demux[1]` were confirmed to feed the same `core_ahb32` path. Two nuances: the erase cannot be repeated without a `sysresetn` (one pass destroys everything anyway), and `ahbarray.hready` low for the duration means any master mid-fetch locks up rather than faulting.

---

<a id="bao-027"></a>

### BAO-027 — All five ReRAM access-control checks are qualified by `data_op`, so an instruction fetch bypasses every one of them

**Severity: High | CWE-1220 | Threat actor: T1 | Confidence: High** *(verifier-surfaced)*

**Location:** `rtl/modules/rrc/rtl/rrc.sv:678-679`, `:717`, `:726`, `:774`, `:782`, `:819`, `:828`

**Description.** `rrc.sv:678-679` derive `inst_op = axprot_reg[2]` and `data_op = !axprot_reg[2]`. Every access-control decision in the module is then ANDed with `data_op`: the key check, the data check, the code-data check, the INFO check and the CFG check. The only term surviving an instruction fetch is `code_access_error_inst`, which is additionally restricted to `& codesel` — the code region only, `haddr_reg[31:12] < 20'h603D_A`. Consequently, for any transfer with `AxPROT[2] = 1` targeting the key region (`0x603F_xxxx`), the data region (`0x603E_xxxx`), the CFG descriptor region (`0x603D_C000`–`0x603D_FFFF`) or the INFO region, `cmd_user_read_dis` is identically 0 and the raw 256-bit ReRAM word is returned. This is not a theoretical `AxPROT` value: `VexRiscv_CramSoC.sv:7508` hardwires `iBusAxi_ar_payload_prot = 3'b110` and the Vex I-bus AXI is wired straight to the ReRAM slave; CM7 instruction fetches likewise set `ARPROT[2]` per AMBA.

**Evidence.**
```systemverilog
// rrc.sv:678-679
    assign inst_op = axprot_reg[2];
    assign data_op = !axprot_reg[2];
// rrc.sv:717, :726, :774, :782, :819 — every check dies on data_op
                                (!trustkey[akeyid] & (haddr_reg[15:6] != 10'h0))) & data_op & keysel & (userid_k[7:4] != 4'h0);
                                ... ) & data_op & datasel & (userid_d[7:4] != 4'h0);
                                ... ) & data_op & codesel;
                                ... ) & axi_info & data_op;
                                ... ) & data_op;
// rrc.sv:770 — the only ifetch check is scoped to the code region, which excludes 0x603E/0x603F
    assign code_access_error_inst = rrsub_code_dis_trustkey & ahb_read_flag & (cm7sel|vexsel) & inst_op & codesel;
// rrc.sv:828 — so nothing masks the read data
    assign cmd_user_read_dis = (key_access_error | data_access_error | info_access_error | code_access_error | cfg_access_error) & ahb_read_flag;
```

**Preconditions.** The ability to set the PC to an arbitrary physical address on either CPU. On the Vex this is trivial at any privilege whenever `satp.MODE == 0`, because there is no PMP (BAO-077).

**Attack scenario.** Attacker runs unprivileged code on the VexRiscv.
1. Install a trap handler for illegal-instruction exceptions.
2. Branch to a ReRAM key-slot address, e.g. `0x603F_0000`. The I-bus issues AR with `ARPROT = 3'b110`, so `data_op = 0`. `key_access_error_pre` is ANDed with `data_op` and evaluates to 0 regardless of `userid_k`, `core_rd_dis_k`, `pri_op` or `trustkey[akeyid]`. `code_access_error_inst` does not apply because `codesel` is false at `0x603F`. `cmd_user_read_dis = 0`, so the key words are returned verbatim as instruction data.
3. The fetched key words execute. Any word that is not a legal RV32 encoding raises an illegal-instruction exception, and VexRiscv places the full 32-bit faulting encoding into `mtval`. The handler reads `mtval`, records the word, advances `mepc` and returns.
4. Walking the address range extracts key material word by word. The same technique reads the CFG descriptor region at `0x603D_C000` and the data slots at `0x603E_xxxx`.

On the CM7 the same fetch succeeds and the data is returned, though extraction is noisier (an execution/fault oracle rather than a direct `mtval` read).

**Impact.** Complete bypass of the ReRAM access-control model for reads, by the ordinary act of branching to the key region. No register writes, no timing, no fault injection.

**Mitigation (a) — RTL.** Qualify the checks on `(inst_op | data_op)` rather than `data_op` — i.e. drop the `data_op` term for the key, data, CFG and INFO regions entirely — and deny instruction fetch to those regions outright.

**Mitigation (b) — fabricated silicon.** Prevent both CPUs from ever fetching outside the code region. On the CM7 this requires an MPU configuration marking `0x603D_A000`–`0x603F_FFFF` execute-never; on the Vex it requires Sv32 paging with those pages non-executable, plus never returning to Bare mode (BAO-077). Neither is enforced by hardware.

**Verification notes.** Surfaced by the verifier. All five `& data_op` qualifications and the `codesel` bound were confirmed verbatim, and the region constants (`PM_CODE_REGION_BORDER = 20'h603D_A`, `PM_KEY_REGION = 16'h603F`, `PM_DATA_REGION = 16'h603E`) were recomputed to confirm the key and data regions lie above the code border and therefore fail `codesel`. The Vex I-bus constant prot value and its routing to the ReRAM slave were confirmed; see BAO-031 for the CPU-side view of the same defect.

---

<a id="bao-028"></a>

### BAO-028 — Vex fabric identity (`coreuser`) is selected by a software-written `satp.ASID`, is not bound to the executing code region, and ignores `satp.MODE`

**Severity: High | CWE-1220 | Threat actor: T1 | Confidence: High**

**Location:** `rtl/modules/vexriscv/rtl/cram_axi.sv:5814-5849`, `:20921-20922`, `:212-213`; consumed at `rrc.sv:670-671`, `:712`, `:815`

**Description.** The 8-bit `coreuser` bundle that the ReRAM controller uses to decide which key slots, data slots and CFG words the RISC-V core may read is produced by comparing `cramsoc_satp_asid` — the ASID field of the software-written `satp` CSR — against eight software-loaded LUT entries. There is no hardware relationship between this tag and where the CPU is executing, and no qualification on `satp.MODE`: `cramsoc_satp_mode` is declared and connected to the CPU but referenced nowhere else in the 23 156-line file, i.e. it is a dangling net. Meanwhile the CPU writes `MmuPlugin_satp_asid` unconditionally on any `satp` write regardless of the mode bit. Any code that can execute `csrw satp` — S-mode or M-mode — therefore selects its own fabric identity, including the privileged boot0/boot1 identities, while simultaneously being free to set `satp.MODE = 0` (Bare) so that no page-table translation or permission check applies at all. This is in direct contrast to the CM7, whose `coreuser` is generated by a hardware PC-range comparator against ReRAM-defined region bounds (`cm7sys.sv:754-761`) and therefore cannot be spoofed by the software running on it. The `coreuser_protect` lock only freezes the ASID→identity LUT; it does not constrain which ASID software may load.

**Evidence.**
```systemverilog
// cram_axi.sv:212-213 — satp_mode is declared and connected, then never used
  wire          cramsoc_satp_mode;
  wire    [8:0] cramsoc_satp_asid;
// cram_axi.sv:5814-5818 — the identity is an ASID lookup
  always @(*) begin
      coreuser_coreuser_2bit <= 2'd0;
      if ((cramsoc_satp_asid == {1'd0, coreuser_lut01})) begin
          coreuser_coreuser_2bit <= coreuser_user01;
      end else begin
// cram_axi.sv:20921-20922 — and becomes the fabric tag
      coreuser_vex[7:4] <= coreuser_coreuser_4bit;
// VexRiscv_CramSoC.v:8288-8292 — ASID stored regardless of MODE
        if(execute_CsrPlugin_csr_384) begin
          if(execute_CsrPlugin_writeEnable) begin
            MmuPlugin_satp_mode <= CsrPlugin_csrMapping_writeDataSignal[31];
            MmuPlugin_satp_asid <= CsrPlugin_csrMapping_writeDataSignal[30 : 22];
// rrc.sv:670-671, :712 — the consumer
    assign coreuser_mux = scesel ? sceuser : vexsel ? coreuser_vex : coreuser_cm7;
    assign key_access_error_pre = (((coreuser_in[7:4] & userid_k[7:4])==0) & (ahb_write_flag | ahb_read_flag) |
```

**Preconditions.** Code execution at S-mode or M-mode on the Vex, and `coreuser_enable1 == 1` (the intended operating state — with it clear, the identity comes from the ReRAM `default_user` instead; see BAO-029). Works whether or not `coreuser_protect` has been set, since protect only freezes the LUT contents.

**Attack scenario.**
1. The attacker obtains code execution in the S-mode kernel context on the Vex — a kernel bug, or simply any of the four ReRAM identities that legitimately runs at S/M and wants to escalate.
2. Reads the eight configured LUT entries at `0xE000_2008`/`0x200C`/`0x2010` — readable even after `coreuser_protect`, because protect only freezes the shadow copy.
3. Picks the ASID whose `uservalue` maps to `coreuser` bit [4] (boot0) or [5] (boot1).
4. Executes `csrw satp, (asid<<22)` with MODE = 0 and PPN = 0. One cycle later `coreuser_vex[7:4]` presents the boot0 identity to the RRC and, simultaneously, all address translation is disabled, giving a flat physical address space.
5. Loads from the ReRAM key window `0x603F_xxxx`. The `(coreuser_in[7:4] & userid_k[7:4]) == 0` test now passes for every boot0-owned slot, and `cfg_prev_dis` also passes because `coreuser_in[4]` is set, giving access to the `0x603D_C000` CFG/ACRAM region that holds the dev-mode magic word. Key material and the access-control table are read out.

**Impact.** The Vex's fabric privilege tag is software-selectable by the software it is meant to constrain, and the same instruction that selects it also disables the MMU. The four `coreuser` "identities" sharing this CPU have no hardware isolation from each other.

**Mitigation (a) — RTL.** Derive the Vex tag the way the CM7 does — from a hardware comparator on the fetch PC against the ReRAM-programmed region bounds. At minimum, gate the LUT lookup on `cramsoc_satp_mode` (force the least-privileged identity when MODE == 0) and force the least-privileged identity whenever `cramsoc_privilege == 2'b11` with no translation.

**Mitigation (b) — fabricated silicon.** (a) Have boot0 program all eight LUT entries to the *same*, least-privileged uservalue and then set `coreuser_protect`, so no ASID selects a privileged identity; rely solely on ACRAM slot ownership assigned to that single identity. (b) Ensure the ACRAM descriptors for all sensitive key slots use owner nibbles that no reachable ASID maps to. (c) Never leave a privileged identity reachable by an ASID that untrusted code can install.

**Verification notes.** All lines confirmed. An exhaustive grep for `cramsoc_satp_mode` in `cram_axi.sv` returns exactly two hits — the declaration and the port connection — so it is genuinely dangling and `satp.MODE` never qualifies the tag. `satp` is CSR 0x180 whose `[9:8] == 2'b01`, so the privilege gate at `VexRiscv_CramSoC.v:7466` admits S-mode and M-mode. `mstatus.TVM` is not implemented anywhere, so `satp` access cannot be trapped. The contrast with the CM7 is real, including the debounce filter the Vex path lacks entirely. Scope correction: the attack requires `coreuser_enable1 == 1` (`cram_axi.sv:5851-5883`); otherwise the identity comes from the ReRAM `default_user`. The finding's secondary note about in-flight re-tagging is independently confirmed — `rrc.sv:660-664` latches `axid_reg`/`axprot_reg`/`vex_mm_reg` at the AXI handshake but `rrc.sv:670-672` consumes `coreuser_vex` live and unlatched — though it adds no capability beyond writing the ASID first.

---

<a id="bao-029"></a>

### BAO-029 — `vex_mm`, the "CPU is privileged" signal the ReRAM controller trusts, is not the hardware privilege level: it is a ReRAM constant in one configuration and invertible by an unprotected software bit in the other

**Severity: High | CWE-1231 / CWE-1220 | Threat actor: T1 | Confidence: High**

**Location:** `rtl/modules/vexriscv/rtl/cram_axi.sv:20923-20927`, `:13177-13178`; consumed at `rrc.sv:713-714`, `:723-724`, `:781-782`, `:815`

**Description.** The RRC uses `vex_mm` as the sole privilege discriminator for every Vex ReRAM access — `vexsel & (!vex_mm_reg)` appears as a deny term in the key check, the data check, the INFO check and the CFG check. That signal is generated as follows. When `coreuser_enable1 == 0`, `vex_mm` is driven by `default_mm`, a static constant from the ReRAM configuration word (`soc_coresub.sv:276`), which the reference default image sets to 1 (`nvrcfgs.sv:69`). In that state the RRC believes every Vex transfer is privileged no matter what `CsrPlugin_privilege` actually is, including U-mode transfers. When `coreuser_enable1 == 1`, `vex_mm` is still not the raw privilege: it is `(privilege[0] | privilege[1]) ^ coreuser_invert_priv1`, where `coreuser_invert_priv1` is bit 1 of the `coreuser_control` register — an ordinary read/write memory-mapped bit. With that bit set, the polarity of the entire privilege decision is flipped: U-mode presents `vex_mm = 1` (privileged) to the RRC, and M-mode presents 0. There is no redundancy, no majority vote and no independent check anywhere in the path.

**Evidence.**
```systemverilog
// cram_axi.sv:20923-20927 — a software-controlled XOR, and a non-CPU-derived fallback
      if (coreuser_enable1) begin
          vex_mm <= ((cramsoc_privilege[0] | cramsoc_privilege[1]) ^ coreuser_invert_priv1);
      end else begin
          vex_mm <= default_mm;
      end
// cram_axi.sv:13177-13178 — both control bits are plain register bits
  assign coreuser_enable0 = coreuser_control_storage[0];
  assign coreuser_invert_priv0 = coreuser_control_storage[1];
// nvrcfgs.sv:69 and soc_coresub.sv:276 — the reference config sets the fallback to "privileged"
          rv_def_mm      : '1,  //15
      assign vexcfg_def_mm = nvrcfgdata.cfgrrsub.rv_def_mm;
// rrc.sv:713-714, :815 — the sole Vex privilege term
                              ahb_read_flag & ((core_rd_dis_k & (cm7sel|vexsel)) | cm7sel&(!pri_op) | vexsel&(!vex_mm_reg)) |
      assign cfg_prev_dis = (((!(coreuser_in[5] | coreuser_in[4])) & (cm7sel|vexsel)) | cm7sel&(!pri_op) | vexsel&(!vex_mm_reg) | scesel)
```

**Preconditions.** Path A: the ReRAM `cfgrrsub` word carries `rv_def_mm = 1` (the reference default) and boot firmware has not enabled the coreuser block. Path B: write access to the CPU-internal CSR bank at `0xE000_2000` before `coreuser_protect` is set (BAO-030).

**Attack scenario.** **Path A:** the shipped ReRAM configuration sets `rv_def_mm = 1` and firmware never sets `coreuser_enable1`. `vex_mm` is then hard 1 forever, so every Vex ReRAM access — including one issued by U-mode application code — is presented to the RRC as privileged. Combined with `default_user = 0`, `coreuser_vex[4]` (boot0) is asserted, so the RRC sees "boot0, machine mode" for unprivileged application code: `cfg_prev_dis` is 0 and the key-slot owner test passes for every boot0-owned slot. U-mode reads out boot0 key slots and the CFG/ACRAM region.

**Path B:** an attacker able to reach `0xE000_2000` (BAO-030) writes `0b11` to `coreuser_control`, setting both enable and invert. It then drops to U-mode; `vex_mm` becomes `(0|0)^1 = 1`, so the RRC treats U-mode as privileged, while any genuine M-mode secure handler is downgraded to `vex_mm = 0` and loses its own ReRAM access.

**Impact.** A privilege signal with a software-controlled polarity and a non-CPU-derived constant override, feeding the ReRAM access-control model.

**Mitigation (a) — RTL.** Drive `vex_mm` directly and unconditionally from `cramsoc_privilege`; delete both the `default_mm` fallback and the `coreuser_invert_priv1` XOR. A privilege signal must never have a software-controlled polarity or a software-selectable constant override. If a pre-configuration default is required it must be the *deny* value (0).

**Mitigation (b) — fabricated silicon.** Boot0 must, as one of its first actions, program the ReRAM `cfgrrsub` word with `rv_def_mm = 0`, then write `coreuser_control = 0x1` (enable set, invert **clear**), program the LUT, and immediately write `coreuser_protect = 1` — before any lower-privilege code runs and before enabling any interrupt that could vector into attacker code. Verify by reading `coreuser_status` (`0xE000_2004`) bit 8 in both M-mode and U-mode and confirming it tracks the actual privilege.

**Verification notes.** All lines confirmed verbatim; `coreuser_invert_priv0` is an ordinary R/W CSR bit in a bank with no privilege qualification, shadowed to `coreuser_invert_priv1`. `default_mm` was traced cleanly from `cram_axi.sv:165` through `vexsys.sv` to `soc_coresub.sv:276` and the ReRAM field. `vex_mm` is consumed only by `rrc.sv`, confirming there is no second, redundant privilege input on the Vex path. **Path A is overstated on one point and must be corrected before it goes to the vendor:** in the ASIC path `nvrcfgdata` is not the `defcfgrrsub` literal — `brc.sv:120` is inside `` `ifdef FPGA ``, while the silicon path is `brc.sv:131` (`assign nvrcfgdata = syscfgdata;`) where `syscfgdata` is a register bank reset to 0. The *hardware reset* value of `default_mm` on silicon is therefore 0 (deny). Path A reduces to: if the shipped ReRAM boot record carries the reference `rv_def_mm = '1` and firmware never sets `coreuser_enable1`, `vex_mm` is stuck at 1 and U-mode transfers are presented as privileged. That is a real configuration-image exposure, not a reset-state exposure. Second minor point: `(privilege[0]|privilege[1])` maps S-mode to `vex_mm = 1` as well as M-mode, which is consistent with the CM7's `pri_op = axprot_reg[0]` ("not user") and is by design.

---

<a id="bao-030"></a>

### BAO-030 — The coreuser identity/privilege configuration block is a plain memory-mapped register bank on the CPU's own data bus, with no privilege qualification

**Severity: High | CWE-1262 | Threat actor: T1 | Confidence: High**

**Location:** `rtl/modules/vexriscv/rtl/cram_axi.sv:13121`, `:13168-13175`, `:21147-21149`, `:22889-22895`

**Description.** The registers that define the Vex's entire fabric identity — `coreuser_control` (enable + invert_priv), `coreuser_map_lo`, `coreuser_map_hi`, `coreuser_uservalue` and `coreuser_protect` — live in a LiteX CSR bank at `0xE000_2000`, decoded off the CPU's ordinary load/store path. The AXI `AxPROT` signals are carried the whole way and are **never used in any comparison anywhere in the file** — every occurrence is a pass-through assignment — so there is no M/S/U qualification on writes to this bank. The only mitigation is `coreuser_protect`, a set-only FDRE that freezes the shadow registers; but it gates only the shadow copy, so writes to the storage registers always land, and it is cleared by `sys_rst`.

**Evidence.**
```systemverilog
// cram_axi.sv:5675, :16499, :13121 — the bank sits at 0xE000_2000 on the dbus
  assign socbushandler_slave_sel_dec0 = (slice_proxy0[29:16] == 14'd14336);
  assign slice_proxy0 = cramsoc_corecsr_aw_payload_addr[31:2];
  assign csrbank0_sel = (interface0_bank_bus_adr[15:10] == 2'd2);
// cram_axi.sv:13168-13175 — write path, no privilege term
  assign csrbank0_protect0_r = interface0_bank_bus_dat_w[0];
      if ((csrbank0_sel & (interface0_bank_bus_adr[9:0] == 3'd5))) begin
          csrbank0_protect0_re <= interface0_bank_bus_we;
          csrbank0_protect0_we <= csrbank0_re;
// cram_axi.sv:22889-22895 — the lock is cleared by sys_rst
  fdre_cosim fdre_cosim(
  	.CE(coreuser_protect_storage),
  	.D(1'd1),
  	.R(sys_rst),
  	.Q(coreuser_protect)
  );
```

**Preconditions.** A store to physical address `0xE000_2000` from the Vex. Trivial from M-mode or S-mode; trivial from U-mode whenever `satp.MODE == 0`, which — because there is no PMP (BAO-077) — means any privilege level in Bare mode.

**Attack scenario.** The attacker has code execution on the Vex at any level that can store to `0xE000_2000`. Before boot firmware sets `coreuser_protect`, it writes `coreuser_map_lo`/`map_hi` at `0xE000_2008`/`0x200C` to make its own ASID match entry 0, writes `coreuser_uservalue` at `0xE000_2010` to map that entry to the boot0 uservalue, and writes `coreuser_control = 0x1` at `0xE000_2000`. One cycle later the RRC sees the attacker as boot0 and reads of `0x603F_xxxx` key slots succeed. Alternatively it sets `coreuser_invert_priv` and drops to U-mode, which the RRC then treats as privileged (BAO-029). The same unqualified bank also contains `irqarrayN_soft_storage`, so the same primitive lets unprivileged code inject arbitrary interrupts.

**Impact.** The Vex's entire fabric identity is set by an unqualified store on the CPU's own load/store path. This is the root enabler for BAO-028 and BAO-029.

**Mitigation (a) — RTL.** Qualify the `csrbank0` write enables with the incoming `AxPROT[0]` privileged bit so only M-mode stores can write the bank, and additionally gate them on `~coreuser_protect` so that once locked the *storage* registers are frozen too, not just the shadows. Move `coreuser_protect` to a reset domain that a software-triggered warm reset cannot clear.

**Mitigation (b) — fabricated silicon.** Boot0/boot1 must program the full coreuser configuration and write `coreuser_protect = 1` at `0xE000_2014` before enabling any interrupt or executing any code it does not control. The S-mode kernel must never map physical page `0xE000_2000` into any U-mode address space. Note that under BAO-077 an S-mode attacker can reach it regardless by clearing `satp`.

**Verification notes.** The address decode was reproduced numerically end to end. All 44 occurrences of `payload_prot` in `cram_axi.sv` were checked and every one is a pass-through or a port connection — `AxPROT` is never compared, so there is genuinely no privilege qualification. The FDRE's `sys_rst` derivation was traced to `~resetn_vex`. **One attack step was refuted and removed:** the original claimed an attacker could pre-load the storage registers, then trigger a warm reset to clear `protect` and have the shadows reload from attacker values. `sys_rst` clears the storage registers too — `cram_axi.sv:22387/22392/22396/22398/22418` reset `coreuser_control_storage`, `map_lo_storage`, `uservalue_storage`, `protect_storage` and `user_default` — and the warm reset also resets the Vex itself, so the attacker's code stops running. What the warm reset actually does is return the block to `coreuser_enable1 == 0`, i.e. the `default_mm`/`default_user` state of BAO-029 — a real concern, but a different one. Also, the bank is behind the Vex's own internal crossbar, so it is reachable only from the Vex, not from any bus master. One citation correction: the crossbar constants are at `cram_axi.sv:22958-22961`.

---

<a id="bao-031"></a>

### BAO-031 — Vex instruction fetch hardwires `AxPROT[2] = 1`, and every RRC access-control check is qualified by `data_op` — so an instruction fetch reads ReRAM key slots with no access control at all

**Severity: High | CWE-1220 | Threat actor: T1 | Confidence: High** *(verifier-surfaced)*

**Location:** `VexRiscv/VexRiscv_CramSoC.v:7484`; `rtl/modules/vexriscv/rtl/cram_axi.sv:5132`; `rtl/modules/core/rtl/vexsys.sv:269`; consumed at `rrc.sv:678-679` and the five checks

**Description.** The CPU-side view of BAO-027. The Vex's instruction-fetch AXI port drives a constant `AxPROT` of `3'b110` — instruction fetch, non-secure, unprivileged — passed through `cram_axi` and `vexsys` to the fabric with `aruser = AMBAID4_VEXI`, so the RRC classifies it as `vexsel` and as `inst_op`. Because all five RRC checks are ANDed with `data_op`, and the one instruction-fetch check is scoped to the code region only, an instruction fetch of the key region (`0x603F_xxxx`), the data region (`0x603E_xxxx`) or the CFG region returns raw contents. The `coreuser` owner check, the `vex_mm` privilege check, the `core_rd_dis` bit and the `trustkey` check are all bypassed simultaneously. This is independent of BAO-028/029/030 — it does not require the attacker to control the `coreuser` tag at all.

**Evidence.**
```systemverilog
// VexRiscv_CramSoC.v:7484 — constant AxPROT on the instruction bus
  assign iBusAxi_ar_payload_prot = 3'b110;
// rrc.sv:678-679, :717 — and every check is qualified by its complement
    assign inst_op = axprot_reg[2];
    assign data_op = !axprot_reg[2];
                                (!trustkey[akeyid] & (haddr_reg[15:6] != 10'h0))) & data_op & keysel & (userid_k[7:4] != 4'h0);
// rrc.sv:770, :686, :644 — the ifetch check covers only addresses BELOW the code border
    assign code_access_error_inst = rrsub_code_dis_trustkey & ahb_read_flag & (cm7sel|vexsel) & inst_op & codesel;
    assign codesel = ( haddr_reg[31:12] < PM_CODE_REGION_BORDER );
    localparam PM_CODE_REGION_BORDER = 20'h603D_A;
// bmxcore.sv:293-295 — the I-bus reaches the ReRAM slave
    .s3         (vex_iaxi),
    .m0         (rrc_axi64),
```

**Preconditions.** Code execution on the Vex able to set the PC to an arbitrary physical address — M-mode or S-mode always, and U-mode whenever `satp.MODE == 0` (no PMP, BAO-077).

**Attack scenario.** As BAO-027, with the Vex-specific extraction detail: because `catchIllegalInstruction` is enabled and `decodeExceptionPort_payload_badAddr = decode_INSTRUCTION`, an illegal encoding places the fetched 32-bit word verbatim into `mtval`/`stval`. The attacker installs a trap handler, jumps to `0x603F_0000`, and reads out key material one word per trap; legal encodings are recovered from their architectural side effects and from `mepc` deltas.

**Impact.** Direct, software-only readout of ReRAM key slots, data slots and the CFG/ACRAM region, with every access-control check structurally inapplicable.

**Mitigation (a) — RTL.** Fix the RRC (BAO-027): do not qualify the key/data/CFG/INFO checks on `data_op`, and deny instruction fetch to those regions outright. On the CPU side, the constant `3'b110` is architecturally correct for an instruction fetch and is not itself the defect.

**Mitigation (b) — fabricated silicon.** The Vex must be prevented from fetching outside the code region — Sv32 paging with the key/data/CFG pages non-executable, established before any untrusted code runs and never relaxed. There is no hardware backstop (no PMP), so this is entirely a firmware discipline.

**Verification notes.** Surfaced by the verifier. The constant, its propagation (`cram_axi.sv:5132` → `vexsys.sv:269` with `iaxim.aruser = AXIIID4 = AMBAID4_VEXI = 4'h3`) and the routing to `rrc_axi64` were all confirmed, as were the `data_op` qualifications and the `codesel` bound that excludes `0x603E`/`0x603F`. The `mtval` extraction path was confirmed at `VexRiscv_CramSoC.v:5444` and `:8497`.

---

<a id="bao-032"></a>

### BAO-032 — Modular inverse is an unblinded binary extended-Euclidean algorithm whose branch sequence and iteration count are a direct function of the secret operand

**Severity: Medium** | CWE-208 Observable Timing Discrepancy | Threat actor: T1 (timing, via sfr_tickcnt) and T2 (SPA/EM, since each branch drives a distinct sequence of long-word RAM operations) | Confidence: High

**Location:** `rtl/modules/crypto_pke/rtl/PkeCtrl.sv:1933`

**Description.** `ModInvState` implements the classical binary extended Euclidean algorithm (Menezes Alg. 14.61) with fully data-dependent control flow. Every loop iteration branches on the parity and relative magnitude of the working values:

- MI_JUDGE1 branches three ways on `Y3IsEven` / `X3IsEven` (line 1937-1942), selecting either a Y-halving chain, an X-halving chain, or a compare.
- MI_JUDGE2 / MI_JUDGE3 branch on `~X1IsEven | ~X2IsEven` (line 1953) and `~Y1IsEven | ~Y2IsEven` (line 1995), inserting two extra multi-word operations (MI_X1ADDU + MI_X2SUBV, or MI_Y1ADDU + MI_Y2SUBV) only when the low bit is set.
- MI_X3CMPY3 branches three ways on the sign/zero result of a long compare (lines 2030-2035).
- MI_Y2ADDP / MI_Y2SUBP loop an unbounded, sign-dependent number of times (lines 2099-2116).

Each of those states waits on `LongAlgDone` from `com_alg`, i.e. each is a full N-word RAM pass. The total number of such passes — and hence the operation's cycle count — is therefore a direct readout of the bit pattern of the secret input. There is no dummy-operation balancing and no constant-time alternative in this block.

**Evidence.**
```systemverilog
PkeCtrl.sv:1933-1943
    MI_JUDGE1:
    begin
        if(ErrorDetect)
            NextModInvState = MI_END;
        else if(Y3IsEven)
            NextModInvState = MI_Y3DIV2;
        else if(X3IsEven)
            NextModInvState = MI_X3DIV2;
        else
            NextModInvState = MI_X3CMPY3;
    end

PkeCtrl.sv:1951-1957
    MI_JUDGE2:
    begin
        if(~X1IsEven | ~X2IsEven)
            NextModInvState = MI_X1ADDU;
        else
            NextModInvState = MI_X1DIV2;
    end

PkeCtrl.sv:2028-2038
    MI_X3CMPY3:
    begin
        if(LongAlgDone & ResultIsZero)
            NextModInvState = MI_Y3SUB1;
        else if(LongAlgDone & ResultIsNeg)
            NextModInvState = MI_Y1SUBX1;
        else if(LongAlgDone )
            NextModInvState = MI_X1SUBY1;
        else
            NextModInvState = ModInvState;
    end

PkeCtrl.sv:2108-2116 (unbounded sign-dependent correction loop)
    MI_Y2SUBP:
    begin
        if(LongAlgDone & Y2IsNeg)
            NextModInvState = MI_Y2ADDP;
        else if(LongAlgDone)
            NextModInvState = MI_Y2SUBP;
        else
            NextModInvState = ModInvState;
    end

PkeCtrl.sv:2130-2131 (the branch conditions are the com_alg status flags)
assign ResultIsZero    = LongAlgSR[0];
assign ResultIsNeg     = LongAlgSR[1];
```

**Preconditions.** Firmware invokes the PKE ModInv primitive (`RsaModInv` / `EccModInv`, dispatched at PkeCtrl.sv:1213-1215) on a secret value — e.g. computing k^-1 mod n for an ECDSA signature, or inverting the projective Z coordinate at the end of a scalar multiply. No masking or blinding is applied to the ModInv input anywhere in PkeCore/PkeCtrl.

**Attack scenario.** 1. Victim firmware generates an ECDSA signature: it picks a nonce k, computes k*G on the PKE, then calls the PKE ModInv primitive to obtain k^-1 mod n.
2. Unprivileged attacker software reads `sfr_tickcnt` (0x4002_C054) immediately after the ModInv completes, obtaining the exact cycle count of that inversion.
3. The binary-EEA iteration count is a well-characterised function of the input: the number of MI_*DIV2 steps equals the total number of halvings, and the number of MI_JUDGE2/JUDGE3 'odd' detours equals the number of odd intermediates. This yields tens of bits of information about k per signature (and, with EM/power traces at T2, the full parity sequence, i.e. essentially all of k).
4. Partial knowledge of the nonce across a modest number of signatures recovers the ECDSA long-term private key by lattice attack (hidden number problem) — a few dozen signatures suffice if ~4-8 bits per nonce leak.
5. The same channel applies to any RSA use of ModInv on secret material (e.g. computing q^-1 mod p for CRT parameters).

**Mitigation.** RTL fix: replace the binary EEA with a constant-time inversion — either Fermat exponentiation (a^(n-2) mod n) reusing the existing constant-time ModExp ladder, or a constant-iteration-count safegcd/Bernstein-Yang divstep where each step performs the same operations and selects results with arithmetic masks instead of branching. At minimum, make MI_JUDGE2/MI_JUDGE3 always execute the ADDU/SUBV pair and discard the result when the parity condition is false, and bound MI_Y2ADDP/MI_Y2SUBP to a fixed iteration count.

Firmware workaround on fabricated silicon: never call ModInv on unblinded secret material. Blind the input multiplicatively before inversion — compute (k*r)^-1 * r instead of k^-1 for a fresh random r — which makes the observed iteration profile a function of the random blinding value rather than of k. For final-Z inversion in ECC, randomise the projective representation before conversion.

**Verification.** Independently confirmed by a second reviewer. Line anchor is exact: PkeCtrl.sv:1933 is `MI_JUDGE1:` and 1937-1942 are the Y3IsEven/X3IsEven/else three-way branch, verbatim as quoted. MI_JUDGE2 at 1951-1957 and MI_JUDGE3 at ~1995 branch on `~X1IsEven | ~X2IsEven` / `~Y1IsEven | ~Y2IsEven` and insert the MI_X1ADDU+MI_X2SUBV (resp. MI_Y1ADDU+MI_Y2SUBV) pair only on the odd path — each of those is a separate LongAlgDone-gated multi-word pass. MI_X3CMPY3 (2028-2038) branches three ways on ResultIsZero/ResultIsNeg, which are LongAlgSR[0]/[1] (2130-2131), verified. MI_Y2SUBP/MI_Y2ADDP (2099-2116) self-loop on Y2IsNeg with no fixed bound. Unlike finding 1 there is no configuration bit to avoid this — ModInv is a fixed primitive dispatched from PkeCtrl.sv:1213-1215 and reached unconditionally by EccM2I/EdM2I (StartModInv_M2I at 1858, StartModInv_EDM2I at 3495, OR-ed at 1875), so the ECC affine conversion path always runs it. I searched for blinding or dummy-operation balancing in PkeCore/PkeCtrl and found none. The only bound is ErrorDetect = (ModInvCnt >= 16'd32768) (PkeCtrl.sv:2481), a convergence watchdog, not a constant-time mechanism.

**Corrections applied by the verifier.** Worth adding for the vendor: the leak is not limited to explicit RsaModInv/EccModInv calls. StartModInv is also asserted from inside the ECC and Ed25519 Montgomery-to-affine conversions (PkeCtrl.sv:1858 `StartModInv_M2I = (EccM2IState == ECCM2I_MOVUT2U) & LongAlgDone`, 3495 for EdM2I, combined at 1875), so any scalar multiplication that ends in a coordinate conversion invokes the variable-time EEA on the projective Z value.

---

<a id="bao-033"></a>

### BAO-033 — Unbounded hash OUTPUT pointer gives an arbitrary chosen-value SCERAM write that bypasses scedma_ac and defeats the ifsob/ifskey key-exfil guard

**Severity: Medium**

**Location:** `rtl/modules/crypto_top/rtl/combohasha.sv:740`

*Surfaced by the independent verifier, not the original domain reviewer.*

**Description.** The finder covered only the read-side pointers. The write side has the identical defect and a different, independent impact. combohasha.sv:740 sets the DMA write-pointer start of every output transfer from a raw, range-unchecked software CR: `assign chnlo_cfg.wpptr_start = cr_segptrstart[SEGID_HOUT2];` where SEGID_HOUT2 = SEGID_SOB+1 = 7 (combohasha.sv:68), i.e. COMBOHASH_SFR_SEGPTR index 7 at 0x4002_B03C. sce_dmachnl.sv:127-129 clamps wpptr with exactly the same broken priority as rpptr — the `(wpptr > thewpsegcfg.segsize)` test is evaluated against the PREVIOUS wpptr, so `chnlstart ? thecfg.wpptr_start` is loaded verbatim and the first beat of every output transfer is written at `thewpsegcfg.segaddr + wpptr_start`, truncated to 12 bits by sce_memc.sv:212. Because combohash's write port is ramreq[9] (sce.sv:456), outside the `chnlreq[0:CHNLACCNT-1]` range scedma_ac filters (sce.sv:377-380), the per-segment ACRULEs write-deny is not applied at all. This yields an arbitrary-address SCERAM write of a value the attacker can choose by offline grinding of the message (2^32 offline hash evaluations for an exact 32-bit word). It writes into segments that ACRULEs deliberately make AHB-write-denied: SEG_SOB and SEG_PSOB (8'b10_00_10_00), SEG_POB (8'b00_00_00_10), and SEG_AOB (8'b10_10_10_10, the AES output buffer, write-denied on every channel). It also defeats the one explicit key-exfiltration guard in the block: combohasha.sv:230 forces opt_ifsob to 0 whenever the secret key segment was used, precisely so that an HMAC computed over SEG_SKEY can never reach the AHB-readable SEG_SOB — but the unbounded wpptr_start moves the MFSM_WB_HOUT write into SEG_SOB anyway.

**Evidence.**
```systemverilog
combohasha.sv:740
    assign chnlo_cfg.wpptr_start = cr_segptrstart[SEGID_HOUT2];

combohasha.sv:68
    localparam [7:0] SEGID_HOUT2 = scedma_pkg::SEGID_SOB + 1 ;

combohasha.sv:223 (8 raw 12-bit pointers, no range check)
    apb_cr #(.A('h20), .DW(scedma_pkg::AW), .SFRCNT(SEGCNT+1) )      sfr_segptr    (.cr(cr_segptrstart), .prdata32(),.*); //## width?

combohasha.sv:230 (the guard this defeats)
    `theregrn( opt_ifsob   ) <= optlock ? cr_opt.ifsob & ~cr_opt.ifskey  : opt_ifsob   ;

combohasha.sv:708-714 (the write that escapes SEG_HOUT)
            MFSM_WB_HOUT     :
                begin
                    chnlo_cfg.rpsegcfg = (cfg_hashtype==HT_SHA3) ? HASHSEG_MSG : HASHSEG_ST;
                    chnlo_cfg.wpsegcfg = SEG_HOUT;
          //          chnlo_cfg.wpptr_start = cr_segptrstart[SEGID_HOUT2];
                    chnlo_cfg.transsize = STSIZE;
                end

sce_dmachnl.sv:127-129 (clamp tested against the previous wpptr, so the load is unclamped)
    `theregrn( wpptr ) <= ( wpptr > thewpsegcfg.segsize ) ? 0 :
                          chnlstart ? thecfg.wpptr_start :
                          transdone ? (( wpptr == thewpsegcfg.segsize - 1 ) ? 0 : wpptr + 1 ) : wpptr;

sce_memc.sv:212
        assign ramm_addr[gvk] = arbm_dat[gvk].segaddr + arbm_dat[gvk].segptr;

sce.sv:456-457 (write port is outside the AC range)
            .chnl_wpreq     (ramreq[9]),
            .chnl_wpres     (ramres[9]),

scedma_pkg.sv:303-307 (segments whose AHB write-deny this bypasses)
        '{ segid:SEGID_POB  , accessrule: 8'b00_00_00_10 },
        '{ segid:SEGID_PSOB , accessrule: 8'b10_00_10_00 },
        '{ segid:SEGID_AKEY , accessrule: 8'b01_01_01_01 },
        '{ segid:SEGID_AIB  , accessrule: 8'b01_01_01_01 },
        '{ segid:SEGID_AOB  , accessrule: 8'b10_10_10_10 },
```

**Attack scenario.** Attacker = software owning the SCE in mode_sec (T1), goal: read a value derived from the unreadable SEG_SKEY despite the combohasha.sv:230 guard.
1. Write COMBOHASH_SFR_SEGPTR index 7 (0x4002_B03C) = 64. SEG_HOUT.segaddr is 384, so the first output beat is written at SCERAM word 384+64 = 448 = SEG_SOB[0].
2. Program SFR_OPT2 (0x4002_B014) with ifskey=1, ifsob=0 (forced anyway), scrtchk=0, and run HF_HMAC256_PASS1 then HF_HMAC256_PASS2 (0x50 then 0x60). MFSM_LD_KEY reads SEG_SKEY (combohasha.sv:645), MFSM_HF computes, opt_check=0 so the FSM goes to MFSM_WB_HOUT.
3. chnlo issues its first write at word 448 instead of 384, so digest word 0 - a value derived from the write-only SEG_SKEY - lands in SEG_SOB[0].
4. Read 0x4002_0700 over AHB; SEG_SOB accessrule 8'b10_00_10_00 permits AHB reads. The ifsob/ifskey guard that was supposed to make this impossible has been bypassed with two register writes.
Second, independent use of the same primitive: pick a target such as SEG_AOB (SEGADDR_AOB = 1856; set pointer to 1472 so 384+1472 = 1856), grind a message offline until SHA-256 digest word 0 equals the value you want, and run one hardware hash. You have now planted a chosen 32-bit word in the AES output buffer, which ACRULEs make write-denied on every channel (8'b10_10_10_10) precisely so that software cannot forge an engine result. The same works for SEG_POB and SEG_PSOB (the PKE secure output buffers).

**Verification.** No independent verdict recorded for this entry.

---

<a id="bao-034"></a>

### BAO-034 — Two ReRAM-controlled bits (devmode_sce[2:1]) unlock the scemode write-lock and suppress the mode-quit reset, giving a direct plaintext read of SKEY/AKEY/PKB and the whole PKE RAM with no wipe

**Severity: Medium** | CWE-1234 Hardware Internal or Debug Modes Allow Override of Locks | Threat actor: T1 (boot0/boot1-classified code able to write the ReRAM CFG region) or T2 (fault injection on the ReRAM boot read) | Confidence: High

**Location:** `rtl/modules/crypto_top/rtl/sce.sv:131`

**Description.** The SCE's confidentiality rests on exactly two interlocks: (a) `scemode` is write-once out of zero (`sce_glbsfra.sv:78` passes `.sfrlock(~devmode & (|cr_scemode))` to the mode register), so a secure session cannot be downgraded back to the wide-open `mode_non` state; and (b) if the mode ever does change from a non-zero value, `modequit` forces an SCE reset which triggers `sceramclr` and wipes the crypto RAM. Both are disabled bit-for-bit by `devmode_sce`, which is derived at sce.sv:131 as `devmode ? '1 : nvrcfg[28]` - i.e. either the SoC-wide dev-mode flag OR, completely independently of it, a single 8-bit byte read from ReRAM configuration word 10 (`nvrcfg` is bound to `nvrcfgdata.cfgsce` at soc_coresub.sv:545). `devmode_sce[2]` is routed to `sce_glbsfr`'s `devmode` port (sce.sv:229) and removes the mode write-lock; `devmode_sce[1]` is routed to `sce_sec`'s `devmode[1]` (sce.sv:284) and forces `modequit` to 0, removing the reset and the RAM wipe. There is no redundancy, no majority vote, no lock, no one-way counter and no anti-rollback on these bits: each is a single bit whose set value means 'disable this security check'. Compare the SoC-level `devmode`, which at least requires a 32-bit magic word (`cpudevmode = 32'h298ca435`, nvrcfgs.sv:82). With bits [2:1] set, the sequence mode_sec -> mode_non becomes a legal software transition that neither resets the SCE nor clears a single RAM word, and in `mode_non` all three remaining protections are simultaneously off: `ahben` is unconditionally 1 (sce_sec.sv:72), the per-segment DMA access rules are bypassed because `acenable = mode_sec` (sce.sv:370 with scedma_ac.sv:47), and the PKE RAM AHB window is unlocked because `pkeahbslock = mode_sec` (sce.sv:138).

**Evidence.**
```systemverilog
rtl/modules/crypto_top/rtl/sce.sv:131-139
    assign devmode_sce = devmode ? '1 : nvrcfg[28];// != 8'h00) || devmode;
        // [0] for ahben bypass
        // [1] for mode quit reset bypass
        // [2] for mode value lock bypass
        // [3] pke ahbs lock bypass
        // [4] alu sec bypass

    assign pkeahbslock = devmode_sce[3] ? '0 : mode_sec;
    assign alusec = devmode_sce[4] ? '0 : mode_sec;

rtl/modules/crypto_top/rtl/sce.sv:229
                .devmode   (devmode_sce[2]),

rtl/modules/crypto_top/rtl/sce.sv:284
        .devmode     (devmode_sce[1:0]),

rtl/modules/crypto_top/rtl/sce_glbsfra.sv:78
    apb_cr #(.A('h00), .DW(2))      sfr_scemode     (.cr(cr_scemode), .prdata32(), .sfrlock(~devmode & (|cr_scemode)), .*);

rtl/modules/crypto_top/rtl/sce_sec.sv:81
    assign modequit = devmode[1] ? '0 : ~( scemodereg == 0 ) && ~( scemode == scemodereg ) ;

rtl/modules/crypto_top/rtl/sce_sec.sv:72
    assign ahben =  mode_non ? 1'b1 :

rtl/modules/crypto_top/rtl/sce.sv:370
    assign acenable = mode_sec;

rtl/modules/soc_coresub/rtl/soc_coresub.sv:545
        .nvrcfg     ( nvrcfgdata.cfgsce ),
```

**Preconditions.** Either the ability to write ReRAM configuration word 10 byte 28 (boot0/boot1-classified code execution, T1) or the ability to fault the ReRAM boot read of that word (T2 glitch / laser FI). The RTL default is safe: `defnvrdat256 = 256'hcf9defc0de` (nvrcfgs.sv:28) has byte 28 = 0, and `brc` latches the field into flops that reset to 0, so an un-programmed part has all five interlocks enabled.

**Attack scenario.** 1. The attacker arranges for `cfgsce` byte 28 to have bits [2:1] set. Two routes: (i) software that is classified as boot0/boot1 by the coreuser PC-range comparator writes the ReRAM CFG region - the byte is a plain configuration byte with no lock, no redundant copy and no signature check; or (ii) a T2 attacker glitches the ReRAM boot read (`brc`) that latches `nvrcfgdata`, flipping one or two bits in a 256-bit word that is captured into plain flops with no ECC check on this field. Because each interlock is a single bit with 1 = disabled, a single successful bit flip is sufficient for either half of the attack, and the two bits are adjacent.
2. On the next boot the SCE comes up with the mode register unlocked and the mode-quit wipe suppressed. Secure boot proceeds normally and loads real secrets: the HMAC key into KEY (0x4002_0100), the secret key into SKEY (0x4002_0200), the AES key and IV into AKEY (0x4002_1C00), the RSA/ECC private operand into PKB (0x4002_0800) and the PKE working RAM at 0x4002_4000.
3. The attacker's code takes SCE ownership (trivial in mode_non, or by winning the ownership latch - see findings 2 and 5) and writes 0x00 to the mode register at 0x4002_8000. Normally this write is rejected by sfrlock; with devmode_sce[2] set it is accepted. Normally the resulting mode change asserts `modequit`, resetting the SCE and running the 1984-word wipe; with devmode_sce[1] set `modequit` is hardwired to 0, so nothing is reset and nothing is cleared.
4. The SCE is now in mode_non with the keys still resident. `ahben` is 1 for every master, `acenable` is 0 so the `01_01_01_01` write-only rules on LKEY/KEY/SKEY/SCRT/PKB/AKEY (scedma_pkg.sv:292-299,303,306) are bypassed, and `pkeahbslock` is 0 so the PKE RAM window is open. The attacker reads the private keys out in the clear with ordinary 32-bit loads from 0x4002_0100, 0x4002_0200, 0x4002_0800, 0x4002_1C00 and 0x4002_4000.

**Mitigation.** RTL fix: (1) do not let a non-devmode ReRAM byte disable security interlocks at all - if a manufacturing bypass is genuinely required, gate it on the same lifecycle state that gates JTAG (CMS_TEST/CMS_VRGN) rather than on a field-writable configuration byte; (2) if the byte must stay, require a full multi-bit magic pattern per bypass (as `cpudevmode`/`coreselcm7_code` already do) rather than a single active-high bit, and replicate the comparison so a single fault cannot flip it; (3) make the crypto-RAM wipe unconditional on ANY `scemode` change, independent of `devmode`, so that even with the reset bypassed the secrets are destroyed - i.e. `sceramclr` should be driven by the mode-change detector directly, not only through `modequit`->`sceresetn`. Software workaround on fabricated silicon: the boot loader must read back `cfgsce` byte 28 immediately after the ReRAM boot read and refuse to load any key material (halt, or trigger `rrcar_suicide`) unless it reads exactly 0x00. This check must itself be redundant, because the same fault that sets the byte can skip the check.

**Verification.** Independently confirmed by a second reviewer. All quotes verified verbatim: sce.sv:131-139 including the bit legend comment; sce.sv:229 `.devmode (devmode_sce[2])` into sce_glbsfr; sce.sv:284 `.devmode (devmode_sce[1:0])` into sce_sec; sce_glbsfra.sv:78 `apb_cr #(.A('h00), .DW(2)) sfr_scemode (.cr(cr_scemode), .prdata32(), .sfrlock(~devmode & (|cr_scemode)), .*);`; sce_sec.sv:81 `assign modequit = devmode[1] ? '0 : ~( scemodereg == 0 ) && ~( scemode == scemodereg ) ;`; sce.sv:370, sce.sv:138, sce_sec.sv:72; soc_coresub.sv:545 `.nvrcfg ( nvrcfgdata.cfgsce )`. The mechanism is exactly as described: devmode_sce[2]=1 removes the write-once lock on scemode, devmode_sce[1]=1 forces modequit to 0 so sceresetnin (sce_sec.sv:83) never drops and sceramclr never re-pulses, and mode_non then simultaneously opens ahben, acenable and pkeahbslock. I verified the safe default: nvrcfg_pkg.sv:28 `localparam nvrdat_t defnvrdat256 = 256'hcf9defc0de;` and nvrcfgs.sv:155 `cfgsce : defnvrdat256` - byte 28 is 0. I also verified the contrast the finder draws: nvrcfg_pkg.sv:82-84 gate the SoC devmode and core-select on full 32-bit magic words (cpudevmode=32'h298ca435 etc., checked at soc_coresub.sv:271-273), whereas devmode_sce is a bare active-high byte with no magic, no redundancy, no lock and no anti-rollback. I found no compensating control - nothing in sce.sv, soc_coresub.sv or nvrcfgs.sv cross-checks this byte, and it is not gated on the CMS lifecycle state the way cmstest/cmsatpg are (soc_top.sv:397).

**Corrections applied by the verifier.** The impact chain is real but the severity was overstated at high. This is a hardening/defence-in-depth defect, not a directly reachable software bug: the interlocks are enabled by default and exploiting them needs either (a) the ability to write the ReRAM CFG region, which requires boot0/boot1-classified execution - an attacker who already holds that has largely won - or (b) fault injection on the ReRAM boot read (T2), which is a physical attack. The strongest form of the argument is the one the finder makes in passing and should be led with: a ReRAM read that faults to all-ones sets devmode_sce=8'hFF and disables all five interlocks at once, so a single coarse fault on one byte is sufficient. Note also that devmode_sce[0], documented as 'ahben bypass', is inert - it only reaches sce_sec.sv:77 `assign ahbs_lock = devmode[0] ? 1'b0 : ~ahben;` and ahbs_lock is unused at sce.sv:109/287. So the reachable bypasses are [1],[2],[3],[4], not [0].

---

<a id="bao-035"></a>

### BAO-035 — SCE trust state (the ReRAM key-slot unlock bits) is on the system reset rather than the SCE reset, so an HMAC authorisation is never revoked by a mode downgrade, an SCE reset or a crypto-RAM wipe; and the top bit is hardwired trusted

**Severity: Medium** | CWE-1272 Sensitive Information Uncleared Before Debug/Power State Transition | Threat actor: T1 (unprivileged software on either CPU able to reach 0x4002_0000) | Confidence: Medium

**Location:** `rtl/modules/crypto_top/rtl/sce.sv:298`

**Description.** `sce_ts` holds the 256-bit `truststate` vector that the ReRAM controller consumes as `trustkey[]` to decide whether a ReRAM key slot may be read (`rrc.sv:717` term `(!trustkey[akeyid] & (haddr_reg[15:6] != 10'h0))`). A bit is set when the hash engine reports `hmac_pass` for the corresponding key index while in secure mode - i.e. the bits are the record of a successful authentication (a PIN/attestation/HMAC challenge). Every other block inside the SCE is instantiated with `.resetn(sceresetn)` - `sce_sec` at sce.sv:275, `sce_glbsfr` at :224, `scedma` at :334, `combohash` at :447 - but `sce_ts` is instantiated with the bare `.resetn,` at sce.sv:298, which is the SCE module's system reset port (bound to `resetn` at soc_coresub.sv:532). `sceresetn` is generated from `sceresetnin = ~( modequit | ar_reset )` (sce_sec.sv:83), so the SCE reset that fires on a mode downgrade and on the software `ar_reset` action register (0x4002_801C <= 0x5a) does NOT clear `tsreg`. Nor does `sceramclr`, which only touches RAM. Furthermore `tsreg[i]` is only ever written when `mode_sec` is asserted (sce_sec.sv:117), so leaving secure mode cannot clear it either - the bits simply freeze in whatever state the last secure session left them, and they are readable at 0x4002_80E0 via `sfr_ts` (sce_glbsfra.sv:103). Separately, `assign ts = { 1'b1, tsreg };` (sce_sec.sv:123) hardwires the most significant bit to 1; with `.TSC(256)` (soc_coresub.sv:517) that is `truststate[255]`, so any ReRAM key slot whose ACRAM descriptor carries `akeyid == 8'hFF` is unconditionally 'trusted' and bypasses the trust gate entirely regardless of any authentication.

**Evidence.**
```systemverilog
rtl/modules/crypto_top/rtl/sce.sv:294-304
    sce_ts #(
        .TSC(TSC)
    )ts(
        .clk,
        .resetn,
        .scemode(glb_scemode),
        .hmac_pass,
        .hmac_fail,
        .hmac_kid,
        .ts (truststate)
    );

rtl/modules/crypto_top/rtl/sce.sv:275 (every other SCE sub-block, for contrast)
        .resetn(sceresetn),

rtl/modules/crypto_top/rtl/sce_sec.sv:83
	assign sceresetnin = ~( modequit | ar_reset );

rtl/modules/crypto_top/rtl/sce_sec.sv:115-123
generate
    for (genvar i = 0; i < TSC-1; i++) begin
    `theregrn( tsreg[i] ) <= ((hmac_kid==i)&mode_sec & hmac_pass) ? 'b1 : ((hmac_kid==i)&mode_sec & hmac_fail) ? 'b0 : tsreg[i];
    end
endgenerate

    // the MSB is always 1.

    assign ts = { 1'b1, tsreg };

rtl/modules/soc_coresub/rtl/soc_coresub.sv:517
        .TSC(256)
```

**Preconditions.** A previous secure session must have unlocked at least one trust bit (the normal case in any design that uses the HMAC key-unlock feature). The attacker needs software execution able to reach 0x4002_xxxx and to re-take SCE ownership, which is the reset state. No physical access required. The residual barrier is the RRC's ACRAM owner-nibble check, so the impact is bounded by how key slots are provisioned - it is a bypass of the authentication step, not automatically a bypass of the ownership step.

**Attack scenario.** 1. During a legitimate secure session, trusted firmware performs the HMAC challenge that unlocks ReRAM key slot K - for example a PIN-derived or attestation-derived check whose whole purpose is to be a one-shot, per-session authorisation. `combohash` reports `hmac_pass` with `hmac_kid == K` while `mode_sec` is asserted, and `tsreg[K]` is set to 1.
2. The session ends. The firmware does what looks like a full teardown: it writes 0x5a to 0x4002_801C (`ar_reset`), which drops `sceresetnin`, holds the whole SCE in reset for 16 cycles, returns `scemode` to 0, and runs the crypto-RAM wipe. From every software-visible indication the SCE has been returned to a pristine state.
3. `tsreg` is untouched, because `sce_ts` is on the system reset. `truststate[K]` is still 1. It is also directly observable by anyone who can read 0x4002_80E0..0x4002_80FC.
4. Attacker code re-opens a secure session (trivial: after the reset the mode register is unlocked and `mode_non` grants ownership to whoever asks - see findings 2 and 5), programs the SCE DMA with a read of ReRAM key slot K, and the RRC's trust gate passes because `trustkey[K]` is still asserted. The authentication has been replayed without ever performing it: the attacker never had to know the PIN or produce the HMAC. The remaining barriers in `rrc.sv:712-717` are the ACRAM owner nibble and the software-chosen `keytype`, both of which are weaker than the HMAC the trust bit was supposed to represent.
5. Independently, any key slot provisioned with `akeyid = 0xFF` is permanently trusted because of the hardwired MSB at sce_sec.sv:123 - no authentication is ever required for it.

**Mitigation.** RTL fix: change sce.sv:298 to `.resetn(sceresetn),` so the trust vector is cleared by `ar_reset` and by `modequit`, and additionally clear `tsreg` on any `scemode` transition (add `~mode_sec` as a synchronous clear term at sce_sec.sv:117) so that leaving secure mode revokes every authorisation. Remove the hardwired MSB at sce_sec.sv:123 (`assign ts = { 1'b1, tsreg };`) or, if a permanently-trusted slot is genuinely required, make it an explicit parameter that provisioning can leave unused, and document that `akeyid = 0xFF` must never be assigned. Software workaround on fabricated silicon: never rely on the trust bits as a session-scoped authorisation. Firmware must treat `truststate` as sticky-until-system-reset: after every use of an HMAC-unlocked key slot it must explicitly drive `hmac_fail` for that `hmac_kid` while still in secure mode (the only path that clears a bit), verify by reading 0x4002_80E0 that the bit went to 0, and must never provision any key slot with `akeyid = 0xFF`.

**Verification.** Independently confirmed by a second reviewer. Verified line by line. sce.sv:294-304 instantiates sce_ts with a bare `.resetn,` at line 298, which binds to the sce module's system reset port (sce.sv:32 `input logic resetn,sysresetn`, driven from soc_coresub.sv:531 `.resetn, .sysresetn,`). Every sibling block uses the SCE reset: sce_sec .resetn(sceresetn) at sce.sv:275, sce_glbsfr at :224, scedma at :334, scedma_ac at :374, combohash at :447, aes at :488(pke)/:512(aes), so sce_ts is the sole outlier. sceresetn is driven from sce_sec.sv:83 `assign sceresetnin = ~( modequit | ar_reset );` through sceresetgen (sce.sv:310-318), so ar_reset (0x1c<=0x5a, sce_glbsfra.sv:86) and modequit do not clear tsreg. sceramclr only reaches cryptoram/aes/pke/hash/alu ramclr ports, never tsreg. sce_sec.sv:115-119 is verbatim as quoted and the write condition is qualified by mode_sec, so leaving secure mode cannot clear a bit either - the bits freeze. sce_sec.sv:123 `assign ts = { 1'b1, tsreg };` is verbatim and with .TSC(256) (soc_coresub.sv:517) that is truststate[255]. I traced the consumer: soc_coresub.sv:836 `.trustkey (truststate)` into rrc, and rrc.sv:717 `(!trustkey[akeyid] & (haddr_reg[15:6] != 10'h0))` gates key-slot reads, plus rrc.sv:761-763 where trustkey[3]/[5]/[7] gate the boot1/fw0/fw1 code regions when nvrcfgdata.cfgrrsub.tkey_en is programmed. The bits are also software-readable at sfr_ts (sce_glbsfra.sv:103). Compensating controls exist but do not close it: rrc.sv:710-717 still requires the ACRAM owner-nibble match against coreuser_in (=sceuser for scesel, rrc.sv:670-671) and keytype_in==keytype_k, and rrc.sv:717 exempts key slots 0/1 by design. So the trust bit is one gate of several, and the finding is a bypass of the authentication step only.

**Corrections applied by the verifier.** Accurate as written; medium is the right level. One nuance worth passing to the vendor: because sceuser is what the RRC uses as coreuser_in for SCE-originated key reads (rrc.sv:670-672), and sceuser resets to 8'h00 and is re-latched on the next 0->non-zero scemode transition, the residual ACRAM owner-nibble check is only as strong as the ownership latch - which findings 2 and 5 show is itself unreliable. The hardwired MSB is clearly deliberate (the comment at sce_sec.sv:121 says so), so it should be reported as a provisioning hazard (akeyid=0xFF must never be assigned) rather than as an accidental defect.

---

<a id="bao-036"></a>

### BAO-036 — A single ReRAM configuration byte (cfgsce byte 29 == 0x5a) replaces the entire hard-coded SCE segment access-control rule table with ReRAM-supplied rules, making the write-only key segments AHB-readable in secure mode with no wipe and no mode change

**Severity: Medium**

**Location:** `rtl/modules/crypto_top/rtl/sce.sv:376`

*Surfaced by the independent verifier, not the original domain reviewer.*

**Description.** sce.sv:372-382 wires the raw ReRAM SCE configuration word straight into scedma_ac as the access-rule source: `.nvracrules ( nvrcfg )`, where nvrcfg is bound at soc_coresub.sv:545 to nvrcfgdata.cfgsce. Inside scedma_ac, one byte of that word is a plain magic-value enable that swaps out the entire compiled-in rule table for the ReRAM contents (scedma_ac.sv:40 and 65-67). The replacement is total: chnlacrules[j] for every one of the 18 segments comes from nvracrules[j], so bytes 0..17 of cfgsce directly define who may read and write LKEY, KEY, SKEY, SCRT, PKB, AKEY and the PKE/AES output buffers on all eight DMA channels. Unlike the SoC devmode (nvrcfg_pkg.sv:82, a 32-bit magic word) this is guarded only by a single-byte 0x5a comparison, with no redundancy, no lock bit, no lifecycle gate and no consistency check against the compiled-in table. This is a distinct and strictly more powerful bypass than the devmode_sce byte at sce.sv:131: it does not require downgrading scemode, does not require suppressing modequit, and therefore does not require avoiding the crypto-RAM wipe - the keys can be read straight out of a live secure session.

**Evidence.**
```systemverilog
rtl/modules/crypto_top/rtl/sce.sv:372-382
    scedma_ac dmaac(
        .clk,
        .resetn             (sceresetn),
        .acenable           ( acenable      ),
        .nvracrules         ( nvrcfg ),
        .chnlinreq          ( chnlreq[0:CHNLACCNT-1]  ),

rtl/modules/crypto_top/rtl/scedma_ac.sv:39-40
    logic nvrrule_enable;
    assign nvrrule_enable = (nvracrules[29] == 8'h5a);

rtl/modules/crypto_top/rtl/scedma_ac.sv:65-67
    for (genvar j = 0; j < scedma_pkg::SEGCNT; j++) begin: gacrule
        assign chnlacrules[j] = nvrrule_enable ? nvracrules[j] : ACRULEs[j].accessrule;
    end

rtl/modules/soc_coresub/rtl/soc_coresub.sv:545
        .nvrcfg     ( nvrcfgdata.cfgsce ),

rtl/modules/sysctrl/rtl/nvrcfgs.sv:28 (default is safe: byte 29 is 0)
    localparam nvrdat_t defnvrdat256 = 256'hcf9defc0de;

rtl/modules/sysctrl/rtl/nvrcfgs.sv:82 (contrast: the SoC devmode requires a 32-bit magic word)
    localparam bit [31:0] cpudevmode = 32'h298ca435;
```

**Attack scenario.** 1. The attacker arranges for cfgsce byte 29 to read 0x5a and bytes 0..17 to read 8'hff. Two routes, the same two as for the devmode_sce byte: code classified boot0/boot1 by the coreuser PC comparator writes the ReRAM CFG region (there is no lock, no second copy and no signature over this field), or a T2 attacker faults the ReRAM boot read that latches nvrcfgdata - and because the enable is a single-byte compare and the rules are active-high permits, a fault that drives the word toward all-ones both enables the override and grants every permission.
2. On the next boot everything proceeds normally. Secure boot brings the SCE to mode_sec, has the SCE DMA load ReRAM key slots into SKEY (0x4002_0200), AKEY (0x4002_1c00) and PKB (0x4002_0800), and runs real operations. acenable is 1, so scedma_ac is fully active - and it is enforcing the attacker's rules.
3. The attacker, from ordinary code that satisfies the ahben ownership comparison, issues plain 32-bit loads from 0x4002_0200, 0x4002_0800 and 0x4002_1c00. chnlac[0] (the AHB read channel) is 1 for those segments because chnlacrules now comes from ReRAM, so the reads are approved and return the key material in the clear.
4. No mode change is needed, so modequit never asserts, sceramclr never pulses, and nothing is wiped. scedma_ac logs nothing because acerr (scedma_ac.sv:61-62,71) only records denials, and these accesses are permitted.

**Verification.** No independent verdict recorded for this entry.

---

<a id="bao-037"></a>

### BAO-037 — scedma_ac violation reporting is structurally tied to zero, and denied accesses are reported to the requester as successful zero-data transfers

**Severity: Medium** | CWE-778 Insufficient Logging of Security-Relevant Events | Threat actor: T1 / T2 (any attacker probing the crypto-RAM ACL; also removes the detection signal that would reveal T2 fault-injection attempts) | Confidence: High

**Location:** `rtl/modules/crypto_top/rtl/scedma_ac.sv:61`

**Description.** `scedma_ac` is the only access-control block for the crypto DMA, and `acerr` is its only violation output (it is exported to firmware as `sfr_fracerr` at SCE APB offset 0x60, `sce_glbsfra.sv:89`, i.e. 0x4002_8060). The error flops are computed from `chnloutreq[i].segrd` - the ALREADY-GATED output - AND-ed with `~chnlac[i]`. Since `chnloutreq[i].segrd = chnlinreq[i].segrd & chnlac[i]` (line 52), the expression is `x & chnlac & ~chnlac`, identically zero. The same holds for `errsw`. The correct source is the ungated `chnlinreq[i].segrd`. Consequently `acerr` never asserts, `sfr_fracerr` always reads 0, and no interrupt or alarm can ever be raised by a crypto-RAM access-control violation. This is compounded by lines 57-59: on a denial the block asserts `segready = '1` and `segrdatvld = '1` and returns `segrdat = '0`, so the requesting channel FSM completes the transfer at full speed and the requester cannot distinguish 'denied' from 'the segment legitimately contains zero'. The net effect is that an attacker can sweep the entire segment/channel ACL matrix, and mount the probing needed for findings 1 and 2, with zero risk of detection by firmware or by an on-chip response.

**Evidence.**
```systemverilog
scedma_ac.sv:52-62
        assign chnloutreq[i].segrd     = chnlinreq[i].segrd  & chnlac[i]   ;
        assign chnloutreq[i].segwr     = chnlinreq[i].segwr  & chnlac[i]   ;
        assign chnloutreq[i].segwdat   = chnlinreq[i].segwdat   ;
        assign chnloutreq[i].porttype  = chnlinreq[i].porttype  ;

        assign chnlinres[i].segready   = chnlac[i] ? chnloutres[i].segready   : '1 ;
        assign chnlinres[i].segrdat    = chnlac[i] ? chnloutres[i].segrdat    : '0 ;
        assign chnlinres[i].segrdatvld = chnlac[i] ? chnloutres[i].segrdatvld : '1 ;

        `theregrn( errsr[i] ) <= chnloutreq[i].segrd & ~chnlac[i];
        `theregrn( errsw[i] ) <= chnloutreq[i].segwr & ~chnlac[i];

scedma_ac.sv:71
    assign acerr = errsr | errsw;

sce.sv:381 / sce.sv:243 (acerr is the only consumer path)
        .acerr              ( acerr )
...
                                          .fr_acerr   (acerr),

sce_glbsfra.sv:89
    apb_fr #(.A('h60), .DW(CHNLACCNT)) sfr_fracerr  (.fr(fr_acerr),      .prdata32(),.*);
```

**Preconditions.** None. The defect is unconditional: it is a boolean identity in the RTL, so `acerr` is a constant 0 in all modes and will be optimised away by synthesis.

**Attack scenario.** 1. An attacker with software access to the SCE writes a DMA descriptor that targets a denied segment/channel pair - e.g. an AXI-general read (channel index 2) of SKEY (segid 2, rule bit 2 = 0).
2. `scedma_ac` correctly drops `segrd`, but because `chnlinres.segready` is forced to 1 the channel FSM runs to completion at full rate and reports `done`; the transfer looks identical to a successful one and delivers a buffer of zeros.
3. `errsr[2]` evaluates `chnloutreq[2].segrd & ~chnlac[2]` = `(segrd & 0) & 1` = 0. `acerr` stays 0, `sfr_fracerr` at 0x4002_8060 reads 0, and no interrupt fires.
4. The attacker therefore enumerates the full 18-segment x 8-channel access matrix, and then brute-forces the pointer/segid combinations required by findings 1 and 2, with no on-chip evidence of a single violation. A monitoring/attestation firmware that polls sfr_fracerr for tamper evidence will report a clean device throughout a full key extraction.

**Mitigation.** RTL fix (one-line): `` `theregrn( errsr[i] ) <= chnlinreq[i].segrd & ~chnlac[i]; `` and `` `theregrn( errsw[i] ) <= chnlinreq[i].segwr & ~chnlac[i]; `` - i.e. sample the ungated request. Separately, a denial should not be signalled as a successful zero read: return an error status to the channel (and, for the AHB slave path, an HRESP ERROR) rather than `segready='1', segrdat='0'`, and route `acerr` to a hard security event (SCE reset + `sceramclr`) not merely to a readable flag register. Silicon workaround: none - firmware cannot recover a detection signal that does not exist. Firmware can only avoid ever relying on sfr_fracerr (0x4002_8060) as evidence of absence of attack, and must not treat an all-zero DMA result as proof of an empty segment.

**Verification.** Independently confirmed by a second reviewer. scedma_ac.sv:52-53 assign chnloutreq[i].segrd = chnlinreq[i].segrd & chnlac[i] and .segwr likewise; scedma_ac.sv:61-62 then compute `errsr[i] <= chnloutreq[i].segrd & ~chnlac[i]` and `errsw[i] <= chnloutreq[i].segwr & ~chnlac[i]`. Substituting gives (x & chnlac) & ~chnlac, a boolean identity equal to 0 for both flops, so acerr (line 71) is a constant 0 in every mode. This is airtight - it needs no assumptions about timing or attacker capability. I traced the consumer chain: sce.sv:381 .acerr(acerr) -> sce.sv:243 .fr_acerr(acerr) -> sce_glbsfra.sv:89 `apb_fr #(.A('h60), .DW(CHNLACCNT)) sfr_fracerr (.fr(fr_acerr), ...)`, i.e. 0x4002_8060 (SCE base 0x4002_0000 from daric_cfg_pkg.sv:53, glbsfr on apbs[0] at ctrl offset 0x8000). There is no other violation output anywhere in the block. Lines 57-59 are also verbatim: on denial segready and segrdatvld are forced to '1 and segrdat to '0, so the requesting FSM completes normally; scedma_amba.sv:91 `assign ahbs.hresp = '0;` means the AHB path cannot signal an error either. No compensating control found.

**Corrections applied by the verifier.** Severity lowered from high to medium. This is a detection/telemetry defect: it does not by itself let an attacker read or write anything. Its real weight is that it removes the only evidence channel for findings 1, 2 and 5, and makes any firmware attestation that polls 0x4002_8060 useless. The finder's claim that the flops 'will be optimised away by synthesis' is correct and worth keeping - it means the silicon almost certainly contains no error-detection logic at all.

---

<a id="bao-038"></a>

### BAO-038 — The SCE's ReRAM key-slot credentials (AXI ID -> keytype, AxPROT[0] -> 'secure privileged') are plain unlocked software SFRs of the crypto DMA

**Severity: Medium** | CWE-1259 Improper Restriction of Security Token Assignment | Threat actor: T1 (software that owns the SCE in mode_sec) | Confidence: Medium

**Location:** `rtl/modules/crypto_top/rtl/scedma.sv:106`

**Description.** The RRC's ReRAM key-slot access check for SCE-originated transactions rests on two credentials that it takes off the AXI bus: the transaction ID (`keytype_in = {3'h0, axid_reg[6:2]}`, rrc.sv:674) and the privilege bit of AxPROT (`sce_sec_op = axprot_reg[0] & mode_sec`, rrc.sv:682). Both are asserted by the requester, and in the SCE DMA both are directly driven by unlocked APB control registers. `axim.arid`/`axim.awid` are literally `cr_segid`, the value of `sfr_sch_segid`/`sfr_xch_segid`; and `axim.arprot`/`axim.awprot` are `cr_axprot = mode_sec ? cr_opt[9:8]|3'h0`, i.e. bits 9:8 of `sfr_sch_opt`/`sfr_xch_opt`. The `keytype_k` field in the ACRAM descriptor exists to bind a ReRAM key slot to a purpose (so that, for example, an AES key slot cannot be pulled into the hash or PKE path); because the presented keytype is a software register, that binding is forgeable by writing one word. Likewise the `sce_sec_op` gate, which the RRC treats as 'this is a privileged secure SCE access', is self-asserted by the same software. Note also that the segid used for the ReRAM keytype credential (`cr_segid`) is the SAME register used by `scedma_ac` to make the SCERAM-side access decision (`scedma_amba.sv:426` -> `axim_segcfg.segid` -> `scedma_ac.sv:45`), so the two access-control domains are coupled through a single attacker-chosen 8-bit value.

**Evidence.**
```systemverilog
scedma.sv:91 and 105-110
    assign sfrlock = 0;
...
    apb_cr #(.A('h30 ), .DW(1)    ) sfr_sch_func     (.cr( schcr.func     ), .prdata32(),.*);
    apb_cr #(.A('h34 ), .DW(10)   ) sfr_sch_opt      (.cr( schcr.opt      ), .prdata32(),.*);
    apb_cr #(.A('h38 ), .DW(32)   ) sfr_sch_axstart  (.cr( schcr.axstart  ), .prdata32(),.*);
    apb_cr #(.A('h3c ), .DW(8)    ) sfr_sch_segid    (.cr( schcr.segid    ), .prdata32(),.*);

scedma_amba.sv:305 (AxPROT is cr_opt[9:8] in secure mode)
    assign cr_axprot = mode_sec ? cr_opt[9:8]|3'h0 : mode_xls ? 3'h2|cr_opt[8] : 3'h2;

scedma_amba.sv:384-395 and 400-412 (ID and PROT go straight onto the bus)
    assign axim.araddr  = cr_axaddrstart + aximprt *4;
    assign axim.arid    = cr_segid | '0;
...
    assign axim.arprot  = cr_axprot|3'h0;
...
    assign axim.aruser  = PM_AXID | '0;
...
    assign axim.awid     = cr_segid | '0;
...
    assign axim.awprot   = cr_axprot|3'h0;

rtl/modules/rrc/rtl/rrc.sv:674 and 681-682 (the RRC consumes exactly those bits)
    assign keytype_in = {3'h0,axid_reg[6:2]};       //sce used only, axim.arid/awid [4:0]
...
    assign sce_exc_op = axprot_reg[0] & (!mode_sec);        //exclusive mode for sce, unsecure(using intf from sce), priviledge
    assign sce_sec_op = axprot_reg[0] & mode_sec;           //security mode for sce, secure(using intf from sce), priviledge

rtl/modules/rrc/rtl/rrc.sv:715-717
                                ahb_read_flag & scesel & (sce_rd_dis_k | (!sce_sec_op) | (keytype_in != keytype_k)) |
                                ahb_write_flag & scesel & (sce_wr_dis_k | (!sce_sec_op) | (keytype_in != keytype_k)) |
                                (!trustkey[akeyid] & (haddr_reg[15:6] != 10'h0))) & data_op & keysel & (userid_k[7:4] != 4'h0);
```

**Preconditions.** SCE in mode_sec (so `sce_sec_op` can be true at all, rrc.sv:682). Attacker can write the scedma SFR block at 0x4002_9030..0x4002_903C; `scedma.sv:91 assign sfrlock = 0;` means there is no lock. The target ReRAM key slot must still require `sceuser` overlap and `trustkey[akeyid]`, which are not defeated by this finding.

**Attack scenario.** 1. Software owning the SCE in mode_sec picks a ReRAM key slot in the 0x603F_xxxx key region whose ACRAM descriptor has a `keytype_k` intended for a different consumer (e.g. an HMAC/attestation key that should only ever be fetched with the hash engine's keytype).
2. It writes `sfr_sch_segid` (0x4002_903C) = the desired keytype shifted into bits [6:2] - i.e. `cr_segid = keytype_k << 2` - so that `keytype_in = {3'h0, arid[6:2]}` matches `keytype_k` exactly and the term `(keytype_in != keytype_k)` in rrc.sv:715 evaluates false.
3. It writes `sfr_sch_opt` (0x4002_9034) with bit 8 set, so `cr_axprot[0] = 1` -> `axprot_reg[0] = 1` -> `sce_sec_op = 1`, satisfying the `(!sce_sec_op)` term.
4. It writes `sfr_sch_axstart` (0x4002_9038) = the ReRAM key-slot address and starts the channel (0xaa to 0x4002_9000).
5. The RRC now sees a transaction with `scesel`=1, the matching keytype and the privilege bit asserted, so two of the four SCE-path gates in `key_access_error_pre` are satisfied by values the attacker chose. Only `sce_rd_dis_k`, the `coreuser_in & userid_k` overlap (which uses `sceuser`) and `trustkey[akeyid]` remain. The key slot's purpose binding - the whole point of the keytype field - is defeated by two register writes.
6. The fetched key word lands in SCERAM, from where findings 1 and 2 can read it out.

**Mitigation.** RTL fix: the keytype credential must not be software-writable. Drive `axim.arid`/`awid` from a hardware-derived tag - e.g. the engine that requested the key transfer, or a value latched from the SCE mode/owner state - not from `cr_segid`; at minimum, give `sfr_sch_segid`/`sfr_xch_segid` and `sfr_*_opt` an operational lock like the one already implemented in aes.sv:135 / combohasha.sv:159 (`` `theregrn( sfrlock ) <= optlock ? 1'b1 : mfsm_done ? '0 : sfrlock; ``) instead of `scedma.sv:91 assign sfrlock = 0;`. `AxPROT[0]` must be generated by hardware from the actual SCE security state, not taken from `cr_opt[9:8]`. Silicon workaround: since the keytype gate is forgeable, firmware must not rely on `keytype_k` for isolation between key consumers; provision every ReRAM key slot so that its `userid_k` and `akeyid`/trustkey linkage alone are sufficient to enforce the intended policy, and set `sce_rd_dis_k` on every slot that the SCE DMA must never fetch.

**Verification.** Verified as written; exploitability not fully established. All cited RTL is verbatim correct. scedma_amba.sv:385/401 drive axim.arid/awid = cr_segid, and scedma.sv:108 shows cr_segid is `apb_cr #(.A('h3c), .DW(8)) sfr_sch_segid`, an unlocked (scedma.sv:91) 8-bit APB register. scedma_amba.sv:305 `cr_axprot = mode_sec ? cr_opt[9:8]|3'h0 : ...` makes axprot[0] = cr_opt[8] = bit 8 of sfr_sch_opt, and axprot[1] = cr_opt[9] (so software also picks the AxPROT 'secure' bit). rrc.sv:674 `keytype_in = {3'h0,axid_reg[6:2]}` and rrc.sv:682 `sce_sec_op = axprot_reg[0] & mode_sec` consume exactly those bits, and rrc.sv:715-716 use both as terms of key_access_error_pre. So the two credentials are factually software-asserted. I also confirmed an amplification the finder missed: because keytype_in = cr_segid[6:2], forging keytype N requires cr_segid = N<<2, which for N>=5 exceeds SEGCNT=18 and makes scedma_amba.sv:426 fall back to SEGCFG_DEF (segaddr 0, segsize 256, segid 0 = LKEY, whose accessrule[5] = 1, i.e. axi-secure WRITE permitted) - so a forged keytype in 0..31 still has a working SCERAM landing zone covering LKEY/KEY/SKEY/SCRT. What keeps this out of 'confirmed' is that I could not demonstrate access to a key the attacker did not already have: the surviving gates are hardware-derived and not spoofable - coreuser_in for scesel is sceuser (rrc.sv:670-672), which sce_sec.sv:61-64 latches from the bus master's hauser at the mode_non->mode_sec transition, plus sce_rd_dis_k and trustkey[akeyid]. Exploitability therefore depends entirely on a provisioning in which two key slots differ ONLY by keytype_k, which I cannot verify from RTL. sce_sec_op being self-asserted is a check that can never fail rather than an escalation.

**Corrections applied by the verifier.** The title's framing is right but the impact stated ('high') is not substantiated. Also note the RRC upper-bounds the forgeable keytype: keytype_in[7:5] is hardwired to 3'h0 (rrc.sv:674), so only keytype_k values 0..31 are reachable at all. The mitigation advice is sound - aes.sv:135 `theregrn( sfrlock ) <= optlock ? 1'b1 : mfsm_done ? '0 : sfrlock;` does exist and does show the designers implemented an operational lock elsewhere but not in scedma.

---

<a id="bao-039"></a>

### BAO-039 — Unbounded array index on the ich channel's segment lookup and in scedma_ac's rule lookup (8-bit software index into 18-entry tables), while the AXI path bounds-checks the identical value

**Severity: Medium** | CWE-129 Improper Validation of Array Index | Threat actor: T1 (software that can write the scedma SFRs at 0x4002_9054) | Confidence: Medium

**Location:** `rtl/modules/crypto_top/rtl/scedma.sv:277`

**Description.** `ichcr_segid` is a 16-bit unlocked SFR split into two 8-bit segment IDs, both of which index the 18-entry `SEGCFGS` localparam with no range check. The very same lookup on the AXI path is explicitly guarded - `scedma_amba.sv:426 assign axim_segcfg = cr_segid < SEGCNT ? SEGCFGS[cr_segid] : SEGCFG_DEF;` - which shows the designers were aware of the hazard and simply did not apply it here. An out-of-range packed-array select is 'x in simulation and a don't-care in synthesis, so the resulting `segcfg` (its `segaddr`, `segsize` AND its `segid`) is whatever the optimiser produced; the tool is free to alias index 18..255 onto any table entry or onto a mix of entries. That `segcfg.segid` is then fed to `scedma_ac.sv:46 chnlacrule = chnlacrules[chnlinsegid[i]][i]`, which is ITSELF an 8-bit index into an 18-entry array with no bound - so an out-of-range segid produces an undefined `chnlac`, which may resolve to 1 (allow). The failure mode is fail-open: the access-control decision for the ich channel is not guaranteed to be a defined function of the software input. Related, and in the same block: the SEGCFG_DEF fallback that the AXI path does use (`scedma_amba.sv:266-276`) yields `segid: '0` (LKEY) with `segaddr: '0` and `segsize: 'd256` - a 1 KB window at the base of SCERAM covering LKEY, KEY, SKEY and SCRT, all adjudicated under LKEY's single rule. Today LKEY/KEY/SKEY/SCRT happen to share the rule 8'b01_01_01_01, so this grants nothing extra, but the ACL decision is being made for a region four times larger than the segment it names, and any future or NVR-supplied rule table (see next finding) that grants read to LKEY would immediately expose SKEY and SCRT.

**Evidence.**
```systemverilog
scedma.sv:113 and 124 and 277-278
    apb_cr #(.A('h54 ), .DW(16)   ) sfr_ich_segid    (.cr( ichcr_segid    ), .prdata32(),.*);
...
    assign { ichcr_rpsegid, ichcr_wpsegid } = ichcr_segid;
...
    assign ichrpsegcfg = SEGCFGS[ichcr_rpsegid];
    assign ichwpsegcfg = SEGCFGS[ichcr_wpsegid];

scedma.sv:66-67 (the index is a full 8 bits)
    bit [7:0]   ichcr_rpsegid;
    bit [7:0]   ichcr_wpsegid;

scedma_pkg.sv:232 (the table has only 18 entries)
    localparam SEGCNT = SEGID_RNGB+1;

contrast - scedma_amba.sv:426 (the AXI path DOES check)
    assign axim_segcfg = cr_segid < SEGCNT ? SEGCFGS[cr_segid] : SEGCFG_DEF;

scedma_ac.sv:35-46 (the rule lookup is also unbounded)
    logic [0:CHNLCNT-1][7:0]    chnlinsegid;
...
    logic [0:scedma_pkg::SEGCNT-1][0:scedma_pkg::CHNLACCNT-1] chnlacrules;
...
        assign chnlinsegid[i] = chnlinreq[i].segcfg.segid;
        assign chnlacrule = chnlacrules[chnlinsegid[i]][i] ;

scedma_amba.sv:266-276 (the fallback descriptor is a 1 KB window labelled LKEY)
    localparam segcfg_t SEGCFG_DEF =
            '{
                segid: '0,
                segtype: ST_NONE,
                ramsel: '0,
                segaddr: '0,
                segsize: 'd256,
                isfifo: '0,
                isfifostream: '0,
                fifoid: '0
            };
```

**Preconditions.** Attacker can write `sfr_ich_segid` at 0x4002_9054 (no lock, `scedma.sv:91`). Exploitability depends on how the synthesis tool resolved the don't-care branches of the out-of-range select, which cannot be determined from RTL alone on an already-fabricated part.

**Attack scenario.** 1. Attacker writes 0x4002_9054 with an rp/wp segment ID >= 18 (e.g. 0x12 = 18, or 0xFF).
2. `ichrpsegcfg = SEGCFGS[18]` selects a don't-care entry. Whatever `segaddr`/`segsize`/`segid` the synthesised mux emits becomes the ich channel's descriptor, with no relation to any real segment - it may point the ich read port at an arbitrary SCERAM base with an arbitrary size, which then also relaxes the `rpptr > segsize` clamp of finding 2.
3. The resulting `segid` is forwarded to `scedma_ac`, where `chnlacrules[segid][6]` is another out-of-range select. If the optimiser resolved the don't-care to 1, `chnlac[6]` = allow and the ich read proceeds unconditionally; if it resolved to a low-bit alias, the attacker gets whichever segment's rule the alias maps to rather than the one the address actually hits.
4. Because `acerr` is dead (finding 3) and denials look like zero data, the attacker can sweep all 238 out-of-range values and observe which ones produce non-zero reads, then use the winner to move key words between segments.

**Mitigation.** RTL fix: apply the same guard the AXI path already has - `assign ichrpsegcfg = ichcr_rpsegid < SEGCNT ? SEGCFGS[ichcr_rpsegid] : SEGCFG_NULL;` (a NULL descriptor with segsize 0, not the 256-word SEGCFG_DEF), and reduce `sfr_ich_segid` to `$clog2(SEGCNT)` bits per field so the illegal encodings are unrepresentable. In `scedma_ac`, clamp or validate the index: `assign chnlacrule = ( chnlinsegid[i] < SEGCNT ) ? chnlacrules[chnlinsegid[i]][i] : 1'b0;` so an unknown segment fails CLOSED. Also change SEGCFG_DEF's `segsize` from 'd256 to '0 so the fallback grants nothing. Silicon workaround: firmware must treat 0x4002_9054 as a security-critical register - never expose the SCE APB window to code that is not already trusted with the crypto RAM, and always program `sfr_ich_segid` to a legal value before starting the ich channel so an attacker's stale value is not in effect.

**Verification.** Verified as written; exploitability not fully established. The evidence is verbatim correct and the asymmetry is real and damning: scedma_amba.sv:426 `assign axim_segcfg = cr_segid < SEGCNT ? SEGCFGS[cr_segid] : SEGCFG_DEF;` guards the AXI path, while scedma.sv:277-278 `assign ichrpsegcfg = SEGCFGS[ichcr_rpsegid];` / `ichwpsegcfg = SEGCFGS[ichcr_wpsegid]` do not, and the index fields are a full 8 bits each (scedma.sv:66-67) sourced from the 16-bit unlocked sfr_ich_segid at 0x4002_9054 (scedma.sv:113,124). SEGCNT is 18 (scedma_pkg.sv:232). scedma_ac.sv:35/46 confirm chnlinsegid is 8 bits and `chnlacrule = chnlacrules[chnlinsegid[i]][i]` indexes an 18-entry array with no bound, and I confirmed the ich path is the ONLY way to inject an out-of-range segid into scedma_ac (the AHB path's segid comes from scedmachnl_addr2seg which is bounded 0..17 by construction, and the AXI path is guarded at line 426). Per the LRM an out-of-range packed-array select is 'x, so simulation is undefined and synthesis is free to alias; the failure direction is genuinely unconstrained and could resolve to allow. It stays 'plausible' rather than 'confirmed' because the actual behaviour in the fabricated part is a synthesis artefact that cannot be determined from RTL - exactly the caveat the finder themselves stated. The secondary claim about SEGCFG_DEF (scedma_amba.sv:266-276, segsize 'd256, segid '0) is correct and, as I noted under finding 4, is actually more consequential than the finder realised because it is the landing zone that makes an out-of-range cr_segid usable.

**Corrections applied by the verifier.** No factual correction; the finder's own hedging is appropriate. Severity kept at medium - it is a real fail-open construct with a proven safe counterexample two files away, but no demonstrable exploit from RTL alone.

---

<a id="bao-040"></a>

### BAO-040 — transsize == 0 is decoded as 2^30 transfers and there is no abort path, giving an unstoppable SCE bus master

**Severity: Medium**

**Location:** `rtl/modules/crypto_top/rtl/sce_dmachnl.sv:110`

*Surfaced by the independent verifier, not the original domain reviewer.*

**Description.** `lasttrans` is `( transcnt == thecfg.transsize - 1 )`. transsize is a TRANSCNTW=30-bit software SFR (scedma_pkg.sv:27, scedma.sv:110 sfr_sch_transize DW(TSW)) whose reset value is 0. With transsize = 0 the comparand is 30'h3FFF_FFFF, and since transcnt is reset to 0 at chnlstart (line 108) the channel executes 2^30 transfers instead of none. There is no abort: `busy` (line 102) clears only on `done`, `done` is `lasttrans & transdone` (line 106), and writing the start address register again just re-asserts start while busy is already high, which is swallowed by `chnlstart = start & ~busy` (line 104). The only way to stop it is a full SCE reset (sfr_arrst, 0xa5/0x5a to 0x4002_801C), which is itself only reachable if the APB is still serviceable. Meanwhile scedma_amba.sv:313/384/400 advance aximprt every transfer and form `axim.araddr = cr_axaddrstart + aximprt * 4`, a 32-bit sum, so a single start sweeps up to 4 GiB of the AXI address space issuing reads or writes tagged hauser = AMBAID4_SCEA/SCES with the latched sceuser coreuser, and simultaneously saturates the SCERAM round-robin arbiter (sce_memc.sv:187-204) against the AES/hash/PKE/TRNG channels.

**Evidence.**
```systemverilog
sce_dmachnl.sv:102-114
    `theregrn( busy ) <=   start ? 1 : busy & done ? 0 : busy;

    assign chnlstart = start & ~busy;

    assign done = lasttrans & transdone;

    `theregrn( transcnt ) <= chnlstart ? 0 : transdone ? ( lasttrans ? 0 : transcnt + 1 ) : transcnt;

    assign lasttrans = ( transcnt == thecfg.transsize - 1 );

scedma.sv:110 (unlocked, reset value 0)
    apb_cr #(.A('h44 ), .DW(TSW)  ) sfr_sch_transize (.cr( schcr.transize ), .prdata32(),.*);

scedma.sv:91
    assign sfrlock = 0;

scedma_amba.sv:400
    assign axim.awaddr   = cr_axaddrstart + aximprt *4;
```

**Attack scenario.** Software that reaches the scedma APB window sets sfr_sch_func = 1 (SCERAM -> AXI), leaves sfr_sch_transize at its reset value of 0, points sfr_sch_axstart at the base of ReRAM or SRAM, and starts the channel. The channel then issues 2^30 AXI writes with SCE credentials, walking 4 GiB of address space, and cannot be stopped by any register write short of asserting the SCE reset. The same configuration with func = 0 turns the block into an unbounded read probe of the AXI map under the SCE's hauser tag. The natural encoding bug - N transfers means transsize = N, so 0 should mean 'no transfer' but means 2^30 - makes this reachable by simple omission as well as deliberately.

**Verification.** No independent verdict recorded for this entry.

---

<a id="bao-041"></a>

### BAO-041 — SCE AES engine has no fault detection: the round count is a single non-redundant equality compare and a faulted result is delivered as a normal completion

**Severity: Medium** | CWE-1247 Improper Protection Against Voltage and Clock Glitches | Threat actor: T2 (physical: clock/voltage glitch, EM or laser fault injection); T1 to drive the engine and read the faulty ciphertext out of AOB | Confidence: Medium

**Location:** `rtl/modules/crypto_aes/rtl/AesCtrl.v:846`

**Description.** The round schedule of the AES core is decided by one comparison of a free-running 8-bit counter against a constant, with no duplication, no residue/parity on the counter, no >= guard and no cross-check that the number of rounds actually executed matches the configured key length. The `err` output of the SCE AES wrapper carries only `ramerror` (ARAM parity), and even that does not abort the operation or suppress the writeback - `intr[0]` and `mfsm_done` fire on reaching MFSM_DONE regardless. There is no redundant computation, no comparison of two independent AES instances, and no ciphertext sanity check anywhere in AesCore, AesCtrl or aes.sv. Two concrete consequences: (a) a fault that makes AesCnt reach 9/11/13 early terminates the cipher after fewer rounds and the reduced-round ciphertext is written to AOB and announced as a valid completion; (b) because the compare is exact equality on a counter that also indexes the round-key RAM as `SCnt+12+(AesCnt<<2)` in an 8-bit address (AesCtrl.v EncAdr), a fault that makes AesCnt skip the terminal value causes the FSM to keep iterating with round-key addresses that overflow the 8-bit ARAM address and wrap into the plaintext/IV/state words 0..7 - the engine still eventually terminates (AesCnt wraps at 256 back through the terminal value) and still reports success, having produced a ciphertext computed under attacker-influenced garbage round keys and no error.

**Evidence.**
```systemverilog
rtl/modules/crypto_aes/rtl/AesCtrl.v:845-848  (single, non-redundant terminal-round decision):
//zhxj,20191013,to be revised!!! according AesLen
assign LastRound = AesLen == 2'b00 ? AesCnt == 8'd9 :
                   AesLen == 2'b01 ? AesCnt == 8'd11:
                                     AesCnt == 8'd13;

rtl/modules/crypto_aes/rtl/AesCtrl.v:646  (the only consumer - EnState leaves the round loop on that one bit):
	if(LastRound & StateEnd)

rtl/modules/crypto_top/rtl/aes.sv:533-534  (the entire error/interrupt surface of the engine):
    `theregrn( intr[0] ) <= ( mfsm == MFSM_DONE );
    `theregrn( err[0:1] ) <= ramerror;
```

**Preconditions.** Attacker can inject a timing/voltage/EM fault during an SCE AES operation and can read the resulting ciphertext (AOB is readable on all four DMA channels per the static rule 8'b10_10_10_10, and in the reset SCE mode scemode==0 the AHB window at 0x4002_1E00 is open to any master). Requires physical access.

**Attack scenario.** 1. Attacker (T1) loads a known plaintext block into the SCE AIB segment and starts an AES-128 encryption under the victim key (cr_func=AF_ENC, sfr_ar<=0x5a at 0x4002_D004). The engine takes a fixed, data-independent number of cycles (AesCtrl is constant-time), so the attacker can time the 9th round precisely from a single reference trace.
2. Attacker (T2) injects a clock or voltage glitch, or an EM/laser pulse, timed to corrupt one byte of the SReg state during round 9 - the standard Piret-Quisquater DFA target.
3. The engine has no redundancy, no round-count check and no output validation; AesCtrl.v:846 still fires LastRound at AesCnt==9, EN_STORE writes the faulty block to ARAM words 68..71, MFSM_WB_D DMAs it into the AOB segment, and aes.sv:533 raises intr[0] as a clean completion. err[0:1] stays 0 because only ARAM parity feeds it.
4. Attacker reads the faulty ciphertext from AOB (0x4002_1E00, readable on all channels) alongside the correct one. Two such faulty/correct pairs from a single-byte fault in round 9 recover the full AES-128 round key 10, hence the cipher key, by standard DFA.
5. Alternative primitive: glitch AesCnt so it skips the terminal value. The FSM does not deadlock or error - it iterates with round-key addresses SCnt+12+(AesCnt<<2) that overflow the 8-bit AesRamAdr and wrap into ARAM words 0..7 (the attacker's own plaintext/IV), then terminates normally when AesCnt wraps back through 9. The attacker thus obtains an AES computed with round keys that they partially control, again reported as success.

**Mitigation.** RTL fix: (1) make the terminal-round decision redundant - compute LastRound from two independently-reset counters (or a counter plus its one's complement) and raise a hard error if they disagree; use `>=` rather than `==` so a skipped value cannot extend the loop. (2) Add an end-of-operation check that the number of EN_ROUND1/StateEnd events equals the expected round count for AesLen, and gate MFSM_WB_D on it. (3) Feed a real fault flag into the existing but unused err[2:7] bits of aes.sv and have it suppress the AOB writeback rather than merely report. (4) Best practice for a part in this class: duplicate the cipher (or recompute and compare, or verify by decrypting the result) and zero the output on mismatch.
Software workaround on fabricated silicon: firmware can approximate the missing check by performing every security-critical AES operation twice with the same inputs and comparing the two AOB results before use, or by encrypting-then-decrypting and checking the round trip. This costs 2x throughput and still leaves a window if the attacker faults both runs identically, but it removes the single-fault DFA primitive. Firmware should also monitor the tamper/glitch sensors (secsub) and refuse to use SCE outputs produced while a sensor event was pending - noting that sensorc's cr_vdmask0/1 default to all-ones, so those detectors must be explicitly unmasked first.

**Verification.** Independently confirmed by a second reviewer. AesCtrl.v:845-848 reproduces verbatim including the `//zhxj,20191013,to be revised!!!` comment, and it is the single decision: `assign LastRound = AesLen == 2'b00 ? AesCnt == 8'd9 : AesLen == 2'b01 ? AesCnt == 8'd11 : AesCnt == 8'd13;`. Its only consumer is AesCtrl.v:646 `if(LastRound & StateEnd)` in the EN_ROUND1 arm of the encrypt FSM. AesCnt is a single 8-bit counter (declaration at 225, update at 868-879) with no parity, no duplicate, and no residue. aes.sv:533-534 reproduces verbatim: `\`theregrn( intr[0] ) <= ( mfsm == MFSM_DONE ); \`theregrn( err[0:1] ) <= ramerror;` — I grepped for any other driver of `err` in aes.sv and there is none, so err[2:7] of the 8-bit ERRCNT vector are undriven and ramerror (ARAM parity) neither aborts the MFSM nor suppresses the MFSM_WB_D writeback. I searched AesCore.v, AesCtrl.v, AesDataPath.v and aes.sv for any redundant computation, output check, or round-count assertion and found none. The secondary claim (b) also holds structurally: AesRamAdr is 8 bits (AesCtrl.v:66) and EncAdr uses `SCnt+12+(AesCnt<<2)` (AesCtrl.v:940-941), so a skipped terminal value wraps the round-key address into low ARAM before AesCnt rolls back through the terminal value. This is an absence-of-countermeasure finding, but it is a concrete, quotable one, and DFA on AES-128 from round-9 faults is textbook.

**Corrections applied by the verifier.** None material. Note for the vendor that consequence (b) — the address wrap into ARAM words 0..7 — is a structural inference from AesCtrl.v:66/940-941 and was not simulated; consequence (a), the classic Piret-Quisquater single-fault DFA on round 9, is the one that stands on its own.

---

<a id="bao-042"></a>

### BAO-042 — TRNG CTR_DRBG never reseeds in its default configuration: reseed_interval==0 disables the reseed path entirely

**Severity: Medium** | CWE-335 Incorrect Usage of Seeds in Pseudo-Random Number Generator (PRNG) | Threat actor: T1 (unprivileged software that consumes TRNG output, or that simply never programs the reseed interval); T2 if combined with entropy-source degradation | Confidence: High

**Location:** `rtl/modules/crypto_trng/rtl/ctr_aes.v:187`

**Description.** The CTR_DRBG reseed trigger is conditioned on `reseed_interval != 2'h0`, and its complement - the branch that keeps the DRBG generating without reseeding - is unconditionally taken when `reseed_interval == 2'h0`. The `reseed_value` lookup at ctr_aes.v:208-215 has no case for 2'd0 and falls through to `default: reseed_value = RESEED_3`, which superficially suggests a 1024-block interval, but that value is never used because both the reseed-set term and the continue term are gated on the interval being non-zero. The net effect is that with the reset-state configuration the DRBG enters GEN2/GEN3 and cycles there forever: it produces an unbounded number of 128-bit outputs from a single 256-bit seed drawn once out of the entropy buffer at the IDLE->RESEED transition, never re-absorbing fresh entropy from the ring oscillators. This violates the SP800-90A reseed requirement and means that a single compromise or degradation of the seed (whose source, `buf_data`, is itself software-readable and software-writable over APB at 0x4002_E030) compromises all subsequent output for the lifetime of the reset domain, with no automatic recovery.

**Evidence.**
```systemverilog
rtl/modules/crypto_trng/rtl/ctr_aes.v:184-188:
assign gen3_done_reseed_set= (ctr_state==GEN3  ) & aes_done & (reseed_cnt  ==(reseed_value-1'b1)) & (reseed_interval!=2'h0);
assign gen3_done_reseed_pre= gen3_done_reseed_set ? 1'b1 :(gen3_done_reseed & buf_ready)? 1'b0: gen3_done_reseed;
assign gen3_done_reseed_neg= (~gen3_done_reseed_pre)& gen3_done_reseed;
assign gen3_done_gen1  = (ctr_state==GEN3  ) & aes_done &((reseed_cnt  !=(reseed_value-1'b1)) | (reseed_interval==2'h0));
assign drng_reseed_req = gen3_done_reseed_set;

rtl/modules/crypto_trng/rtl/ctr_aes.v:208-215  (the default arm is unreachable because of the gating above):
always@(*)begin
    case(reseed_interval)
	2'd1   : reseed_value = RESEED_1;     
	2'd2   : reseed_value = RESEED_2;     
	2'd3   : reseed_value = RESEED_3;
	default: reseed_value = RESEED_3;
    endcase
end 

rtl/modules/crypto_top/rtl/trng.sv:110,257-258,311  (the interval is a plain unlocked CR with no reset value, i.e. 0):
    apb_cr #(.A('h08), .DW(17) )      sfr_pp          (.cr(cr_postproc), .prdata32(),.*);
    assign { cr_reseed_sel,
            cr_reseed_intval[1:0],
    /*        input  logic [1:0]        */ .reseed_interval           ( cr_reseed_intval[1:0] ),

rtl/modules/crypto_top/rtl/trng.sv:52  (module write-protect hardwired off, so software can also clear it back to 0 at any time):
    `theregrn( sfrlock ) <= '0;
```

**Preconditions.** The TRNG post-processor is configured for CTR_DRBG mode (cr_postproc_opt == 2). cr_postproc (sfr_pp at 0x4002_E008) is an apb_cr with no .IV, so cr_reseed_intval powers up as 2'b00 and stays there unless firmware explicitly writes a non-zero value; the module's sfrlock is hardwired to 0 so nothing prevents software from writing it back to zero at any time.

**Attack scenario.** 1. The SoC comes out of reset. cr_postproc (0x4002_E008) is all zeros, so cr_reseed_intval = 0 and cr_postproc_opt = 0. Firmware selects CTR_DRBG by writing cr_postproc_opt=2 but - because the reset state is 0 and nothing forces otherwise - leaves cr_reseed_intval at 0. Alternatively an attacker with T1 write access to the unlocked sfr_pp simply writes cr_reseed_intval back to 0 at any time; trng.sv:52 hardwires sfrlock low so this always succeeds.
2. ctr_aes takes its one and only seed at the IDLE->RESEED transition: aes_key = K0 ^ buf_data[255:128] ^ personalization_string[255:128], aes_text_in = M0 ^ buf_data[127:0] ^ personalization_string[127:0] (ctr_aes.v:163,171). K0/M0 are compile-time constants and personalization_string is a software SFR (sfr_drpsz at 0x4002_E020).
3. From then on, gen3_done_reseed_set is permanently 0 (reseed_interval==2'h0) and gen3_done_gen1 is permanently satisfied, so the FSM loops GEN2 -> GEN3 -> GEN2 indefinitely. Every 128-bit word ever delivered into the RNGA/RNGB pools - and therefore every key, nonce and blinding value derived from the TRNG for the rest of that reset domain - is a deterministic function of that single 256-bit seed.
4. Because buf_data is directly readable over APB at 0x4002_E030-0x4002_E03C and directly writable in DRNG mode, an attacker (T1) who reads or sets the seed once predicts the entire subsequent output stream. Without reseeding there is no forward recovery: the DRBG never re-absorbs entropy, so a one-time seed compromise is permanent.

**Mitigation.** RTL fix: remove the `& (reseed_interval!=2'h0)` qualifier at ctr_aes.v:184 and the `| (reseed_interval==2'h0)` escape at ctr_aes.v:187, and give reseed_value a safe non-zero mapping for the 2'd0 case (it already defaults to RESEED_3=1024) so that interval 0 means "reseed every 1024 generates" rather than "never reseed". Give sfr_pp a non-zero reset value that selects a conservative interval, and make the reseed-interval field write-once/lockable (trng.sv:52 currently hardwires sfrlock to 0), so untrusted software cannot turn reseeding off.
Software workaround on fabricated silicon: fully mitigable in firmware. Secure boot must program cr_postproc (0x4002_E008) with cr_reseed_intval set to 1, 2 or 3 (1 / 128 / 1024 generates) at the same time it selects cr_postproc_opt=2, and must do so before any TRNG output is consumed. Because trng.sv:52 leaves sfrlock at 0, firmware cannot lock the register, so the TRNG SFR window (0x4002_E000) must be kept out of reach of untrusted masters, and privileged code should re-verify cr_reseed_intval is non-zero before drawing key material. As defence in depth, firmware should also periodically force a reseed by toggling rngcore_en (returning the FSM to IDLE, which re-draws the seed) and should mix TRNG output with an independent source before using it as key material.

**Verification.** Independently confirmed by a second reviewer. ctr_aes.v:184-188 reproduces verbatim. The gating is exactly as claimed: line 184 ANDs `& (reseed_interval!=2'h0)` onto the reseed trigger and line 187 ORs `| (reseed_interval==2'h0)` onto the continue-generating term, so with interval 0 the FSM can only take the GEN3->GEN1/GEN2 arms (state machine at 111-120) and never reaches RESEED. The case at 208-215 does default to RESEED_3, but that arm is dead under the interval==0 gating — the finder is right that it is misleading rather than protective. I confirmed the parameter values at ctr_aes.v:22-24 (RESEED_1=1, RESEED_2=128, RESEED_3=1024). On the reset state: trng.sv:110 is `apb_cr #(.A('h08), .DW(17) ) sfr_pp (.cr(cr_postproc), .prdata32(),.*);` with no `.IV` parameter, and apb_cr's default is `parameter IV=32'h0` (apb_sfr.sv:81), so cr_postproc powers up all-zero; trng.sv:257-258 unpacks cr_reseed_intval[1:0] out of it and trng.sv:311 wires it to `.reseed_interval`. trng.sv:52 `\`theregrn( sfrlock ) <= '0;` confirms the register can be rewritten to zero at any time by any master that reaches the TRNG SFR window. The seed is drawn once at IDLE->RESEED from K0/M0 ^ buf_data ^ personalization_string (ctr_aes.v:163,171), and buf_data is exposed via `apb_buf #(.BAW(3), .A(12'h30), .DW(32)) sfr_buf` (trng.sv:278). Precondition is accurately stated: this only bites in CTR_DRBG mode (postprocess.v:156-166 shows postprocess_opt==2 selects ctr_dataout), which firmware must opt into.

**Corrections applied by the verifier.** None. The finding is correctly scoped as conditional on firmware selecting cr_postproc_opt=2 while leaving cr_reseed_intval at its reset value of 0; the report should keep that qualifier prominent rather than the unqualified word 'default' in the title, since the reset default of cr_postproc_opt is 0 (LFSR post-processing), not CTR_DRBG.

---

<a id="bao-043"></a>

### BAO-043 — PKE side-channel countermeasure is disabled at reset, uses a fixed-IV deterministic LFSR as its "random" source, and its reseed injects only one bit of entropy

**Severity: Medium** | CWE-1241 Use of Predictable Algorithm in Random Number Generator | Threat actor: T2 (power/EM side-channel measurement); T1 to leave the countermeasure disabled | Confidence: High

**Location:** `rtl/modules/crypto_top/rtl/pke.sv:788`

**Description.** Three compounding defects in the PKE's DPA countermeasure:

(1) It is off by default. `optsec` is registered from `mimmcr[3]` (pke.sv:788-789), and `mimmcr` is `sfr_mimmcr` (pke.sv:310), an ordinary `apb_cr` that resets to 0. With `optsec == 0`, `mimm_dbrnd` is forced to zero (pke.sv:793) and, inside `mac_cell`, the idle multiplier lanes are driven with zeros (`pb[i] = ... ( opt_sec ? DB_rnd : '0 )`, mac_cell.sv:51), so the multiplier array's switching activity is purely a function of the real key-dependent operands.

(2) When enabled, the "random" is not random. `mimm_dbrnd` comes from two `drng_lfsr` instances with hard-coded compile-time initial values `'h5a5a_a5a5` and `'ha5a5_5a5a` (pke.sv:800,805), clocked only while `optsec` is asserted (`.sen(optsec)`). The sequence is therefore identical on every reset and fully predictable by anyone with the netlist. There is no connection from the TRNG to this block anywhere in pke.sv.

(3) The software reseed is one bit wide. `drng_lfsr`'s write path XORs only the top bit of the input into the whole state: `sen ? ( swr ? ( sdin[LFSR_IW-1] ^ sdata ) : sdatapre ) : sdata` (insauth.v:38). Writing the 32-bit `sfr_maskseed` (pke.sv:316) and pulsing `sfr_maskseedar` therefore injects at most one bit of entropy into a 229-bit state.

Separately, even at its best this is a dummy-operation scheme, not blinding: `pa[i]` is driven with the REAL operand word `DA[i]` in the dummy cycles too (mac_cell.sv:49), so the dummy multiplies are (secret operand) x (known LFSR value) — a known-multiplicand product that itself leaks DA.

**Evidence.**
```systemverilog
pke.sv:310
    apb_cr #(.A('h24), .DW(9))       sfr_mimmcr     (.cr(mimmcr), .prdata32(),.*); //## width?

pke.sv:788-793
    `theregfull( clkpke, resetn, optsec0, '0 ) <= mimmcr[3];
    `theregfull( clkpke, resetn, optsec,  '0 ) <= optsec0;
`ifdef FPGA
    assign mimm_dbrnd = '0;
`else
    assign mimm_dbrnd = optsec ? pkemaskdat : '0;
`endif

pke.sv:798-805
    drng_lfsr #( .LFSR_W(229),.LFSR_NODE({ 10'd228, 10'd225, 10'd219 }), .LFSR_OW(32), .LFSR_IW(32), .LFSR_IV('h5a5a_a5a5) )
        ua( .clk(clkpke), .sen(optsec), .resetn(resetn), .swr(maskseedupd_sync), .sdin(maskseed), .sdout(pkemaskdat[31:0]) );
    drng_lfsr #( .LFSR_W(229),.LFSR_NODE({ 10'd228, 10'd225, 10'd219 }), .LFSR_OW(32), .LFSR_IW(32), .LFSR_IV('ha5a5_5a5a) )
        ub( .clk(clkpke), .sen(optsec), .resetn(resetn), .swr(maskseedupd_sync), .sdin(pkemaskdat[31:0]), .sdout(pkemaskdat[63:32]) );

rtl/modules/common/rtl/insauth.v:36-38
    reg [LFSR_W-1:0] sdata=LFSR_IV, sdatapre, stap;

    `theregfull( clk, resetn, sdata, LFSR_IV ) <= sen ? ( swr ? ( sdin[LFSR_IW-1] ^ sdata ) : sdatapre ) : sdata ;

rtl/modules/crypto_pke/rtl/mac_cell.sv:48-53
			assign pp[i] = pa[i] * pb[i];
			assign pa[i] =  ( opt_pl >= i )&&( ME | ~ME & opt_sec )  ? DA[i] : '0;
			assign pb[i] =  ME & ( opt_pl >= i ) ? DB :
						   ~ME & ( opt_pl >= i ) ? ( opt_sec ? DB_rnd : '0 ) : '0;
//			`thereg ({ pcc[i], pss[i] }) <= ME & ( opt_pl >= i ) ? DA[i] * DB : '0;//{ pcc[i], pss[i] } ;
			`thereg ({ pcc[i], pss[i] }) <= ( opt_pl >= i )&&( ME | ~ME & opt_sec ) ? pp[i] : '0;
```

**Preconditions.** For the 'disabled' case: none — `mimmcr` is an APB CR that resets to 0, so `optsec = mimmcr[3] = 0` out of reset and the countermeasure is off unless firmware explicitly enables it. For the 'predictable' case: the attacker collects power/EM traces of PKE operations; because the LFSR state is a compile-time constant at reset and only advances while `optsec` is asserted, the dummy-operand sequence is identical on every power-up.

**Attack scenario.** Case A (countermeasure left off — the default): 1. Firmware performs an RSA or ECC private-key operation without ever writing `mimmcr[3]`. 2. `optsec == 0`, so `mimm_dbrnd == 0` and the PL=4 multiplier lanes are zeroed on non-multiply cycles. 3. An attacker with T2 access collects power/EM traces. Because the multiplier's Hamming-weight profile is now an unmasked function of the operand words, standard CPA on the multiplier output recovers the Montgomery operands, and thence the private exponent/scalar, in a few thousand traces.

Case B (countermeasure on): 1. Firmware sets `mimmcr[3]=1`. 2. The dummy operands are `pkemaskdat`, the output of a 229-bit LFSR whose state at reset is the constant `'h5a5a_a5a5` / `'ha5a5_5a5a` and which advances deterministically. 3. The attacker, who has the netlist, simulates the LFSR from reset and knows `DB_rnd` for every cycle of every operation. 4. The dummy-cycle contribution to the power trace is therefore a known, subtractable constant; worse, since `pa[i]` carries the real operand `DA[i]` even in dummy cycles, the dummy cycles supply extra traces of DA multiplied by a KNOWN value — an ideal CPA target. The countermeasure does not increase the attacker's work and arguably decreases it. 5. Attempting to fix this in firmware by writing `sfr_maskseed` from the TRNG achieves almost nothing, because only bit 31 of the written word is XORed into the state.

**Mitigation.** RTL fix: (a) seed both `drng_lfsr` instances from the TRNG's conditioned output rather than a compile-time `LFSR_IV`, and re-seed at the start of every PKE operation; (b) fix `insauth.v:38` so the whole `sdin` word is XORed into the state (`sdin ^ sdata[LFSR_IW-1:0]`), not just `sdin[LFSR_IW-1]`; (c) drive `sen` from a constant 1 so the generator free-runs and does not restart from a known state when the countermeasure is toggled; (d) default `optsec` to enabled (invert the polarity of `mimmcr[3]`, or hard-wire it on when `mode_sec` is asserted), so a firmware omission fails closed; (e) change `pa[i]` (mac_cell.sv:49) so the dummy cycles use a random multiplicand as well, not the real `DA[i]`.

Firmware workaround on fabricated silicon: always set `mimmcr[3]=1` before any private-key operation; before each operation, pulse `sfr_maskseedar` (0x4002_C064) many times with fresh TRNG bits placed in bit 31 of `sfr_maskseed` (0x4002_C060) — 128+ pulses to accumulate 128 bits of state entropy. More importantly, do not rely on this mechanism at all: apply algorithmic exponent/scalar blinding and base blinding in software, which is independent of the broken hardware masking.

**Verification.** Independently confirmed by a second reviewer. All four sub-claims check out verbatim. (1) pke.sv:310 declares sfr_mimmcr as an apb_cr, and apb_cr's IV parameter defaults to 32'h0 (rtl/modules/amba/rtl/apb_sfr.sv:81), so mimmcr — and hence optsec=mimmcr[3] (pke.sv:788-789) — is 0 out of reset; mimm_dbrnd is then forced to '0 (pke.sv:793). (2) The two drng_lfsr instances at pke.sv:799 and 804 carry compile-time LFSR_IV of 'h5a5a_a5a5 and 'ha5a5_5a5a, with `.sen(optsec)` so the state does not advance unless the countermeasure is enabled; there is no TRNG connection anywhere in pke.sv. (3) insauth.v:38 is verbatim `<= sen ? ( swr ? ( sdin[LFSR_IW-1] ^ sdata ) : sdatapre ) : sdata ;` — sdin[31] is a 1-bit value XOR'd against a 229-bit vector, which zero-extends and therefore modifies only sdata[0]. A 32-bit maskseed write injects one bit. (4) mac_cell.sv:49 is verbatim `assign pa[i] = ( opt_pl >= i )&&( ME | ~ME & opt_sec ) ? DA[i] : '0;` — the real operand word drives the multiplicand in dummy cycles, so dummy products are (secret DA) x (known LFSR value). I found no compensating control: no reseed-from-TRNG, no lock, no mode_sec override.

**Corrections applied by the verifier.** Two corrections to framing. (a) mac_cell is instantiated only inside mac_core, which is instantiated only inside mimm (mimm.sv:235-255), i.e. the mmsel==1 datapath. Since mmsel=mimmcr[8]=0 at reset, in the default configuration the masking logic is not in the datapath at all — 'Case A' is therefore better stated as 'the DPA countermeasure does not exist on the default multiplier' rather than 'the countermeasure is off'. (b) Supporting evidence the finder missed and should include: the comment at pke.sv:797-798 records a tapeout deviation — 'LFSR_IV is too long, causes verilator errors. Original value: 'h55aa_aa55_5a5a_a5a5, assume truncatetion to the LSB's' — so the shipped seed is a 32-bit constant zero-extended into a 229-bit state, i.e. 197 of the 229 state bits are zero at reset. Severity: this is a countermeasure-quality defect requiring T2 power/EM measurement to exploit, not a software-reachable key read.

---

<a id="bao-044"></a>

### BAO-044 — ALU divider (aludiv) is a restoring shift-subtract whose per-bit iteration cost is the quotient bit itself — the operation's cycle count leaks the quotient's Hamming weight

**Severity: Medium** | CWE-208 Observable Timing Discrepancy | Threat actor: T1 (timing via APB status polling) and T2 (SPA) | Confidence: High

**Location:** `rtl/modules/crypto_alu/rtl/aludiv.sv:100`

**Description.** `aludiv` implements restoring division. For each quotient bit it runs MFSM_RND0 (compare remainder against shifted divisor) and then MFSM_RND1 (multi-word subtraction). Both phases are data-dependent:

(1) MFSM_RND1 is skipped entirely when the quotient bit is 0. `mfsm_rnd1skip` is latched from `mfsm_rnd1skippre = rnd0cyc_cmpflag & ( ramrdatreg > ramrdat )` (line 146) and short-circuits the RND1 state (line 100). The quotient bit is literally the negation of that flag: `assign qtbit = mfsm_rnd1skippre ? '0 : '1;` (line 176). So a 0 bit costs ~1 cycle and a 1 bit costs the full `dscnt`-word subtraction loop (3 cycles per word, line 158-164). For a 2048-bit divisor that is ~99 cycles per set bit.

(2) MFSM_RND0 terminates at the first differing word (`mfsm_rnd0done = rnd0cyc_cmpflag & ( ramrdatreg != ramrdat ) | ...`, lines 143-144), so even the compare phase length depends on the running remainder.

(3) The pre-normalisation loop MFSM_IFPRESFT/MFSM_PRESFT iterates once per leading zero of the divisor (`ifpresft = mfsm_ifpresftdone & ~ramrdat[DW-1]`, line 119).

The result is that the total division time is essentially an affine function of the Hamming weight of the quotient. On top of that, `alu.sv:146` publishes `sr_divlen` = {rmcnt, qtcnt}, the word counts of the remainder and quotient, i.e. the magnitude bucket of the result, in a plain readable status register.

**Evidence.**
```systemverilog
aludiv.sv:95-101
	assign mfsmnext = start ? MFSM_IFPRESFT :
						 (( mfsm == MFSM_IFPRESFT ) &&  mfsm_ifpresftdone ) ? ( ifpresft ? ( qs0err ? MFSM_DONE : MFSM_PRESFT ) : MFSM_RND0 ):
						 (( mfsm == MFSM_PRESFT ) &&  mfsm_presftdone ) ? MFSM_IFPRESFT :
					     (( mfsm == MFSM_RND0 ) && mfsm_rnd0done ) ? MFSM_WRQT :
					     (( mfsm == MFSM_WRQT ) ) ? MFSM_RND1 :
					     (( mfsm == MFSM_RND1 ) && mfsm_rnd1done | mfsm_rnd1skip ) ? ( mfsm_rndlast ? MFSM_DONE : MFSM_SFT1 ) :
					     (( mfsm == MFSM_SFT1 ) && mfsm_sft1done ) ? MFSM_RND0 :

aludiv.sv:119
	assign ifpresft = mfsm_ifpresftdone & ~ramrdat[DW-1];

aludiv.sv:143-146
	assign mfsm_rnd0done = rnd0cyc_cmpflag & ( ramrdatreg != ramrdat ) |
						   rnd0cyc_cmpflag & ( ramrdatreg == ramrdat ) & ( ramaddr_rnd0pl1 == ( dsidx_lsb/DW + RAMBASE_DS));
	`theregrn( mfsm_rnd1skip ) <= start|mfsm_rnd1done ? '0 : mfsm_rnd0done ? mfsm_rnd1skippre : mfsm_rnd1skip;
	assign mfsm_rnd1skippre = rnd0cyc_cmpflag & ( ramrdatreg > ramrdat );

aludiv.sv:174-176 (the skipped-subtraction flag IS the quotient bit)
	assign qtreg_clr = start;
	assign qtreg_lshb = ( mfsm == MFSM_RND0 ) && mfsm_rnd0done;
	assign qtbit = mfsm_rnd1skippre ? '0 : '1;

rtl/modules/crypto_alu/rtl/alu.sv:146 (result magnitude published in a status register)
    apb_sr #(.A('h14), .DW(16))      sfr_srdivlen   (.sr(sr_divlen), .prdata32(),.*);

rtl/modules/crypto_alu/rtl/alu.sv:512-517 (key-segment guard only armed in mode_sec)
    `theregrn( aluinvld ) <= mode_sec & (
            ( scedma_pkg::SEGCFGS[cr_segcfg[0][15:12]].segtype == scedma_pkg::ST_KI )|
```

**Preconditions.** Firmware uses the crypto ALU's AF_DIV function (alu.sv:48,167) to reduce a secret value modulo a public modulus — e.g. reducing an ECDSA nonce or an RSA blinding factor. Note the ALU's key-segment guard `aluinvld` (alu.sv:512-517) is only armed when `mode_sec` is set, so in `mode_non`/`mode_xls` even ST_KI segments can be fed to the divider.

**Attack scenario.** 1. Firmware reduces a secret bignum modulo a public modulus using the ALU AF_DIV function (e.g. reducing a wide random value into [0,n) to produce an ECDSA nonce, or normalising a blinding factor).
2. Unprivileged attacker software polls `sfr_srmfsm` (0x4002_F008) or `sfr_fr` (0x4002_F00C) to time the operation, or simply counts its own cycles across the ALU busy window.
3. Because RND1 is skipped for every zero quotient bit and costs ~3*dscnt cycles for every one bit, the measured duration is (constant + HW(quotient) * 3 * dscnt). The attacker recovers the exact Hamming weight of the quotient.
4. For a nonce derived as `k = wide_random mod n`, the quotient's Hamming weight plus the `sr_divlen` word counts constrain k substantially. Repeated across signatures, the leaked bias is fed to a hidden-number-problem lattice attack to recover the ECDSA private key.
5. With T2 (SPA), the RND0/RND1 alternation is directly visible in the power trace, giving the quotient bits in order rather than just their weight — a complete readout of the reduction.

**Mitigation.** RTL fix: make the division constant-time — always execute the MFSM_RND1 subtraction for the full `dscnt` words and select between the subtracted and unsubtracted remainder with an arithmetic mask derived from the borrow, instead of skipping the state (aludiv.sv:100,145-146). Remove the early-exit term from `mfsm_rnd0done` (line 143) so the compare always scans all words, and make the MFSM_IFPRESFT/PRESFT normalisation run a fixed number of passes. Also gate `sr_divlen` (alu.sv:146) so it is not readable in secure mode.

Firmware workaround on fabricated silicon: do not use AF_DIV on secret operands. Derive nonces by rejection sampling from the TRNG rather than by modular reduction, or blind the dividend (reduce `x + r*n` for random r and correct afterwards) so the quotient's Hamming weight is a function of r rather than of x. If AF_DIV must be used on a secret, ensure `mode_sec` is asserted so the ST_KI guard at alu.sv:512-517 at least blocks key-typed segments.

**Verification.** Independently confirmed by a second reviewer. aludiv.sv:95-103 is the quoted FSM verbatim; 119, 143-146 and 174-176 are verbatim. I traced the skip path: mfsm_rnd1skip is latched on mfsm_rnd0done from mfsm_rnd1skippre (line 145-146); the next-state term at line 100 parses as ((mfsm==RND1) && mfsm_rnd1done) | mfsm_rnd1skip, so with skip set the FSM leaves RND1 after one cycle and, because ramwr_rnd1 = (mfsm_rnd1cyc0=='h2) (line 164) and rnd1cyc0 only reaches 0 in that cycle, no subtraction is written. Without skip, RND1 walks words at 3 cycles each (lines 158-164) until ramaddr_rnd1 reaches deidx_msd. qtbit = ~mfsm_rnd1skippre (line 176) makes the timing literally the quotient bit. The RND0 early exit at line 143 is real. alu.sv:146 (`sfr_srdivlen`) and alu.sv:512-517 (aluinvld gated on mode_sec) are both verbatim, and I confirmed sr_divlen = {rmcnt,qtcnt} at alu.sv:318. No constant-time alternative divider exists in crypto_alu.

**Corrections applied by the verifier.** Minor: the ST_KI guard the finder cites as a partial mitigation is itself further weakened — alu.sv's `mode_sec` input is driven from sce.sv:139 `assign alusec = devmode_sce[4] ? '0 : mode_sec;`, and sce.sv:131 `assign devmode_sce = devmode ? '1 : nvrcfg[28];`, so the key-segment guard is disabled entirely in devmode or when bit 4 of NVR config byte 28 is set. The firmware advice 'ensure mode_sec is asserted so the ST_KI guard blocks key-typed segments' should note that dependency.

---

<a id="bao-045"></a>

### BAO-045 — Detected PKE RAM parity errors are reported as a status flag only — the faulty result is still computed and written out, enabling Bellcore-style fault attacks

**Severity: Medium** | CWE-1261 Improper Handling of Single Event Upsets | Threat actor: T2 (laser fault injection, clock/voltage glitching, EM fault injection) | Confidence: Medium

**Location:** `rtl/modules/crypto_top/rtl/pke.sv:1552`

**Description.** The PKE datapath does implement error detection: both `cryptoram` PRAM instances are configured with `isPRT: '1` (pke.sv:1502) and report `ramerror0`/`ramerror1`, and `mimm_dpram` computes and checks a per-byte parity across its 72-bit word (mimm_dpram.sv:82-90), producing `parityerr`. All three are OR-ed into `err[0]` (pke.sv:1552).

But `err` is a pure status output. It travels to `sce.sv:503 .err(pke_err)`, is bundled into `glb_err` (sce.sv:249), and terminates in `apb_fr #(.A('h18), .DW(ERRCNT)) sfr_frerr` (sce_glbsfra.sv:84) — a software-readable flag register. Nothing in PkeCore, PkeCtrl, mimm or pke.sv consults `err`, `parityerr`, `ramerror0` or `ramerror1`. The state machines do not abort, the result is not suppressed, and the output DMA channel still copies the (corrupted) result out to the destination segment. There is also no result verification anywhere in the PKE (no recomputation, no consistency check between the two CRT halves, no `s^e mod N == m` check in hardware).

So an injected fault that the hardware DEMONSTRABLY DETECTS still produces a usable faulty signature. The only defence is that firmware must remember to poll `sfr_frerr` at 0x4002_8018 after every operation and discard the result — an easy omission, and a check that can itself be skipped by a second glitch.

**Evidence.**
```systemverilog
pke.sv:1500-1503 (parity is enabled on the PKE working RAMs)
        isBWEN: '1,
        isSCMB: '1,
        isPRT:  '1,
        EVITVL:  15

pke.sv:1551-1552 (errors go to a status bit and nowhere else)
    `theregrn( intr[0] ) <= ( mfsm == MFSM_DONE );
    `theregrn( err[0] ) <= |{ ramerror0, ramerror1, parityerr };

rtl/modules/crypto_pke/rtl/mimm_dpram.sv:82-90 (parity is computed and checked)
    		assign wdata72[8][i] = ^wdata64[i];
    		assign wdata72[i] = wdata64[i];
    		assign rdataerr[i] = rdatavld & (rdata72[8][i] != ^rdata72[i]);
    	end
    endgenerate

    `thereg( rdatavld ) <= rd;

    assign parityerr = |rdataerr;

rtl/modules/crypto_top/rtl/sce.sv:249 (bundled into a flag word)
    assign glb_err  = { ramerr[0][0:1] , hash_err[0:1] , pke_err[0:1] , aes_err[0:1] } | '0;

rtl/modules/crypto_top/rtl/sce_glbsfra.sv:84 (terminates in a read-only flag register)
    apb_fr #(.A('h18), .DW(ERRCNT)) sfr_frerr       (.fr(fr_err),     .prdata32(),.*);

(By contrast, PkeCtrl.sv's ModExp/PointMul FSMs — lines 1238-1343, 4710-4946 — contain no reference to any error input; they always run to MODEXP_END / ECCPM_END regardless.)
```

**Preconditions.** Attacker has physical access and can inject a transient fault into one of the two PKE working RAMs (PRAM, 2x512x64) or into the MIMM Montgomery-intermediate DPRAM while an RSA-CRT exponentiation or ECC scalar multiply is in flight, and can obtain the resulting signature.

**Attack scenario.** 1. Attacker decapsulates the device and targets one of the PRAM macros with a laser, or applies a precisely timed clock/voltage glitch during an RSA-CRT signature.
2. A single bit flips in the working value of one CRT half (S_p) while the other half (S_q) is computed correctly. The RAM's parity check detects this and sets `parityerr`/`ramerror`, which propagates to `sfr_frerr` bit for the PKE.
3. But no FSM in PkeCore/PkeCtrl/mimm looks at that signal. MODEXP_END is reached normally, `PkeInt` fires, `mfsm` reaches MFSM_DONE, and the output channel copies the faulty S out to the destination segment.
4. Firmware that does not poll 0x4002_8018 between the operation and the release of the signature emits the faulty signature S'.
5. The attacker computes gcd(S'^e - m, N) = p, factoring the RSA modulus and recovering the private key from a single faulty signature (Boneh-DeMillo-Lipton). The equivalent attack on the ECC ladder (a faulty point that lands on a weak twist, or a differential fault on the final iteration) recovers the scalar.
6. Even if firmware does check `sfr_frerr`, the check is a software branch that a second glitch on the CPU can skip; the hardware provides no independent enforcement.

**Mitigation.** RTL fix: route `err[0]` (pke.sv:1552) back into PkeCore/PkeCtrl as a hard abort — force `PkeState` to an error state, suppress `pcore_done`, and zeroise the destination segment so no result is emitted. Equivalently, gate the output DMA channel (`chnlo_en`) on `~err`. The same treatment is needed for the ALU (`alu.sv:620 err[0:1] <= ramerror[1]|ramerror[0]`). Additionally add an infection/verification step: recompute the last ladder iteration and compare, or (for RSA) verify S^e mod N == m in hardware before releasing the result. Make the error condition sticky and clearable only by an SCE reset so a single glitch cannot clear it.

Firmware workaround on fabricated silicon: after EVERY PKE operation and before using or releasing the result, read `sfr_frerr` at 0x4002_8018 and treat any PKE error bit as fatal — zeroise the output segment and abort. Perform this check redundantly (read it twice, from two independent code paths, with the result combined) so a single instruction-skip glitch cannot bypass it. For RSA-CRT specifically, always verify the signature with the public exponent in software before releasing it, and for ECDSA verify the produced signature before output; this is the only defence that also covers faults the parity check does not catch (e.g. faults in the multiplier logic rather than in RAM).

**Verification.** Independently confirmed by a second reviewer. pke.sv:1500-1503 (isBWEN/isSCMB/isPRT:'1/EVITVL) is verbatim at those exact lines; pke.sv:1551-1552 is verbatim, with err[0] the OR of ramerror0, ramerror1 and parityerr. mimm_dpram.sv:82-90 computes and checks per-byte parity as quoted (ASIC branch; the FPGA branch stubs it at line 47, irrelevant to the tapeout). sce.sv:503 routes it to pke_err, sce.sv:249 bundles it into glb_err, and sce_glbsfra.sv:84 terminates it in an apb_fr status register — all verbatim. I independently confirmed the negative claim: `grep parityerr` over PkeCore.sv returns only the port declaration (29, 66, 69) and the mimm_dpram connection (412); it is a pure output with no consumer. `grep ramerror0/ramerror1` over pke.sv returns only the two cryptoram instantiations and line 1552. PkeCtrl's only error-ish signal, ErrorDetect (PkeCtrl.sv:2481), is a ModInv iteration watchdog unrelated to RAM parity. Nothing suppresses pcore_done, aborts the FSM, or gates chnlo_en on err.

**Corrections applied by the verifier.** Two additions worth making to the report. (a) The same pattern is confirmed in the ALU: alu.sv:619 `theregrn( err[0:1] ) <= ramerror[1]|ramerror[0];` is the sole consumer of ALURAM error there too (and note the 2-bit LHS is driven by a 1-bit expression, so both bits carry the same value). (b) pke.sv assigns only err[0]; err[1], which sce.sv:249 samples as pke_err[1] into the status word, is never driven in pke.sv — so half the PKE error field reported to software is meaningless. Severity medium is correct: this requires T2 fault injection and the parity mechanism does at least detect the fault, so it is a missing-enforcement gap rather than an absent defence.

---

<a id="bao-046"></a>

### BAO-046 — mimm round count truncates; top words silently dropped

**Severity: Medium** | CWE-682 Incorrect Calculation | Threat actor: T1 | Confidence: Medium

**Location:** `rtl/modules/crypto_pke/rtl/mimm.sv:121`

*Introduced at the synthesis stage with no structured reviewer record. Read against the RTL
directly during assembly by the orchestrating model; evidence below is quoted from source.*

**Description.** The Montgomery multiplier's round count is computed with truncating integer division: `lastrnd` asserts at `nlen/(opt_pl+1) - 1`. Where `nlen` is not an exact multiple of the pipeline factor `opt_pl+1`, the final partial round is never executed and the top words of the operand are silently dropped from the reduction. The result is returned as a normal completion with no error indication.

**Evidence.**
```systemverilog
// mimm.sv:121
    assign lastrnd = ( mfsmrnd == nlen/(opt_pl+1) - 1 );
    assign firstrnd = ( mfsmrnd == 0 );
    `theregrn( mfsmrnd ) <= start ? 0 : mfsmrnd+mfsm_s2done;
```

**Attack scenario.** An operand length that is not a multiple of the configured pipeline factor yields a silently incorrect modular product. In a signing or key-agreement operation this produces a mathematically invalid result from valid inputs - the precondition for Bellcore-style fault analysis, except reachable purely by choosing an operand length, with no fault injection equipment required.

**Mitigation.** RTL: round up rather than truncate, or assert that `nlen mod (opt_pl+1) == 0` and raise an error otherwise. Firmware: constrain every PKE operand length to an exact multiple of the configured pipeline factor, and validate results before use.

**Verification.** Read against the RTL during report assembly by the orchestrating model.
Not independently reviewed, not adversarially tested, and not seen by a human.

---

<a id="bao-047"></a>

### BAO-047 — Divide-by-zero guard tests the wrong index; ALU deadlocks

**Severity: Medium** | CWE-369 Divide By Zero | Threat actor: T1 | Confidence: Medium

**Location:** `rtl/modules/crypto_alu/rtl/aludiv.sv:120`

*Introduced at the synthesis stage with no structured reviewer record. Read against the RTL
directly during assembly by the orchestrating model; evidence below is quoted from source.*

**Description.** The divider's zero-divisor guard tests `dsidx_msb == 0`, the index of the divisor's most-significant set bit. That index is 0 both for a divisor of zero and for a divisor of one, so the guard conflates the two: a legitimate divide-by-one is flagged as an error, and the genuine zero case is not distinguished by the condition it was written for.

**Evidence.**
```systemverilog
// aludiv.sv:120
    assign qs0err = ifpresft & ( dsidx_msb == 0 );
```

**Attack scenario.** Software issuing a divide-by-one receives a spurious error, while the zero-divisor path is not separately identified. Depending on how `qs0err` is consumed downstream this either aborts valid operations or fails to abort invalid ones.

**Mitigation.** RTL: test the divisor for zero directly rather than inferring it from the MSB index. Firmware: screen divisor operands for 0 and 1 before submitting them to the ALU.

**Verification.** Read against the RTL during report assembly by the orchestrating model.
Not independently reviewed, not adversarially tested, and not seen by a human.

---

<a id="bao-048"></a>

### BAO-048 — Parity-filter mode forces digi_data_vld high regardless of the per-channel enable/valid bits, so the digitizer emits a stream of 'valid' constant bits from disabled, frozen entropy channels

**Severity: Medium** | CWE-1241 Use of Predictable Algorithm in Random Number Generator | Threat actor: T1 (unprivileged software write to 0x4002_E004); also reachable with no attacker at all as a silent firmware-initialisation error | Confidence: Medium

**Location:** `rtl/modules/crypto_trng/rtl/digitalization.v:83`

**Description.** digitalization.v produces two signals for the downstream conditioner: digi_data_out (the entropy bit) and digi_data_vld (the 'this bit is real' qualifier). When partityfilter_en is set, line 83-84 replaces the per-channel qualifier ana_vld_sys[0] with a literal 1'b1, so validity is asserted purely because the LF ring oscillator produced an edge (clk_ana_pos[0]) — with no reference to ana_en or ana_vld at all. Simultaneously line 81 forms the data bit as `^data_samp[ANA_NUM-1:0]`, the XOR of ALL eight channels, again ignoring ana_en, so channels the software believes it disabled still contribute. And line 61 makes a channel with ana_vld[i]==0 hold its previous sample forever: `assign data_samp_pre[i]=ana_vld[i]?ana_data[i]:data_samp[i];`. Combining these: with cr_ana at its reset value (an apb_cr with default IV='0, trng.sv:109, so ana_en=8'h00 and ana_vld=8'h00) and cr_pfilter_en set, all eight data_samp bits are frozen at their reset value 0, the XOR is constant 0, yet digi_data_vld pulses once per LF oscillator period. The downstream logic cannot tell the difference: data_buf.v:64-65 increments buf_cnt on digi_data_vld and data_buf.v:101 asserts buf_ready at 256, so the conditioner is handed a 256-bit all-zero 'seed' and the LFSR falls through to its hard-coded constant (lfsr129.v:88). The failure is silent and produces a fixed, publicly computable output rather than stalling. Note the asymmetry: with partityfilter_en cleared the same misconfiguration fails SAFE (digi_data_vld stays low, buf_cnt never reaches 256, the RNG simply never produces output) — so the parity path specifically converts a safe stall into a catastrophic silent success.

**Evidence.**
```systemverilog
rtl/modules/crypto_trng/rtl/digitalization.v:81-86:
assign digi_data_out_tmp_pre[0]           = partityfilter_en ? (^data_samp[ANA_NUM-1:0]): data_samp[0];
assign digi_data_out_tmp_pre[ANA_NUM-1:1] = partityfilter_en ? 'h0                      : data_samp[ANA_NUM-1:1];
assign digi_data_vld_tmp_pre[0]           = (digi_cnt==ANA_NUM) ? 1'b0:
			                     clk_ana_pos[0]     ? (partityfilter_en ? 1'b1 : ana_vld_sys[0])          : digi_data_vld_tmp[0];
assign digi_data_vld_tmp_pre[ANA_NUM-1:1] = (digi_cnt==ANA_NUM) ?  'h0:
			                     clk_ana_pos[0]     ? (partityfilter_en ?  'h0 : ana_vld_sys[ANA_NUM-1:1]): digi_data_vld_tmp[ANA_NUM-1:1];

rtl/modules/crypto_trng/rtl/digitalization.v:61 (a channel with ana_vld==0 freezes at its last value):
        assign data_samp_pre[i]=ana_vld[i]?ana_data[i]:data_samp[i];

rtl/modules/crypto_trng/rtl/digitalization.v:76 (the enable term that the parity path bypasses):
	assign ana_vld_sys[i]= clk_ana_pos[i]  & ana_en[i] & ana_vld[i];

rtl/modules/crypto_top/rtl/trng.sv:109,132 (ana_en/ana_vld come from an apb_cr with default IV='0):
    apb_cr #(.A('h04), .DW(16)  )     sfr_crana       (.cr(cr_ana), .prdata32(),.*);
    assign { cr_anaen[7:0], cr_anavld[7:0] } = cr_ana ;

rtl/modules/crypto_trng/rtl/data_buf.v:64-65 (buf_cnt counts 'valid' bits with no quality check):
assign buf_cnt_pre= trng_drng_sel_chg|postprocess_opt_chg|post_read|(buf_read  & (buf_addr==3'd7)) ? 9'h0 :
	          ((~trng_drng_sel)&digi_data_vld&(buf_cnt<9'd256))?(buf_cnt+1'b1):buf_cnt;
```

**Preconditions.** cr_pfilter_en set (the intended de-biasing configuration) together with cr_ana at or driven to zero. For the active variant, bus write access to 0x4002_E004 (T1), unrestricted while scemode==0.

**Attack scenario.** Attack variant (T1): 1. An unprivileged task writes 0x4002_E004 (sfr_crana) with 0x0000, clearing every channel's ana_en and ana_vld. This is permitted because trng.sv:52 hardwires sfrlock to 0 and, while scemode==0, sce_sec.sv:72 leaves the SCE APB page ungated. 2. It ensures cr_pfilter_en is set in sfr_pp (0x4002_E008) — or simply waits, if firmware already set it, which is the configuration a designer would choose since the parity filter is the intended de-biasing mode. 3. Every data_samp[i] now freezes (digitalization.v:61) while digi_data_vld keeps pulsing (line 84), so the digitizer emits a constant bit stream that the rest of the block accepts as valid. 4. The victim's key generation proceeds normally: buf_cnt reaches 256 (data_buf.v:64), buf_ready asserts, the LFSR is seeded with the constant, the zero-state guard reloads 129'h1_A39A8864_5DF3BECE_074EC5D3_BAF39D18, and the output word is the fixed sequence the attacker computed offline. 5. The victim's key is known. Firmware-error variant (no attacker): boot code writes cr_src to start the oscillators and writes cr_postproc with cr_pfilter_en=1, but omits or mis-orders the cr_crana write; the part ships and every unit generates the same key material, with no error indication anywhere — healthtest_err would flag it but gates nothing, and `err`/`intr` are tied to 0 at trng.sv:283-284.

**Mitigation.** RTL: qualify the parity path with the channel enables — the XOR must be `^(data_samp & ana_en)` and digi_data_vld in parity mode must be `clk_ana_pos[0] & (|(ana_en & ana_vld))` rather than a literal 1'b1, so a fully disabled source produces no valid bits and the pipeline stalls safely instead of emitting constants. Additionally, refuse to assert buf_ready on an all-zero or all-ones 256-bit accumulation, and require the startup health test to pass before the first buf_ready. Firmware workaround on fabricated silicon: (1) boot code must write sfr_crana (0x4002_E004) with all eight ana_en and ana_vld bits set BEFORE writing cr_pfilter_en, and must read the register back to confirm; (2) re-verify sfr_crana immediately before and after every key draw, since the register has no lock; (3) enable the health test and check sr_hlthtest_errcnt in sr_rng (0x4002_E010) across each draw; (4) as a defence in depth, compare the first generated word against the known constant sequence and hard-fault on a match.

**Verification.** Independently confirmed by a second reviewer. digitalization.v:81-86 matches the quote verbatim; line 84 does substitute a literal 1'b1 for ana_vld_sys[0] when partityfilter_en is set, bypassing the `clk_ana_pos[i] & ana_en[i] & ana_vld[i]` qualifier built at line 76. Line 61 `assign data_samp_pre[i]=ana_vld[i]?ana_data[i]:data_samp[i];` matches and does freeze a channel with ana_vld==0 at its last value (reset 0 per line 57). trng.sv:109 and :132 confirm ana_en/ana_vld come from cr_ana, an apb_cr with IV='0. I verified the fail-safe direction the finding claims: with partityfilter_en cleared, digi_data_vld_tmp_pre[0] takes ana_vld_sys[0], which is 0 when ana_en/ana_vld are 0, so digi_data_vld (line 126) never asserts, buf_cnt never reaches 256 (data_buf.v:64-65) and buf_ready never asserts (data_buf.v:100-101) -- the pipeline stalls safely. The parity path genuinely converts that safe stall into a silent stream of constant 'valid' bits, and data_buf.v:64 has no quality check, so the downstream conditioner cannot distinguish it. Combined with lfsr129.v:88 the result is the fixed known sequence as described.

**Corrections applied by the verifier.** Severity reduced from high to medium, and one sub-claim is overstated. (1) Overstated: 'channels the software believes it disabled still contribute' -- true that line 81 XORs all eight data_samp bits without masking by ana_en, but a disabled channel's sample is frozen at a constant (line 61), and XORing a constant into a parity is an entropy-preserving bijection. It removes no entropy from the live channels and is not itself a defect; the report should drop this and keep only the validity-forcing claim, which is the real bug. (2) The scenario needs one precondition the finding does not state: clk_ana_pos[0] must still pulse, which requires the LF ring oscillators to be running, i.e. cr_src's rnglf_en set (trng.sv:131,189,194-206). At full reset (cr_src=0) the oscillators are off and nothing pulses. So the exploitable window is 'oscillators enabled via cr_src, parity filter enabled, cr_ana zero', which is a narrower and more firmware-order-dependent configuration than 'the reset default'. (3) The fail-safe/fail-open asymmetry the finding identifies is correct and is the strongest part of it.

---

<a id="bao-049"></a>

### BAO-049 — apb_buf address decode is 32 bytes wide, aliasing the raw-entropy/seed buffer on top of the personalization-string and additional-input registers at 0x20/0x24/0x28

**Severity: Medium**

**Location:** `rtl/modules/crypto_top/rtl/trng.sv:432`

*Surfaced by the independent verifier, not the original domain reviewer.*

**Description.** apb_buf decodes only paddr[11:5], so a 32-byte block, but it is instantiated at A=12'h30. 12'h30[11:5] == 7'h01, which is the block spanning 0x20-0x3F. sfr_buf therefore claims sixteen word addresses, three of which are already occupied by apb_shfin instances: sfr_drpsz at 0x20, sfr_drgen at 0x24 and sfr_drreseed at 0x28 (trng.sv:275-277). apb_shfin decodes exactly (trng.sv:401) so those registers still work, but every APB access to them ALSO asserts buf_read/buf_write and steps the free-running buf_addr (trng.sv:439-441). Three consequences. (a) The raw entropy accumulator is readable at 0x20-0x2C as well as 0x30-0x3C (trng.sv:443), widening the leak reported in the 'raw entropy readable' finding to addresses firmware treats as write-only. (b) A firmware read-back of the personalization-string address silently destroys accumulated entropy whenever the free-running buf_addr happens to be 7, because data_buf.v:64 and :100 clear buf_cnt and buf_ready on `buf_read & (buf_addr==3'd7)`. (c) Worst case, in DRNG mode (cr_drng_en=1) the eight writes that load the 256-bit personalization string are simultaneously eight buf_write operations (data_buf.v:68-77) that overwrite buf_data with those same words, and since eight consecutive writes step buf_addr through all eight values, exactly one of them lands on buf_addr==3'd7 and asserts buf_ready (data_buf.v:101). The CTR_DRBG then reseeds from `K0 ^ buf_data[255:128] ^ personalization_string[255:128]` (ctr_aes.v:163) where buf_data is now a rotation of personalization_string itself, so the seed carries zero entropy; on the aligned rotation the two terms cancel exactly and the DRBG's initial key is the compile-time constant K0 = 128'h58e2fccefa7e3061367f1d57a4e7455a (ctr_aes.v:59) with counter M0+1.

**Evidence.**
```systemverilog
rtl/modules/crypto_top/rtl/trng.sv:432 (decode ignores paddr[4:2], so the window is 0x20-0x3F, not 0x30-0x4C):
    assign sfrsel = ( apbs.paddr[AW-1:BAW+2] == A[AW-1:BAW+2] );

rtl/modules/crypto_top/rtl/trng.sv:275-278 (the aliased instances):
    apb_shfin #(.A(12'h20), .DW(32), .REVY(1), .SFRCNT(8)) sfr_drpsz     (.dr(dr_psz_str),.*);
    apb_shfin #(.A(12'h24), .DW(32), .REVY(1), .SFRCNT(8)) sfr_drgen     (.dr(dr_gen_dat),.*);
    apb_shfin #(.A(12'h28), .DW(32), .REVY(1), .SFRCNT(8)) sfr_drreseed  (.dr(dr_gen_reseed),.*);
    apb_buf  #(.BAW(3), .A(12'h30), .DW(32) ) sfr_buf (.prdata32(),.*);

rtl/modules/crypto_top/rtl/trng.sv:439-443 (any access in the block steps buf_addr and drives the buffer):
    `theregrn( buf_addr ) <= buf_addr + buf_write + buf_read;
    assign buf_write = sfrsel & apbwr;
    assign buf_read = sfrsel & apbrd;
    assign buf_datain = apbs.pwdata;
    assign prdata32 = sfrsel ? buf_dataout : '0;

rtl/modules/crypto_trng/rtl/data_buf.v:100-101 (a write landing on buf_addr==7 declares the seed ready):
assign buf_ready_pre= (trng_drng_sel_chg|postprocess_opt_chg|(buf_read  & (buf_addr==3'd7))|post_read)? 1'b0: 
		      ((trng_drng_sel & buf_write & (buf_addr==3'd7))|(~trng_drng_sel &(buf_cnt>=9'd256)))? 1'b1:

rtl/modules/crypto_trng/rtl/ctr_aes.v:59,163 (the seed the clobbered buffer feeds):
parameter K0    =128'h58e2fccefa7e3061367f1d57a4e7455a;
assign aes_key_pre    =((ctr_state==IDLE  )&(ctr_state_nxt==RESEED)) ? K0                   ^buf_data[255:128]^personalization_string[255:128]:
```

**Attack scenario.** Firmware configures the DRBG in the documented order: set cr_drng_en / cr_postproc_opt=2 at 0x4002_E008, then write the 256-bit personalization string as eight words to 0x4002_E020. Because sfr_buf also decodes 0x20, those eight writes land in buf_data as well, and the one that coincides with buf_addr==3'd7 sets buf_ready. ctr_aes leaves IDLE into RESEED on the next cycle (ctr_aes.v:92-93) and seeds itself from K0 ^ buf_data[255:128] ^ personalization_string[255:128]. buf_data is now a rotation of the personalization string, so the seed is a value the attacker can compute from the personalization string alone -- and on the aligned rotation the XOR cancels and the initial key is the fixed constant K0. Every subsequent DRBG output is then computable offline. A second, unprivileged-attacker variant: a task with SCE access polls 0x4002_E020 in a loop; each read steps buf_addr, and one read in eight clears buf_cnt/buf_ready, so the victim's TRNG never accumulates 256 entropy bits and never completes a draw -- a denial of key generation from an address firmware does not associate with the entropy buffer at all.

**Verification.** No independent verdict recorded for this entry.

---

<a id="bao-050"></a>

### BAO-050 — Memory-BIST port hands full read/write control of every SRAM — including the ReRAM access-control RAM and AO SRAM — to the JTAG BIST controller, with no zeroization on test-mode entry

**Severity: Medium** | CWE-1244 Internal Asset Exposed to Unsafe Debug Access Level or State | Threat actor: T2 (physical), T4 (reset/power control) | Confidence: High

**Location:** `rtl/modules/bio_bdma/rtl/ram_1rw_s.sv:128`

**Description.** `rbspmux` is instantiated in front of every RAM macro in the SoC (cryptoram.sv:146-164 for SCERAM/HRAM/ARAM/PRAM/ALURAM, rrc.sv:405-422 for the ACRAM, aoram.sv, ifram.sv, tcmram.sv, core_srambank, bioram, udcmem). When `cmsbist` is asserted it multiplexes the *entire* macro control set — clock, chip-enable, global write-enable, per-bit write-enable, address and write data — from the `rbif` bus, and returns the macro's read data on `rbs.ramrdata`. This is not a signature-only BIST wrapper: it is unrestricted random-access read and write. `cmsbist` is `cmstest` (soc_top.sv:397), which per Finding 1 is selected by two external pads, and the BIST TAP is released by the same signal (pad_frame_arm.sv:244-246). Critically, entering BIST/TEST mode triggers no zeroization of any kind. The only wipe machinery in the design is the SCE's `sceramclr` (sce_sec.sv:87), and it (a) is confined to the SCE's own RAMs, (b) skips the RNGA/RNGB pools (sce.sv:417 `.clrend(scedma_pkg::SEGADDR_RNGA-1)`), and (c) is not connected to `cmstest`, `cmsbist` or any tamper input. Nothing at all clears the ReRAM ACRAM (which holds the per-key-slot owner/permission descriptors that rrc.sv:712-726 uses to gate ReRAM key reads), the CM7 ITCM/DTCM, the core SRAM banks, IFRAM0/1, the BIO RAM, or the always-on SRAM — and the AO SRAM contents survive every reset short of a battery removal (ao_top.sv:248-266, `.ret1n(1'b1)`). No memory in the SoC is scrambled (cryptoram.sv:112-113 `.scmben('0), .scmbkey('0)`), so what BIST reads back is plaintext.

**Evidence.**
```systemverilog
rtl/modules/bio_bdma/rtl/ram_1rw_s.sv:125-132
    logic rb_clk_undft; CLKCELL_MUX2 c1 (.A(clk), .B(rbs.ramclk), .S(cmsbist), .Z(rb_clk_undft));
    assign rb_clk = (TCM==1'b1)?rb_clk_undft : (cmsatpg ? 1'b0 : rb_clk_undft);
    assign rb_cen  = cmsatpg ? '1 : undft_cen  ; assign undft_cen  = cmsbist ? rbs.ramcen   : cen  ;
    assign rb_gwen = cmsatpg ? '1 : undft_gwen ; assign undft_gwen = cmsbist ? rbs.ramgwen  : gwen ;
    assign rb_wen  = cmsatpg ? '1 : undft_wen  ; assign undft_wen  = cmsbist ? rbs.ramwen   : wen  ;
    assign rb_a    = cmsatpg ? '1 : undft_a    ; assign undft_a    = cmsbist ? rbs.ramaddr  : a    ;
    assign rb_d    = cmsatpg ? '1 : undft_d    ; assign undft_d    = cmsbist ? rbs.ramwdata : d    ;

rtl/modules/bio_bdma/rtl/ram_1rw_s.sv:140
    assign rbs.ramrdata = cmsatpg ? undft_q : rb_q;

rtl/modules/rrc/rtl/rrc.sv:404-412  (the ReRAM access-control RAM sits behind the same mux)
    rbspmux #(.AW(11),.DW(64))rbmux(
         .cmsatpg,
         .cmsbist,
         .rbs         (rbs),
         .q(acram_rdata),
         .clk(acram_clk),
         .cen(acram_cs),
         .gwen(acram_wr),
         .a(acram_addr),

rtl/asic_top/rtl/soc_top.sv:397
    assign cmsbist = cmstest;

rtl/modules/crypto_top/rtl/cryptoram.sv:112-113  (no scrambling on any crypto RAM)
        .scmben('0),
        .scmbkey('0),
```

**Preconditions.** Physical pin access (T2) plus the ability to reset the part (T4). Requires Finding 1 (or any other route to cmstest=1). Exploiting step 4/5 additionally requires the raw-access instruction set of the closed-source `rbist` core; the RTL guarantees the datapath is present and unrestricted, but the command encoding is not in this repo.

**Attack scenario.** 1. Attacker obtains a running device that has just performed a secure operation, so software copies of key material, unwrapped secrets and the ReRAM ACRAM image are resident in core SRAM / TCM / AO SRAM / ACRAM. 2. Attacker pulses PAD_XRSTn with WMS0=WMS1=1 (Finding 1) to enter CMS_VRGN. SRAM contents are not destroyed by reset — no RTL path clears core_srambank, ITCM, DTCM, IFRAM, aoram, bioram, udcmem or the RRC ACRAM on any reset, and none of them is scrambled. 3. `cmsbist` is now 1, so for every RAM in the SoC, rbspmux lines 125-132 route the macro's clock, cen, gwen, wen, address and write data from the `rbif` bus, and line 140 returns the macro read data to the BIST controller. 4. The attacker drives the released BIST TAP (jtagrb, pad_frame_arm.sv:243-246, TDO on PB3 via pad_frame_arm.sv:263) with a read-address sequence and shifts out the contents of rbif_ram32kx72 / rbif_ram8kx72 / rbif_dtcm8kx36 / rbif_itcm32kx18 / rbif_aoram1kx36 / rbif_acram2kx64, recovering plaintext secrets that were never zeroized. 5. Alternatively the attacker WRITES the ACRAM through the same port: setting a key slot's `userid_k[7:4]` field to 0 makes rrc.sv:717's trailing `& (userid_k[7:4] != 4'h0)` term false, disabling the key-slot access check entirely for that slot, after which normal software can read the ReRAM key slot over the ordinary bus.

**Mitigation.** RTL: qualify `cmsbist` with a non-volatile lifecycle bit rather than a pad-derived mode, and force a hardware zeroization sweep of every RAM (not just SCE RAMs) as an unconditional precondition of asserting cmsbist/cmsatpg — hold the BIST enable off until a wipe-done flag from every RAM's clear FSM is asserted. Wire the tamper/mesh/sensor outputs into `sceramclr` and into an equivalent clear for the ACRAM, TCM and AO RAM. Enable the memory scrambler that is already plumbed but tied off (`.scmben('0), .scmbkey('0)` at cryptoram.sv:112-113, aoram.sv:95, ifram.sv:82, cm7sys_tcm.sv:116-117, soc_coresub.sv:721,739). Silicon workaround: firmware must explicitly overwrite every buffer that has held key material — including stack and heap in SRAM/TCM, the AO SRAM and aobureg — immediately after use, and must not rely on reset to clear them; there is no firmware action that can prevent the BIST port itself from being enabled.

**Verification.** Verified as written; exploitability not fully established. The RTL evidence is accurate and I reproduced all of it. ram_1rw_s.sv:125-132 and :140 are verbatim correct. I verified rbspmux is real design RTL, not a sim-only stub: it is defined exactly once (ram_1rw_s.sv:94) and instantiated by rrc.sv:404 (ACRAM), cryptoram.sv:146, aoram.sv, ifram.sv, tcmram.sv, core_srambank.try8k.sv and cryptoram_verilate.sv. cryptoram.sv:112-113 `.scmben('0), .scmbkey('0)` and aoram.sv:95 `.scmben(1'b0)` confirm no scrambling. I grepped every consumer of cmstest/cmsbist repo-wide: soc_top.sv:397/598/769/868/907 and pad_frame_arm.sv:233-269 — there is indeed no RAM-clear, key-zeroize or tamper hook anywhere on the test-mode-entry path. Also note that clkbist is NOT gated by cmsbist (sysctrl.sv:373-378 mux clkbist only against clkocc on cmsatpg), so the BIST controller is clocked during functional operation too. The fail-open amplifier the finder cites is real: rrc.sv:717 does end `...) & data_op & keysel & (userid_k[7:4] != 4'h0);` with userid_k = keycfg[23:16] = acram_rdata bits (rrc.sv:696), so an all-zero ACRAM descriptor does disable the whole key-slot check. Conclusion: the unrestricted BIST datapath and the absence of any zeroization gate are real and worth reporting; the end-to-end key-extraction story is not proven.

**Corrections applied by the verifier.** The exploit chain is stated as 'critical' on the strength of Finding 1, which I refuted; without a demonstrated way to reach cmsbist=1 on a fielded part, this is a defence-in-depth gap, not a demonstrated break. Also, the read-back step is unverifiable from this repo: the BIST controller itself is redacted — rbist_inc.sv:38-83 `include`s rbist.sv and ~50 Tessent MBIST files that are absent (rtl/modules/rbist/rtl/ contains only rbist_wrp.sv), so `rbist rbcore(.*)` (rbist_wrp.sv:408) is a black box. Standard Tessent MemoryBIST does not expose an arbitrary read port over JTAG; it exposes go/no-go and failing-address/bitmap diagnostics. The WRITE half of the claim is on firmer ground than the READ half.

---

<a id="bao-051"></a>

### BAO-051 — RAM margin-trim registers at 0x40045000 are unlocked and unprivileged, giving unprivileged software a fault-injection primitive against the SCE key RAM and the ReRAM access-control RAM

**Severity: Medium** | CWE-1233 Security-Sensitive Hardware Controls with Missing Lock Bit Protection | Threat actor: T1 (unprivileged software on either CPU) — no physical access required | Confidence: Medium

**Location:** `rtl/modules/rbist/rtl/rbist_wrp.sv:161`

**Description.** `rbist_wrp` exposes a 24-bit APB control register that selects one of the 28 RAM groups and writes its 16-bit timing-margin trim word. The module hard-ties its own lock signal to zero, so `apb_sfr`'s write gate (`assign apbwr = ~sfrlock & apbslave.psel & apbslave.penable & apbslave.pwrite;`, apb_sfr.sv:333) is permanently open. The register sits on apbsys[5] (soc_top.sv:968) i.e. 0x40045000 (confirmed by the generated header, bao1x_peri.h:3259 and doc/rbist_wrp.rst), which is in the apb1-system window 0x40040000-0x4004FFFF. No slave in this SoC consumes `pprot`/`hprot`, and there is no coreuser check anywhere on this path, so any bus master that can reach the peripheral bus — CM7 AHB-P (hauser=0x8), Vex AHB-P (0xD), the MDMA (0x7) and the BIO/BDMA peripheral master (0x0) — can write it from unprivileged code. The trim word is not cosmetic: the packed `t_trm` struct is {ema[15:13], emab[12:10], emaw[9:8], emas[7], wabl[6], wablm[5:3], rawl[2], rawlm[1:0]} and the vendored macro-instantiation macro maps exactly those bit ranges onto the Artisan macro's extra-margin-adjustment, write-assist and read-assist pins. Group 9 is the SCE unified crypto RAM (sce_sceram_10k, which holds SKEY/SCRT/AKEY/PKB), group 26 is the RRC ACRAM that holds the ReRAM key-slot access-control descriptors, and group 27 is the always-on SRAM. Detuning EMA/WABL/RAWL on a live macro is a standard, well-characterised way to induce read and write failures without any physical apparatus.

**Evidence.**
```systemverilog
rtl/modules/rbist/rtl/rbist_wrp.sv:158-161
    logic apbrd, apbwr;
    logic sfrlock;

    assign sfrlock = '0;

rtl/modules/rbist/rtl/rbist_wrp.sv:176-181
    apb_cr #(.A('h00), .DW(24))         sfrcr_trm    (.cr( trmcr    ), .prdata32(),.*);
    apb_sr #(.A('h04), .DW(24))         sfrsr_trm    (.sr( trmsr    ), .prdata32(),.*);
    apb_ar #(.A('h08), .AR(32'h5a))     sfrar_trm    (.ar( trmar    ),             .*);

    assign            { sfrtrmsel[7:0],  sfrtrmdat[15:0]      } = trmcr;

rtl/modules/rbist/rtl/rbist_wrp.sv:192-200
        for ( i = 0; i < 28 ; i++) begin: gtrm
            t_trm trmtmp;
            `theregfull( clksys, sysresetn, trmtmp , IV_trm[i] ) <=
                    sfrtrmset & ( sfrtrmsel == i )     ? sfrtrmdat[15:0] :
                    ipttrmset & ( ipttrmsel == 128+i ) ? ipttrmdat[15:0] :
                    nvrtrmset & nvrtrmvld[i]           ? nvrtrmdat[i][15:0] :
                                                         trmtmp;
            assign trmdat[i] = trmtmp;

rtl/modules/rbist/rtl/rbist_wrp.sv:104 and :121  (the targets)
    logic [15:0] trm_sce_sceram_10k ; assign trm_sce_sceram_10k = trmdat[9 ]; ...
    logic [15:0] trm_acram2kx64     ; assign trm_acram2kx64     = trmdat[26]; ...

rtl/modules/rbist/rtl/rbist_wrp.sv:71-80  (bit-field layout)
    typedef struct packed {
        bit [2:0]   ema;
        bit [2:0]   emab;
        bit [1:0]   emaw;
        bit         emas;
        bit         wabl;
        bit [2:0]   wablm;
        bit         rawl;
        bit [1:0]   rawlm;
    } t_trm;

rtl/modules/bio_bdma/rtl/ram_1rw_s.sv:84-92  (same bit ranges land on the macro's margin pins)
`define rf_sp_hde_inst_bio          \
         .ema         ( rbs.ramtrm[15:13] ), \
         .emaw        ( rbs.ramtrm[9:8]   ), \
         .emas        ( rbs.ramtrm[7]     ), \
         .wabl        ( rbs.ramtrm[6]     ), \
         .wablm       ( rbs.ramtrm[4:3]   ), \
         .rawl        ( rbs.ramtrm[2]     ), \
         .rawlm       ( rbs.ramtrm[1:0]   ), \

rtl/modules/amba/rtl/apb_sfr.sv:333
    assign apbwr = ~sfrlock & apbslave.psel & apbslave.penable & apbslave.pwrite;
```

**Preconditions.** Any code execution that can issue a store to 0x40045000/0x40045008 — i.e. unprivileged software on either CPU, or the BIO/BDMA peripheral master (which presents hauser=0). Confirmation of the final trm->ramtrm wire requires the closed-source `rbist` core (rbist_wrp.sv:408 `rbist rbcore(.*);`); the bit-field mapping between t_trm and the vendored macro-instantiation macro is exact, and the same trmdat path is fed by the production ReRAM IFR trim load (nvrtrmset/nvrtrmdat, rbist_wrp.sv:197), which establishes it as the real trim mechanism.

**Attack scenario.** 1. Unprivileged software running on either CPU writes 0x40045000 with {sfrtrmsel=26, sfrtrmdat=<aggressive margin>} to select the RRC ACRAM group and set an EMA/RAWL combination outside the qualified window; a write to 0x40045008 with 0x5a fires `sfrar_trm`, which the sync_pulse at rbist_wrp.sv:187 converts into `sfrtrmset`, latching the new trim into trmdat[26] (rbist_wrp.sv:194-198). There is no lock bit to stop this (line 161) and no privilege check on the APB. 2. Software then performs a ReRAM key-slot access at 0x603Fxxxx. The RRC reads the slot's access-control descriptor out of the now-detuned ACRAM (rrc.sv:404-424, rrc.sv:684-697). 3. A read failure that returns zeros for the descriptor makes `userid_k[7:4] == 4'h0`, and the whole key-access check in rrc.sv:712-717 is multiplied by the trailing term `& (userid_k[7:4] != 4'h0)` — so `key_access_error` becomes 0 and the read is permitted. rrc.sv:583 returns HRESP=OKAY and rrc.sv:555-558 delivers the key word instead of zeros. 4. The same primitive aimed at group 9 (sce_sceram_10k) or group 27 (aoram) corrupts SCE key/state words or AO-domain secrets, and aimed at group 7/6 (ITCM/DTCM) corrupts instruction memory of the other CPU — all from unprivileged software, with no physical access and no glitch equipment.

**Mitigation.** RTL: drive `sfrlock` from a sticky, boot-set lock bit (the pattern already used in aes.sv:135 and combohasha.sv:159, `theregrn( sfrlock ) <= optlock ? 1'b1 : mfsm_done ? '0 : sfrlock;`) so that the trim registers become read-only once the ReRAM IFR trim load completes; alternatively gate the register with a coreuser/boot-region check as the RRC CFG region is, and exclude the security-critical groups (9, 26, 27) from software-writable trim entirely. Silicon workaround: the earliest boot stage must relocate this peripheral out of reach — since no lock exists, the only firmware mitigation is to configure the CM7 MPU / Vex PMP to make 0x40045000-0x4004500C inaccessible to all non-boot code, and to keep the region blocked for the life of the boot. Note that the CM7 MPU configuration in daric_cfg_pkg.sv:117-127 is currently commented out, so this workaround requires firmware to program the MPU itself.

**Verification.** Independently confirmed by a second reviewer. Every load-bearing claim checks out. rbist_wrp.sv:158-161 is verbatim: `logic apbrd, apbwr; logic sfrlock; assign sfrlock = '0;`. apb_sfr.sv:333 `assign apbwr = ~sfrlock & apbslave.psel & apbslave.penable & apbslave.pwrite;` is verbatim, and apb_ar (apb_sfr.sv:234-261) passes `sfrlock|'0` to the same gate, so both the CR and the AR are permanently writable. Address: soc_top.sv:968-969 attaches rbist to apbsys[5]; apb_mux is instantiated with DECAW(4) (soc_top.sv:671) and decodes `paddrdec = apbslave.paddr[PAW-1:SAW]` (amba_components.sv:301), and the APB1-system window is 0x4004_0000-0x4005_0000 (daric_cfg_pkg.sv:51) => 0x40045000. Privilege: apbif (amba_interface_def.sv:365-395) carries pprot but no hauser/coreuser, and I found no slave in the tree that consumes pprot; the AHB `hauser` signal is not propagated into APB at all. So an unprivileged store from either CPU (or the BDMA peripheral master, bio_bdma.sv:1579 `assign ahbm.hauser = '0;`) reaches it. Targets: rbist_wrp.sv:104 (trmdat[9] = sce_sceram_10k), :121 (trmdat[26] = acram2kx64), :122 (trmdat[27] = aoram1kx36). Update logic rbist_wrp.sv:194-198 gives the APB path the HIGHEST priority, above the ReRAM-provisioned trim load (nvrtrmset), and the value persists until sysresetn. The trim word reaches the macro's read/write-assist pins unconditionally in functional mode (ram_1rw_s.sv:84-92, `rf_sp_hde_inst_bio`). The downstream fail-open at rrc.sv:717 that the finder relies on for the ACRAM scenario is real and I read it. This is a genuine missing-lock-bit defect (CWE-1233) on a security-relevant control.

**Corrections applied by the verifier.** Two small inaccuracies that do not change the conclusion. (a) The t_trm bit layout is right but the macro mapping is not identical: t_trm puts wablm at [5:3] while the vendored instantiation macro connects `.wablm ( rbs.ramtrm[4:3] )` (ram_1rw_s.sv:89) — 2 bits, not 3 — and emab[12:10] is not connected at all in that macro. (b) The last hop trmdat -> rbif_*.ramtrm is inside the redacted `rbist` core (rbist_wrp.sv:408; rtl/modules/rbist/rtl/ contains only rbist_wrp.sv), so it is inferred from port-name matching, not read. Severity lowered from high to medium because the resulting RAM failure is probabilistic and PVT-dependent, whereas the register write itself is certain.

---

<a id="bao-052"></a>

### BAO-052 — CMS data register powers up holding the VIRGIN pattern

**Severity: Medium** | CWE-1221 Incorrect Register Defaults | Threat actor: T2/T4 | Confidence: High

**Location:** `rtl/modules/sysctrl/rtl/cms.sv:107`

*Introduced at the synthesis stage with no structured reviewer record. Read against the RTL
directly during assembly by the orchestrating model; evidence below is quoted from source.*

**Description.** The chip-mode-select data register's **reset value is the VIRGIN-mode pattern**. `cmsdatareg` is declared with `CMSDAT_VRGNMODE` as its reset constant, so out of every reset - and for the entire window before ReRAM supplies a lifecycle value and asserts `cmsdatavld` - the register holds the least-restrictive lifecycle state rather than a fail-closed one. A separate `cmsdataregvld` flag tracks whether a real value has arrived, so the exposure depends on every consumer honouring that flag.

**Evidence.**
```systemverilog
// cms.sv:107 - reset value is the VIRGIN pattern, not a fail-closed default
    `theregfull(clk, resetn, cmsdatareg, cms_pkg::CMSDAT_VRGNMODE) <= cmsdatavld ? cmsdata : cmsdatareg;
    `theregrn( cmsdataregvld ) <= cmsdatavld ? 1'b1 :    cmsdataregvld;
```

**Attack scenario.** An attacker who can hold the chip in reset, brown it out, or prevent the ReRAM lifecycle read from completing leaves the mode register at VIRGIN. Any consumer that samples `cmsdatareg` without also qualifying on `cmsdataregvld` sees the most permissive lifecycle state. Security defaults should fail closed; this one fails open.

**Mitigation.** RTL: reset to the most restrictive lifecycle pattern, not the least. Firmware: no mitigation - this is a reset value in fabricated silicon.

**Verification.** Read against the RTL during report assembly by the orchestrating model.
Not independently reviewed, not adversarially tested, and not seen by a human.

---

<a id="bao-053"></a>

### BAO-053 — Anti-tamper mesh integrity check is a static, software-chosen DC level compared against the same software-readable register that drives it - no challenge-response, and the reset default drives all 64 mesh lines to constant 0

**Severity: Medium** | CWE-330 Use of Insufficiently Random Values | Threat actor: T2 (physical) for the replay; T1 for the disarm variant | Confidence: High

**Location:** `rtl/modules/sec/rtl/mesh.sv:68`

**Description.** The mesh has 64 lines (MESHLC=64) each with 32 sense points (MESHPC=32). Each line is driven by one bit of the software register `cr_mldrv` (mesh.sv:62), the sense point is registered (mesh.sv:67), and the integrity test is a direct equality against that very same drive register (mesh.sv:68).

There is no LFSR, no counter, no per-cycle toggling, no random challenge and no timing/propagation-delay measurement anywhere in the module. `cr_mldrv` is a plain APB control register that changes only when software writes it; between writes each mesh line carries a constant DC level. Worse, `cr_mldrv` is in the read-back OR list (mesh.sv:48-51 `assign apbx.prdata = '0 | sfr_mldrv.prdata32 | ...`), so the exact static level of every one of the 64 lines is readable at 0x4005_2000-0x4005_2004 by any bus master, with sfrlock hardwired to 0 (mesh.sv:46) and no coreuser/privilege check on the 0x4005_xxxx APB.

And the reset default is the worst case: `apb_cr` has default `IV=32'h0` (apb_sfr.sv:81), and sfr_mldrv is instantiated without an IV override, so out of every core reset all 64 mesh lines are driven to constant logic 0 and every sense point is expected to read 0. `cr_mlie` also resets to 0, which zeroes `apterr` entirely (mesh.sv:68), so the mesh reports nothing at all until firmware arms it.

A mesh whose expected value is a constant that the adversary can either read out of a register or simply guess (all-zero at reset) provides no protection against the standard attack: cut/delaminate the mesh and tie the sense side of each line to the expected level.

**Evidence.**
```systemverilog
mesh.sv:46
    `theregrn( sfrlock ) <= '0;

mesh.sv:48-53
    assign apbx.prdata = '0
                        | sfr_mldrv.prdata32
                        | sfr_mlie.prdata32 | sfr_mlsr.prdata32
                        ;

    apb_cr #(.A('h00), .DW(32), .REVY(1), .SFRCNT(LC/32))  		sfr_mldrv   (.cr(cr_mldrv), .prdata32(),.*);

mesh.sv:61-68
		meshlinedrv ud(.A(mldrvin[i]),.Z(mldrv[i]));
		assign mldrvin[i] = (~cmsatpg) & cr_mldrv[i];
		assign t_mlie[i] = cmsatpg ? '0 : cr_mlie[i];
		for (genvar j = 0; j < PC; j++) begin: gp
			meshlinebuf ua(.A(mlapt[i][j]),.IE(t_mlie[i]),.Z(t_apt[i][j]));
			assign apt[i][j] = cmsatpg ? '0 : t_apt[i][j];
			`theregrn( aptreg[i][j] ) <= apt[i][j];
			assign apterr[i][j] = cr_mlie[i] & ( aptreg[i][j] != cr_mldrv[i] );

rtl/modules/amba/rtl/apb_sfr.sv:81  (default IV for apb_cr)
      parameter IV=32'h0,
```

**Preconditions.** For the replay: physical access to the die (T2). Reading cr_mldrv additionally needs any APB read to 0x4005_2000 (T1), but is unnecessary against a freshly-reset part since the default pattern is all-zero. For the disarm variant: any write to 0x4005_2010 (T1, or any AHB master on core_ahb32).

**Attack scenario.** Attacker (T2) decapsulates the package and needs to reach the die under the active mesh. Step 1: before or during the attack, read 0x4005_2000 and 0x4005_2004 over the APB - either with T1 software (no privilege check exists on this path: soc_top.sv:661-666 bridges coreahb_sec straight to the secsub APB, and secsub.sv:46 is a bare apb_mux) or, if the part has just been reset, skip this step entirely because `cr_mldrv` resets to 0 and every line is at constant 0. Step 2: the 64-bit value read back is the exact DC level held on every mesh line, and it does not change unless firmware writes the register. Step 3: cut the mesh anywhere to open a hole for probing/FIB, and short each severed sense-side line to the level named in `cr_mldrv[i]` (ground for the reset default). Because mesh.sv:68 only tests `aptreg[i][j] != cr_mldrv[i]`, every sense point still matches, `apterr` stays 0, `sr_mlsr` stays 0, and `irq` stays 0. The mesh is now transparent while the die is fully exposed for microprobing of the SCE key RAM buses or laser fault injection. A rotating pseudo-random pattern with propagation-delay checking - the standard construction - would make this replay impossible; none is present anywhere in the module.

Variant requiring no physical mesh work at all: write 0 to `cr_mlie` at 0x4005_2010 (reset value is already 0). mesh.sv:68 ANDs every error term with `cr_mlie[i]`, so the entire 64x32 detector array reports clean. There is no lock bit to prevent this and no way for hardware to notice.

**Mitigation.** RTL fix: drive the mesh from a hardware LFSR/PRNG reseeded from the TRNG rather than from a software register, and compare the sense point against a delayed copy of the *driven* pattern rather than against a static CR; the driving pattern must not be readable over the bus (remove sfr_mldrv.prdata32 from the prdata OR list, or make it write-only). Add propagation-delay checking so that a shorted or re-routed line fails timing. Add a real lock: replace `` `theregrn( sfrlock ) <= '0; `` with a set-once lock bit, and default cr_mlie to all-ones so the mesh is armed out of reset rather than disarmed.
Silicon workaround: firmware must write a nonzero, ideally per-boot-random, pattern to cr_mldrv (0x4005_2000/4) and 0xFFFF_FFFF to cr_mlie (0x4005_2010/14) very early in boot0, and should rewrite cr_mldrv with a fresh random value frequently (each rewrite forces the attacker to re-short every line to a new level in real time). Firmware must also poll cr_mlie/cr_mldrv for unexpected changes. This raises the bar but cannot make the mesh unpredictable to an attacker who can read the register, so key material should not be treated as mesh-protected.

**Verification.** Independently confirmed by a second reviewer. Every quoted line is verbatim correct. mesh.sv:46 `` `theregrn( sfrlock ) <= '0; ``; mesh.sv:48-51 puts sfr_mldrv.prdata32 in the read-back OR, so the drive pattern is bus-readable; mesh.sv:53 instantiates sfr_mldrv with no .IV, and apb_sfr.sv:81 `parameter IV=32'h0` is the default, so cr_mldrv resets to all-zero across LC=64 lines (daric_cfg_pkg.sv:203 MESHLC=64, :204 MESHPC=32); mesh.sv:68 `assign apterr[i][j] = cr_mlie[i] & ( aptreg[i][j] != cr_mldrv[i] );` is the entire integrity test. I read mesh.sv end to end (286 lines) — there is no LFSR, counter, TRNG tap or delay measurement anywhere; meshlines_2d (mesh.sv:132+) is a pure combinational chain, and the SIM disconnect model drives a cut point to (i+j)%2, confirming the design intent is a static level compare. cr_mlie also has no .IV, so it resets to 0 and mesh.sv:68 force-zeroes every error term until firmware arms it; mesh.sv:65 additionally gates the sense buffer with IE=cr_mlie.

No compensating control exists: sfrlock is a constant 0, and the APB path (soc_top.sv:661-666 -> soc_coresub.sv:646 ahb_thru) carries no privilege check, so the disarm variant (write 0 to cr_mlie at 0x4005_2010/14) is one unprivileged store.

Correction to the finder's emphasis: the 'attacker reads cr_mldrv over the APB' step is close to worthless as a lever — an attacker who has decapped far enough to short mesh lines can simply measure the DC level on the line itself. The substantive defect is that the expected value is a static DC level with no rotation and no propagation-delay check, plus the disarmed (cr_mlie=0) and all-zero (cr_mldrv=0) reset state. On that basis I set severity to medium rather than high: it is a genuine weakening of an anti-probing countermeasure, but exploitation requires full decap/FIB (T2) and many shipping meshes use static patterns.

---

<a id="bao-054"></a>

### BAO-054 — Glue chain (anti-decap/laser detector) is held in reset out of reset, its stimulus is a software register, and software can clear the latched tamper state at will

**Severity: Medium** | CWE-1233 Security-Sensitive Hardware Controls with Missing Lock Bit Protection | Threat actor: T1 to disarm, then T2 to exploit; T4 alone (watchdog/reset) for the passive variant | Confidence: High

**Location:** `rtl/modules/sec/rtl/gluechain.sv:58`

**Description.** The glue chain is 64 chains (GLCX=64) of 32 series `ip_gluecell` tamper cells (GLCY=32). Three separate software registers control it, all instantiated as plain `apb_cr` with no IV override, i.e. reset value 0, and all with `sfrlock` hardwired to 0 (gluechain.sv:42):

1. `gluerst` (sfr_gcrst, offset 0x10 for GCX=64 -> 0x4005_4010/14) is ANDed into the per-chain reset at gluechain.sv:58. Reset value 0 means `glueresetn[i] = 0` for all 64 chains, i.e. every glue cell is held in reset out of every core reset. Per the only available cell model (rtl/modules/model/rtl/gluecell.sv:32-34) `always@(negedge d2a_nrst) thereg <= 0;` and `assign a2d_glue_out = thereg | d2a_glue_in;` - with nrst held low the cell can never latch a tamper event.
2. `gluetest` (sfr_gctest, 0x4005_4018/1C) is fed directly into the head of every chain at gluechain.sv:55. Reset value 0, so even if the chain were out of reset the propagated value is 0 and `gluereg` can never set.
3. `cr_gcmask` (sfr_gcmask, 0x4005_4000/04) ANDs off the alarm per chain at gluechain.sv:56.

So the glue chain is completely inert until firmware writes all of gluerst and (per the model) gluetest, and the *only* consequence when it does fire is `` `theregrn( irq ) <= |gluereg; `` (gluechain.sv:69) - a maskable interrupt (see the separate finding on evc erren).

Separately, because `gluerst` is a live read/write CR rather than a one-way arm bit, writing 0 then 1 to 0x4005_4010 pulses `d2a_nrst` low on every cell, clearing any latched tamper. The design provides an explicit, unlocked, unprivileged "erase the tamper evidence" control.

Finally the module's `resetn` is `coreresetn` (secsub.sv:93 `.resetn` bound to secsub's `resetn`, which soc_top.sv:703 drives with `coreresetn`), so a watchdog reset or a write of 0x55AA to sysctrl `sfr_rcurst1` at 0x4004_0084 returns gluerst/gluetest/cr_gcmask to 0 and disarms the whole chain again.

**Evidence.**
```systemverilog
gluechain.sv:42
    `theregrn( sfrlock ) <= '0;

gluechain.sv:48-51
    apb_cr #(.A('h00*(GCX/32)), .DW(32), .SFRCNT(GCX/32) )  		sfr_gcmask    (.cr(cr_gcmask), .prdata32(),.*);
    apb_sr #(.A('h04*(GCX/32)), .DW(32), .SFRCNT(GCX/32) )  		sfr_gcsr      (.sr(gluereg),   .prdata32(),.*);
    apb_cr #(.A('h08*(GCX/32)), .DW(32), .SFRCNT(GCX/32) )       sfr_gcrst     (.cr(gluerst),   .prdata32(),.*);
    apb_cr #(.A('h0C*(GCX/32)), .DW(32), .SFRCNT(GCX/32) )       sfr_gctest    (.cr(gluetest),  .prdata32(),.*);

gluechain.sv:55-58
		assign gluenet[i][0] = cmsatpg ? '0 : gluetest[i];
        `theregfull( clksys, resetn, gluereg[i], '0 ) <= t_gluenet[i] & ~cr_gcmask[i];
        assign t_gluenet[i] = cmsatpg ? 0 : gluenet[i][GCY];
		assign glueresetn[i] = cmsatpg ? '0 : gluerst[i] & resetn;

gluechain.sv:69
	`theregrn( irq ) <= |gluereg;

rtl/modules/model/rtl/gluecell.sv:32-34
        bit thereg = 0;
        always@(negedge d2a_nrst) thereg <= 0;
        assign a2d_glue_out = thereg | d2a_glue_in;
```

**Preconditions.** For the disarm: any write access to 0x4005_4010 (unprivileged software on CM7 or Vex, or any AHB master reaching core_ahb32 - the 0x4005_xxxx APB has no hauser/coreuser/pprot filter, see soc_top.sv:661-666 and secsub.sv:46). For the passive variant: a warm core reset, which the attacker can induce via the watchdog or via 0x4004_0084. The polarity claim (chain-in-reset => no alarm) relies on the behavioral cell model, the only description of ip_gluecell in the repo.

**Attack scenario.** Step 1 (T1, one store). Unprivileged code on either CPU - or the BIO/BDMA peripheral AHB master, which drives hauser=0 and hits no coreuser check on this bus - writes 0x0000_0000 to 0x4005_4010 and 0x4005_4014. `gluerst` goes to 0, `glueresetn[i]` (gluechain.sv:58) goes to 0 for all 64 chains, every `ip_gluecell` is held in its reset state and `a2d_glue_out` collapses to the chain input, which is `gluetest` = 0. `gluereg` can no longer set; `irq` can no longer assert. There is no lock bit (gluechain.sv:42 ties sfrlock to constant 0), no privilege check, and no hardware record that the detector was disarmed.
Step 2 (T2). Attacker decapsulates the package and applies laser fault injection or UV/optical probing over the die. The glue cells that would have latched the event are in reset. No interrupt, no status bit, no reset, no key erase.
Step 3 (evidence removal). If any chain did latch before step 1, writing 0 then 1 to 0x4005_4010 pulses d2a_nrst on every cell and clears `thereg`, wiping the tamper record.

No-attacker-action variant: after any core reset - including one the attacker induces by simply letting the watchdog expire, since gluechain's resetn is coreresetn (soc_top.sv:703) - gluerst returns to 0 and the entire glue chain is disarmed until firmware re-arms it. The attack window is every boot.

**Mitigation.** RTL fix: make the glue chain armed out of reset (`.IV` all-ones on sfr_gcrst) rather than disarmed; make `gluerst` a one-way arm bit that can be set but not cleared until POR, or gate it behind a real sfrlock set at end of boot; latch `gluereg` as sticky-set in a domain that `gluerst` cannot clear so the tamper record survives a de-arm; drive the chain head from a hardware pattern generator rather than the software `gluetest` register; and route |gluereg to an autonomous zeroize/reset path instead of only `irq`.
Silicon workaround: boot0 must write 0xFFFF_FFFF to 0x4005_4010/14 (gluerst) and to 0x4005_4018/1C (gluetest) and 0x0000_0000 to 0x4005_4000/04 (gcmask) before any secret is loaded, and must re-verify these values on every secret-handling entry. Firmware should also snapshot gluereg (0x4005_4008/0C) into always-on backup registers (aobureg, 0x4006_xxxx, POR-only reset) so a de-arm cannot erase the evidence. This is defeated by anything that gets one 32-bit write before firmware notices.

**Verification.** Verified as written; exploitability not fully established. The RTL quotes are verbatim correct: gluechain.sv:42 `` `theregrn( sfrlock ) <= '0; ``; gluechain.sv:48-51 instantiates sfr_gcmask/sfr_gcsr/sfr_gcrst/sfr_gctest as plain apb_cr/apb_sr with no .IV (so gluerst, gluetest, cr_gcmask all reset to 0); gluechain.sv:58 `assign glueresetn[i] = cmsatpg ? '0 : gluerst[i] & resetn;`; gluechain.sv:69 `` `theregrn( irq ) <= |gluereg; ``. GLCX=64/GLCY=32 confirmed at daric_cfg_pkg.sv:212-213, and secsub.sv:93 binds gluechain's resetn to secsub's resetn = coreresetn (soc_top.sv:703). The register addresses the finder gives are right (SFRCNT=2 gives gcmask@0x00, gcsr@0x08, gcrst@0x10, gctest@0x18).

Two of the finder's mechanisms are wrong and must be corrected before this goes to a vendor:
(1) 'gluetest reset value 0, so even if the chain were out of reset the propagated value is 0 and gluereg can never set' is FALSE. The only cell description in the repo, rtl/modules/model/rtl/gluecell.sv:34, is `assign a2d_glue_out = thereg | d2a_glue_in;` — a tripped cell ORs itself into the chain regardless of the head stimulus. gluetest is a continuity self-test input, not a precondition for detection. Firmware does not need to write it.
(2) 'gluerst=0 holds every cell in reset so it can never latch' is an inference from the port name, not from the available model. gluecell.sv:33 is `always@(negedge d2a_nrst) thereg <= 0;` — it clears on the falling edge only; with nrst held low the random tamper process at gluecell.sv:37-46 still sets thereg and it still propagates. Whether the real analog cell holds its latch cleared while d2a_nrst is low is unverifiable from this repo. It is likely, which is why this is plausible rather than refuted, but the report must say so.

What IS solidly confirmed: gluereg is not sticky (gluechain.sv:56 `gluereg[i] <= t_gluenet[i] & ~cr_gcmask[i]` re-evaluates every clksys cycle) and the cells' only sticky element is clearable by pulsing gluerst — so an unprivileged 0-then-1 write to 0x4005_4010/14 erases the tamper record, with sfrlock constant 0 and no privilege check on the 0x4005_xxxx APB. cr_gcmask does reset to 0, i.e. unmasked, which the finder lists among the defects but is actually the safe default. Severity medium: the evidence-erasure control is real and unlocked, but the headline 'the detector is inert out of reset' is unproven from this RTL.

---

<a id="bao-055"></a>

### BAO-055 — Every tamper event terminates in a maskable interrupt whose enable register resets to zero; no tamper source triggers any autonomous reset or key zeroization

**Severity: Medium** | CWE-1320 Improper Protection for Outbound Error Messages and Alert Signals | Threat actor: T1 (mask) plus T2 (physical attack); the default state means T2 alone suffices | Confidence: High

**Location:** `rtl/asic_top/rtl/soc_top.sv:480`

**Description.** secsub aggregates the three detectors into a single 8-bit interrupt bundle and nothing else: `assign irq8 = {meshirq, sensorcirq, glcirq} | '0;` (secsub.sv:100). Tracing that forward, `irq8` becomes `secirq` (soc_top.sv:713) and is consumed in exactly two places: as ordinary event bits `ev[239:224]` (soc_top.sv:473) and as a single OR-reduced error bit `err[3] = |secirq` (soc_top.sv:480). In evc, the error bits produce the CM7 NMI, but only through a software enable mask: `assign cm7nmi = |(errin&erren);` (evc.sv:71), where `erren` is `apb_cr ... .IV(0)` at 0x4004_4084 with `assign sfrlock = '0;` (evc.sv:140,158).

Consequences:
1. Out of reset `erren == 0`, so mesh intrusion, glue-chain (laser/decap) detection, light detection and voltage-tamper all produce NO NMI. They are ordinary maskable interrupts only.
2. Any bus master can write 0 to 0x4004_4084 at any time to re-mask all of them; the register has no lock (evc.sv:140 hardwires sfrlock to 0) and the 0x4004_xxxx APB carries no coreuser/privilege check.
3. Because err[3] is `|secirq` - a single OR of all tamper sources - a single mask bit disables the NMI for mesh, glue chain, light and voltage tamper simultaneously.
4. There is NO hardware zeroization path from any tamper source. Grepping the whole design, the SCE crypto-RAM wipe has exactly two sources (`sce_sec.sv:85-87`: SCE reset release and the `ar_clrram` software action register); no mesh, glue-chain, light or voltage signal reaches it. The mesh and glue chain do not even reach a reset - only sensorc's `vdresetn` does (soc_top.sv:712), and that is itself masked off by default (see the cr_vdmask1 finding). So a confirmed physical intrusion through the active mesh, or a confirmed laser attack detected by the glue chain, results in *nothing at all* unless firmware is running, is trusted, has enabled the NMI, and chooses to act.
5. The whole response therefore depends on a CPU that the attacker is in the middle of faulting, on clocks the attacker controls, and on registers the attacker can write.

**Evidence.**
```systemverilog
secsub.sv:100
	assign irq8 = {meshirq, sensorcirq, glcirq} | '0;

soc_top.sv:473
    assign ev[239:224] = '0 | secirq[7:0];

soc_top.sv:480
    assign err[3] = |secirq;

evc.sv:71
    assign cm7nmi = |(errin&erren);

evc.sv:140
    assign sfrlock = '0;

evc.sv:157-158
apb_fr #(.A('h80), .DW(ERRCNT)                   )  sfr_cm7errfr  (.fr(errin),      .prdata32(),.*);
apb_cr #(.A('h84), .DW(ERRCNT), .IV(0)           )  sfr_cm7errcr  (.cr(erren),      .prdata32(),.*);

rtl/modules/crypto_top/rtl/sce_sec.sv:85-87  (the only two sources of the crypto-RAM wipe - no tamper input)
    `theregrn( initregs ) <= { initregs, 1'b1 };

    assign sceramclr = ( initregs == 4'h7 ) | ar_clrram ;
```

**Preconditions.** Either the reset default (erren=0, no action needed), or one 32-bit write to 0x4004_4084 by any master reaching the 0x4004_xxxx APB (CM7-P hauser=0x8, Vex-P 0xD, MDMA 0x7, BDMA-AHB 0x0 - none of which is filtered on this path).

**Attack scenario.** Attacker (T1) writes 0x0000_0000 to the EVC error-enable register at 0x4004_4084. `erren` is now 0, so evc.sv:71 `cm7nmi = |(errin & erren)` is permanently 0 for every tamper source. (This is also the state the part boots into: .IV(0).) The attacker additionally masks the ordinary interrupt via the EVC event-enable registers, or simply runs the attack while the CPU is halted through SWD or is in a sleep state.

Attacker (T2) then decapsulates and microprobes. The mesh trips: mesh.sv:76 sets `irq`, secsub.sv:100 sets secirq[2], soc_top.sv:480 sets err[3]. Because erren is 0, no NMI is raised. Because the mesh output is not connected to any reset or clear signal anywhere in the design, the SCE key RAM is not wiped, the ReRAM key slots are not locked, `truststate` is not cleared, and the SoC keeps running with all keys live while the die is open. The same applies to the glue chain (laser detection) and to the light detectors (`sr_ldsr`, sensorc.sv:105,115, which reach only `irq` and never touch `vdresetn`).

Even with a perfectly-behaved firmware that enables the NMI, the response is a software interrupt handler: the attacker's next fault injection can skip it, and stopping the CPU clock stops it entirely. There is no clock-independent or software-independent tamper response anywhere in this chip.

**Mitigation.** RTL fix: route the tamper condition (|secirq, or better each detector individually) into a dedicated hardware tamper-response block that (a) asserts an asynchronous, non-maskable reset of the SCE and (b) directly drives `sceramclr` / an equivalent key-RAM wipe and clears `truststate`, without any software enable and without requiring clksys - e.g. a self-timed erase driven from the always-on 32 kHz domain so that stopping the main clock cannot defeat it. Latch the tamper condition stickily in the AO/POR domain (like `aocmsuser` at ao_top.sv:144) so it survives every warm reset. Make the EVC error-enable for err[3] default to 1 and lockable.
Silicon workaround: boot0/boot1 must write 0x0000_00FF (or at minimum bit 3) to 0x4004_4084 before any key is loaded, and must re-verify it on every entry to a secret-handling routine; the NMI handler must immediately wipe SCERAM via the `ar_clrram` action register (write 0xA5 to 0x4002_801C) and force a system reset via 0x4004_0080. This is a software mitigation with all the weaknesses above - it does not survive a CPU halt, a clock stop, or a single successful fault on the handler.

**Verification.** Independently confirmed by a second reviewer. All five links of the chain check out verbatim. secsub.sv:100 `assign irq8 = {meshirq, sensorcirq, glcirq} | '0;` (3 bits zero-extended into an 8-bit bundle). soc_top.sv:473 `assign ev[239:224] = '0 | secirq[7:0];` and soc_top.sv:480 `assign err[3] = |secirq;`. evc.sv:71 `assign cm7nmi = |(errin&erren);`, evc.sv:140 `assign sfrlock = '0;`, evc.sv:158 `apb_cr #(.A('h84), .DW(ERRCNT), .IV(0)) sfr_cm7errcr (.cr(erren), ...)`. And the zeroization claim holds: I grepped sceramclr across the whole tree and its sole assignment is sce_sec.sv:87 `assign sceramclr = ( initregs == 4'h7 ) | ar_clrram ;` — SCE reset release plus a software action register, with no mesh/glue/light/vd input. Nothing else drives it (sce.sv:291/424/449/489/515/556 are all consumers). The mesh and glue chain outputs terminate at secirq only; they reach no reset, no clear, no lock.

One compensating control the finder missed, which I checked: evc.sv:157 `apb_fr #(.A('h80), .DW(ERRCNT)) sfr_cm7errfr (.fr(errin), ...)` is a sticky flag register (apb_sfr.sv:191 FRMASK=32'hffff_ffff, i.e. set-on-input / write-1-to-clear), so a one-cycle secirq pulse IS latched at 0x4004_4080 and survives for firmware to poll even with erren=0. That blunts point 1: the event is recorded, only the NMI is suppressed. It does not touch points 2-4.

I am correcting high to medium. Every sub-claim is factually right, but an interrupt-enable register that resets to 0 is the normal contract for an event controller, the event is still recorded stickily, and the substantive part of the finding is architectural — the absence of any autonomous, software-independent zeroize/reset path from mesh or glue-chain intrusion, plus the missing lock on erren. That is a real hardening gap worth reporting, but it is not an access-control bypass.

---

<a id="bao-056"></a>

### BAO-056 — Voltage-detector enable and test registers let any unprivileged bus master blind all six voltage-tamper detectors with one store, defeating the reset response even when cr_vdmask1 is correctly armed

**Severity: Medium**

**Location:** `rtl/modules/sec/rtl/sensorc.sv:78`

*Surfaced by the independent verifier, not the original domain reviewer.*

**Description.** sensorc exposes the analog voltage detectors' enable and self-test pins as two ordinary, unlocked APB control registers. sfr_vdip_ena (offset 0x40 -> 0x4005_3040) drives the VD09ENA/VD25ENA/VD33ENA analog enables, and sfr_vdip_test (offset 0x44 -> 0x4005_3044) drives VD09TL/TH, VD25TL/TH, VD33TL/TH. Both are plain apb_cr with sfrlock hardwired to 0 (sensorc.sv:57) on the 0x4005_xxxx APB, which soc_top.sv:661-666 bridges from coreahb_sec with no hauser/coreuser/pprot check (soc_coresub.sv:646 is a bare `ahb_thru`). The vendor's own PMU behavioural model shows what those pins do: with ENA low the detector output is forced to the *healthy* level, and with the T pin high it is likewise forced to the healthy level. Since sensorc treats vd=1 as healthy (sensorc.sv:90 resets vds to '1, sensorc.sv:98 `vdflag[i] = (cr_vdcfg[i]==0) ? ~vd[i] : vdreg[i]`), either register gives a complete, silent blinding of all voltage tamper detection: vdflag can never set, so sr_vdsr, the sticky sfr_vdfr flag at 0x4005_300C, the interrupt and vdresetn all stay quiet. This is strictly more powerful than the cr_vdmask1 mask the original reviewer focused on, because it survives correct firmware arming of cr_vdmask1 and leaves the status registers reading clean rather than merely masked. Note also that a self-test control which can only force the NON-alarming state is useless as a self-test and useful only as a bypass.

**Evidence.**
```systemverilog
rtl/modules/sec/rtl/sensorc.sv:78-79
    apb_cr #(.A('h40), .DW(VDC/2+2), .IV({2'h0,{VDC/2{1'b1}}}) ) sfr_vdip_ena     (.cr(vdena),   .prdata32(),.*);
    apb_cr #(.A('h44), .DW(VDC) )           sfr_vdip_test    (.cr(vdtst),   .prdata32(),.*);

rtl/modules/sec/rtl/sensorc.sv:57
    `theregrn( sfrlock ) <= '0;

rtl/asic_top/rtl/soc_top.sv:688-690
    assign  { vd_VD09_CFG[1:0],VD09ENA,VD25ENA,VD33ENA } = sensor_vdena;
    assign  { VD09TL,VD09TH,VD25TL,VD25TH,VD33TL,VD33TH } = sensor_vdtst ;
    assign  sensor_vd = { VD09L,VD09H,VD25L,VD25H,VD33L,VD33H };

rtl/asic_top/rtl/pmu_top.sv:281-287
    always@(*)begin
        reg_VD09L = VDD25 & VDD85A & ( ~D2A_VDD85D_VD09ENA ? '1 : D2A_VDD85D_VD09TL ? '1 : VDD85D );
        reg_VD09H = VDD25 & VDD85A & ( ~D2A_VDD85D_VD09ENA ? '1 : D2A_VDD85D_VD09TH ? '1 : VDD85D );
        reg_VD25L = VDD25 & VDD85A & ( ~D2A_VDD85D_VD25ENA ? '1 : D2A_VDD85D_VD25TL ? '1 : VDD25 );
        reg_VD25H = VDD25 & VDD85A & ( ~D2A_VDD85D_VD25ENA ? '1 : D2A_VDD85D_VD25TH ? '1 : VDD25 );
        reg_VD33L = VDD25 & VDD85A & ( ~D2A_VDD85D_VD33ENA ? '1 : D2A_VDD85D_VD33TL ? '1 : VDD33 );
        reg_VD33H = VDD25 & VDD85A & ( ~D2A_VDD85D_VD33ENA ? '1 : D2A_VDD85D_VD33TH ? '1 : VDD33 );
    end
```

**Attack scenario.** Unprivileged code on the CM7 or the Vex - or any AHB master reaching core_ahb32, including the BDMA - executes a single 32-bit store of 0x0000_0000 to 0x4005_3040 (or 0x0000_003F to 0x4005_3044). Per pmu_top.sv:282-287 all six comparators immediately output the healthy level. The attacker then mounts a voltage-glitch campaign (T2/T4) against a secure-boot signature branch or an SCE key comparison on the 0.9 V, 2.5 V or 3.3 V rails. vdflag never sets, so sfr_vdsr (0x4005_3008) and the sticky sfr_vdfr (0x4005_300C) both read clean, no interrupt is raised, and vdresetn (sensorc.sv:93-94 -> soc_top.sv:712 secresetn -> sysctrl.sv:794 sysresetgen) never deasserts - even if boot firmware correctly wrote 0x0 to cr_vdmask1. There is no lock bit and no privilege gate anywhere on this path, and firmware cannot detect the blinding except by explicitly re-reading 0x4005_3040/44.

**Verification.** No independent verdict recorded for this entry.

---

<a id="bao-057"></a>

### BAO-057 — Mesh tamper indications are never latched

**Severity: Medium** | CWE-1247 Improper Protection Against Voltage and Clock Glitches | Threat actor: T2 | Confidence: High

**Location:** `rtl/modules/sec/rtl/mesh.sv:55`

*Introduced at the synthesis stage with no structured reviewer record. Read against the RTL
directly during assembly by the orchestrating model; evidence below is quoted from source.*

**Description.** Anti-tamper mesh error indications are combinational and are never latched. `apterr` is a continuous comparison of the sampled mesh value against the drive register, and the status register `sr_mlsr` is a bare reduction of it. A tamper event that disturbs the mesh and then resolves - a probe touched and withdrawn, a transient short - sets the status only for as long as the disturbance persists, then clears it with no persistent record.

**Evidence.**
```systemverilog
// mesh.sv:55 and the comparison feeding it - combinational throughout, no latch
    apb_sr #(.A('h20), .DW(32), .REVY(1), .SFRCNT(LC*GC/32))  sfr_mlsr (.sr(sr_mlsr), .prdata32(),.*);
    ...
    assign apterr[i][j] = cr_mlie[i] & ( aptreg[i][j] != cr_mldrv[i] );
    assign sr_mlsr[i][k] = |apterr[i][GW*k+GW-1:GW*k];
```

**Attack scenario.** A physical attacker probes the mesh briefly. Unless firmware happens to poll `sr_mlsr` during the exact disturbance window, the event leaves no trace. Combined with the mesh's tamper response being a maskable interrupt that resets to disabled, a transient physical intrusion is not merely unpunished but unrecorded.

**Mitigation.** RTL: latch `apterr` into a sticky, software-clearable fault register. Firmware: no reliable mitigation - polling cannot be made fast enough to guarantee catching a transient.

**Verification.** Read against the RTL during report assembly by the orchestrating model.
Not independently reviewed, not adversarially tested, and not seen by a human.

---

<a id="bao-058"></a>

### BAO-058 — Keypad (PIN entry) pad inputs are unconditionally mirrored into the main-domain GPIO input path, and the keypad/GPIO mux plus the full keystroke event FIFO are exposed through unlocked registers with no privilege check

**Severity: Medium** | CWE-1274 Improper Access Control for Volatile Memory Containing Boot Code / CWE-1189 Improper Isolation of Shared Resources on System-on-a-Chip | Threat actor: T1 (unprivileged software on either CPU, or a BIO/BDMA program); T3 for the pad-drive variant | Confidence: Medium

**Location:** `rtl/modules/ao/rtl/ao_sysctrl.sv:562`

**Description.** On this device lineage the 4x4 keypad on PF9-PF2 is the user's PIN/passphrase entry channel. The AO pinmux is asymmetric: the direction that matters for confidentiality is not gated. Line 563 correctly gates the keypad controller's view of the pads on `kpiosel` (`assign kpio[i-2].pi = kpiosel ? socpad[i].pi : 1'b1;`), but line 562 routes the raw pad input into the SoC-domain pinmux with no gate at all (`assign socpad[i].pi = aopad[i].pi;`). Those pads are iopad_F -> iopad[80:89] in the main pinmux (soc_top.sv:806), so while the user is typing a PIN the raw column/row lines are simultaneously readable through the ordinary GPIO input registers by any code in the main domain. Compounding this: `kpiosel` itself is AO_IOX at 0x4006_0060, a plain unlocked `apb_cr` with reset 0, so any master can also take the pads away from the keypad controller and drive them from the SoC pinmux (line 559/561 select socpad's po/oe when kpiosel=0). And the keypad controller's own registers are equally open — `assign sfrlock = '0;` (dkpc.sv:182) — exposing the live 16-node matrix plus the four raw KPI pins in KPC_SR0 at 0x4006_4010 and a FIFO of {16-bit timestamp, node index} press/release events at KPC_FF 0x4006_4020. Nothing in the AO APB path applies a coreuser, hauser or pprot check, so there is no notion of a privileged owner of the keypad.

**Evidence.**
```systemverilog
rtl/modules/ao/rtl/ao_sysctrl.sv:558-564 (note 562 ungated vs 563 gated)
        for (genvar i = 2; i < IOC; i++) begin:gio2
            assign aopad[i].po = kpiosel ? kpio[i-2].po : socpad[i].po;
            assign aopad[i].pu = aopadpu[i];//kpiosel ? kpio[i-2].pu : socpad[i].pu;
            assign aopad[i].oe = kpiosel ? kpio[i-2].oe : socpad[i].oe;
            assign socpad[i].pi = aopad[i].pi;
            assign kpio[i-2].pi = kpiosel ? socpad[i].pi : 1'b1;
        end

rtl/modules/ao/rtl/ao_sysctrl.sv:413 (mux select is an unlocked CR)
    apb_cr #(.A('h60), .DW(1))                   sfr_iox       (.cr(kpiosel   ), .prdata32(),.*);
rtl/modules/ao/rtl/ao_sysctrl.sv:362
    assign sfrlock = '0;

rtl/modules/ao/rtl/dkpc.sv:181-182
    logic sfrlock;
    assign sfrlock = '0;
rtl/modules/ao/rtl/dkpc.sv:195 (live matrix + raw pin state)
    apb_sr #(.A('h10), .DW(KPOC*KPIC+4) )      sfr_sr0          (.sr({kpi[3].pi, kpi[2].pi, kpi[1].pi, kpi[0].pi,  kpnodereg}), .prdata32(),.*);
rtl/modules/ao/rtl/dkpc.sv:142 (timestamped event)
    assign evdat = {tikcnt, evidx};
rtl/modules/ao/rtl/dkpc.sv:198-205 (event FIFO exposed as a read-pop APB window)
    apb_buf2  #(.BAW(3), .A(12'h20), .DW(32) ) sfr_ff (
        .prdata32(),
        .buf_addr   (),
        .buf_write  (),
        .buf_read   (evffrd_sfr),
        .buf_datain (),
        .buf_dataout({evffrdat[20:5],11'h0,evffrdat[4:0]}),
        .*);

rtl/asic_top/rtl/soc_top.sv:806 (PF pads are ordinary GPIO in the main pinmux)
    iothrus #(10)uiopadF(.iodrv(iopad_F[0: 9]), .ioload(iopad[80:89])); // [80:95]
```

**Preconditions.** Any code execution able to reach the AO APB window (0x4006_0000-0x4006_0FFF) or the main-domain GPIO input registers. Requires the device to use the PF keypad as its trusted PIN/passphrase entry path, which docs/src/system-control.md:171-198 and docs/src/ch03-00-io-configuration.md:21 describe.

**Attack scenario.** 1. A compromised unprivileged process on either CPU (T1), or the BIO/BDMA AHB master (hauser='0', matching no identity check anywhere in the design), configures the PF9-PF2 pads as GPIO inputs in the main-domain pinmux. Because ao_sysctrl.sv:562 mirrors `aopad[i].pi` into `socpad[i].pi` unconditionally, this works even while `kpiosel=1` and the keypad controller believes it owns the pins. 2. The attacker polls the GPIO input register while the user enters a PIN, observing the scan pattern: the keypad drives one KPO row at a time (dkpc.sv:100-105) and the pressed key pulls the corresponding KPI column, so the row/column pair is directly recoverable from the raw pad samples. 3. Alternatively, and more cheaply, the attacker just reads KPC_SR0 at 0x4006_4010 for the decoded 16-node matrix state, or pops KPC_FF at 0x4006_4020 for a stream of {16-bit tikcnt timestamp, node index} press and release events — giving both the digits and the inter-keystroke timing, which is itself usable for a timing-based guessing advantage. 4. As an active variant, the attacker writes 0 to AO_IOX (0x4006_0060); lines 559/561 then hand po/oe of the keypad pads to the SoC pinmux, letting the attacker drive the rows and columns directly and forge keypresses to the real keypad controller, or hold a column asserted to mask the user's real input.

**Mitigation.** RTL: gate the pad-to-SoC input path on the mux select exactly as the reverse path is gated — change ao_sysctrl.sv:562 to `assign socpad[i].pi = kpiosel ? 1'b0 : aopad[i].pi;` so the keypad lines are not visible to the general-purpose GPIO block while the keypad function is selected. Make `kpiosel` (AO_IOX) a lockable register so that boot firmware can pin the keypad to the AO controller. Drive `sfrlock` in dkpc from a real lock, and put a coreuser/hauser filter in front of the AO APB so that only the identity that owns the secure input path can read KPC_SR0/KPC_FF. Silicon workaround: partial only. Firmware must keep the PF9-PF2 GPIO input registers and the whole 0x4006_4000 page out of every untrusted address space, must never map the AO page to application code, and should treat any concurrent GPIO configuration of iopad[80:89] as a compromise indicator — but with no MPU configuration active in this build and no bus-level filter, this is a software-only control that anything with bus access can bypass.

**Verification.** Independently confirmed by a second reviewer. ao_sysctrl.sv:558-564 verbatim as quoted, including `assign socpad[i].pi = aopad[i].pi;` at 562 ungated and `assign kpio[i-2].pi = kpiosel ? socpad[i].pi : 1'b1;` at 563. sfr_iox at :413 and sfrlock='0 at :362 confirmed. dkpc.sv:181-182, :142 (`assign evdat = {tikcnt, evidx};`), :195 (sfr_sr0 exposing `{kpi[3].pi, kpi[2].pi, kpi[1].pi, kpi[0].pi, kpnodereg}`) and :198-205 (apb_buf2 read-pop FIFO at 'h20) all verbatim; dkpc.sv:100-105 is the one-row-at-a-time scan as described. I closed the gap the finder left open: daric_top.sv:900 `.socpad(iopad_F)`, soc_top.sv:806 `iothrus #(10)uiopadF(.iodrv(iopad_F[0: 9]), .ioload(iopad[80:89]));`, and in the pinmux iox.sv:78-81 `\`thereg( iopireg0[i] ) <= iopad[i].pi;` / `assign iopi[i] = iopireg[i];` with iox.sv:211-227 `assign srgi[...] = { iopi[...] }` feeding `apb_sr #(.A('h130+GPIOSFRC*3*4)) sfr_gpioin` (line 159). The GPIO input status register therefore shows the live PF pad values REGARDLESS of `afsel`, so the polling attack works while kpiosel=1. iox.sv:111/113 additionally lets any code arm a pad interrupt on those same indices. `.ioxlock('0)` at soc_top.sv:772 means the iox SFRs are unlocked too. docs/src/system-control.md:185 confirms 'Port F (PF9-PF2) is dedicated to the keypad function'. Severity stays medium: it is a confidentiality break of the user input channel available to any bus master, but the PIN-entry assumption is a product-level premise I could not verify from RTL.

**Corrections applied by the verifier.** One framing correction: line 562 is not a 'missing gate symmetric to 563'. Line 563 exists so the keypad FSM does not see stray activity when it does not own the pins; line 562 is the ordinary pad-input-to-pinmux path that every pinmux has. Argue the finding as 'there is no way to make the keypad lines invisible to the general-purpose GPIO block, and no privileged owner of the secure input path', not as an asymmetry bug - the vendor will otherwise dismiss it. Also, the easiest attack is not the GPIO polling variant, it is simply reading KPC_SR0 / popping KPC_FF, which needs no assumption about the pinmux at all.

---

<a id="bao-059"></a>

### BAO-059 — The always-on timebase source is a software-selectable mux with no lock and no privilege check: any bus master can hand clk32k to an external pad or stall it, freezing the RTC, the AO watchdog and both AO reset-extension counters

**Severity: Medium**

**Location:** `rtl/modules/ao/rtl/ao_sysctrl.sv:379`

*Surfaced by the independent verifier, not the original domain reviewer.*

**Description.** AO_CR bit [0] (`clk32kselreg`, 0x4006_0000) selects whether the always-on 32 kHz clock comes from the on-die RC oscillator or from the externally driven XTAL32K pad, and AO_OSCCR (0x4006_0034) holds the oscillator-enable shadow values applied automatically whenever `ipsleep` or `aopdreg` asserts. Both are plain `apb_cr` registers on the AO APB, where `sfrlock` is hard-tied to zero (ao_sysctrl.sv:362) and no coreuser/hauser/pprot filter exists anywhere on the path. `clk32k` is not a peripheral clock: it is the clock of BOTH AO reset-extension counters (genporreset at ao_sysctrl.sv:424-430 producing porresetn_undft, and gensocreset at 445-451 producing socresetn_undft), of the 1 Hz divider that drives the RTC (496-501, aoperi.sv:53), of the 1 kHz divider that drives the AO watchdog (aoperi.sv:37-40), of the keypad scan engine and of the power-down FSM. Switching the source to a pad that is not driven, or disabling the oscillator through the low-power shadow before entering sleep, stops the entire AO timebase; `cgudyncswt` is a glitch-free switch with no liveness check on the target clock and no fallback to the source it left. Nothing bounds, locks or sanity-checks the selection, and nothing detects that clk32k has stopped.

**Evidence.**
```systemverilog
rtl/modules/ao/rtl/ao_sysctrl.sv:362
    assign sfrlock = '0;
rtl/modules/ao/rtl/ao_sysctrl.sv:379
    apb_cr #(.A('h0), .DW(3), .IV(3'h6))        cr_cr            (.cr( { pclkicg, pdisoen, clk32kselreg}       ), .prdata32(),.*);
rtl/modules/ao/rtl/ao_sysctrl.sv:264
    assign osc_ctrl = ipsleep ? sfrosccrlp : aopdreg ? sfrosccrpd : osccrreg;
rtl/modules/ao/rtl/ao_sysctrl.sv:398-399
    apb_cr #(.A('h34), .DW(3+OSCTRMW*2), .IV({IV_OSC32KCR,IV_OSC32KTRM,IV_OSC32KCR,IV_OSC32KTRM,IV_OSC32KCR}))   sfr_osccr
                 (.cr({  sfrosccrpd, sfrosctrmlp, sfrosccrlp, sfrosctrm, sfrosccr} ), .prdata32(),.*);
rtl/modules/ao/rtl/ao_sysctrl.sv:471
    assign osc32ken0 = cmsatpg ? '0 : osc_ctrl;
rtl/modules/ao/rtl/ao_sysctrl.sv:479-491
    cgudyncswt uclk32ksel(
        .clk0   (clkosc32k_dft),
        .clk1   (clkxtl32k_dft),
        .resetn (porresetn),
        .clksel (clk32kselreg),
        .clk0en (clkosc32ken),
        .clk1en (clkxtl32ken)
    );
    ...
    assign clk32k_unbuf = cmsatpg ? clkocc : ( clk32k0 | clk32k1 ) ;
rtl/modules/ao/rtl/ao_sysctrl.sv:424-430 (POR reset extension is clocked by clk32k)
    aoresetgen #(.ICNT(1),.EXTCNT(10))genporreset(
        .clk         ( clk32k ),
rtl/modules/ao/rtl/ao_sysctrl.sv:445-451 (SoC reset extension is clocked by clk32k)
    aoresetgen #(.ICNT(1),.EXTCNT(RSTEXTCNT))gensocreset(
        .clk         ( clk32k ),
rtl/modules/sysctrl/rtl/aoperi.sv:37-40 (AO watchdog timebase)
    `theregfull( clk32k, presetn, clk1kcnt, '0 ) <= clk1kcnt + 1;
    `theregfull( clk32k, presetn, clk1ken, '0 ) <= ( clk1kcnt == '1 ) ;
    ICG_hvt uclk1k ( .CK (clk32k), .SE(cmsatpg), .EN (clk1ken), .CKG(clk1k));
rtl/asic_top/rtl/pad_frame_arm.sv:410 (the alternate source is an external pin)
    padcell_xtal #(.X33k(1),.H('0)) u_xtal32k( .padxin(XTAL32K_IN), .padxout(XTAL32K_OUT), .pc( clkxtl32k ), .thecfg('0), .rtosns(rtosnsao),.sleep(1'b0) );
```

**Attack scenario.** T1: unprivileged code on either CPU, or a BIO/BDMA program (hauser='0', matched by no identity check anywhere), writes 1 to AO_CR[0] at 0x4006_0000 on a board with no 32 kHz crystal populated. `cgudyncswt` disables the RC-oscillator ICG and waits for a handshake on `clkxtl32k` that never arrives, so `clk32k = clk32k0 | clk32k1` stops. The RTC 1 Hz tick stops, the AO watchdog's 1 kHz tick stops, the keypad scan stops, and both AO reset-extension counters freeze - so any RTC-based retry throttle or time-based lockout is frozen and the AO watchdog can no longer time out, all without touching any documented security register. The APB itself stays alive (pclk comes from aopclk, ao_sysctrl.sv:609-616), so the attack is silent rather than self-limiting. T1+T3: with XTAL32K_IN driven by the attacker, the AO timebase becomes attacker-rate: the RTC can be run arbitrarily fast to expire a lockout, or arbitrarily slow to extend the reset-extension windows. A variant needing no pad access at all: write sfrosccrlp=0 in AO_OSCCR (0x4006_0034) and enter sleep, at which point ao_sysctrl.sv:264 switches osc_ctrl to the attacker's shadow value and gates the oscillator off for the duration of sleep.

**Verification.** No independent verdict recorded for this entry.

---

<a id="bao-060"></a>

### BAO-060 — Unprivileged software can permanently power down the SoC domain with no wake path: AO_WKUPMASK and PMU_PDAR are unlocked and unfiltered, and masking all wake sources makes pmupdresetn permanently inactive

**Severity: Medium**

**Location:** `rtl/modules/ao/rtl/ao_sysctrl.sv:588`

*Surfaced by the independent verifier, not the original domain reviewer.*

**Description.** `pmupdresetn` is the only signal that clears `aopdreg`, and `aopdreg` is the only thing that releases `socresetnin` once the power-down flow has run. `pmupdresetn = (~|pmupdresetsrc) & porresetn`, and `pmupdresetsrc` is the full wake-source vector ANDed with `~wkupmask`. `wkupmask` is bits [17:8] of a plain `apb_cr` at AO offset 0x08 with no `.IV` and, like every AO register, `sfrlock` hard-tied to zero and no coreuser/hauser/pprot filter on the bridge. If any bus master sets all ten mask bits and then triggers the power-down flow by writing the magic 0x5A to PMU_PDAR at 0x4006_0044 (also a plain unlocked `apb_ar`), `pmupdresetsrc` is identically zero forever, `pmupdresetn` never asserts, `aopdreg` never clears, and `socresetnin = ~aopdreg & (&rstsrc)` is stuck at 0, holding the entire SoC domain in reset. `aowkupvld = ~pmupdresetn` is also stuck low, so nothing signals the SoC either. Neither the PF0/PF1 wake pads, nor the RTC, nor the AO watchdog, nor the keypad can recover the device; only PAD_XRSTn or a true POR (which drive `porresetn` low) will. There is no lock bit, no write-once, no plausibility check that at least one wake source remains armed, and no privilege distinction between the code that is allowed to configure power management and the code that is not.

**Evidence.**
```systemverilog
rtl/modules/ao/rtl/ao_sysctrl.sv:362
    assign sfrlock = '0;
rtl/modules/ao/rtl/ao_sysctrl.sv:381
    apb_cr #(.A('h8), .DW(18))                  cr_wkupmask      (.cr( {wkupmask, inten}  ), .prdata32(),.*);
rtl/modules/ao/rtl/ao_sysctrl.sv:404
    apb_ar #(.A('h44), .AR(32'h5a))              sfr_pmupdar  (.ar(sfrpmupdar    ),             .*);
rtl/modules/ao/rtl/ao_sysctrl.sv:583-584
    `theregfull( clk32k, resetn, pdflowfsm, '0 ) <= ( pdflowfsm != 0 ) | pdar ? (( pdflowfsm == 4 )&pdflowfsmstop ?  pdflowfsm : ( pdflowfsm == 7 ) ? '0 : pdflowfsm + 1 ) : pdflowfsm;
    `theregfull( clk32k, pmupdresetn, aopdreg, '0 ) <= ( pdflowfsm == 2 ) ? 1 : aopdreg;
rtl/modules/ao/rtl/ao_sysctrl.sv:588
    assign pmupdresetn = cmsatpg ? atpgrst : ( ~|pmupdresetsrc ) & porresetn;
rtl/modules/ao/rtl/ao_sysctrl.sv:594-598
    assign pmupdresetsrc =
                {
                ~aopad[0].pi, ~aopad[1].pi, //~aopad[2].pi, ...
                wkupintsrc
                }& ~wkupmask ;
rtl/modules/ao/rtl/ao_sysctrl.sv:443
    assign socresetnin = cmsatpg ? 1'b1 : ~aopdreg & (&rstsrc) ;
rtl/modules/ao/rtl/ao_sysctrl.sv:601
    assign aowkupvld = ~pmupdresetn; //wakeup for socpd
```

**Attack scenario.** T1: unprivileged code on either CPU - or a BIO/BDMA program, whose AHB master drives hauser='0' (bio_bdma.sv:1579, 1670) and is matched by no identity check anywhere in the design - performs exactly two bus writes. First, 0x4006_0008 <= 0x0003_FF00, setting wkupmask[9:0] to all ones so that `pmupdresetsrc` is forced to zero regardless of the PF0/PF1 pads, the keypad async wake, the RTC, the ATimer or either watchdog. Second, 0x4006_0044 <= 0x0000_005A, which pulses `sfrpmupdar` -> `pdar` -> the pdflow FSM, which asserts `aopdreg` at state 2. From that instant `socresetnin` is 0 and `pmupdresetn` is stuck at porresetn=1, so `aopdreg` can never clear. The SoC domain, both CPUs, the SCE and all peripherals are held in reset indefinitely; the AO domain stays powered but has no path back. Recovery requires physical assertion of PAD_XRSTn or removal of the AO supply, which for a sealed/battery-backed secure element is a hard denial of service. The same two registers also make a subtler attack possible: masking only the AO watchdog and RTC bits while leaving PF0/PF1 armed silently removes the timeout-based recovery paths while leaving the device looking healthy.

**Verification.** No independent verdict recorded for this entry.

---

<a id="bao-061"></a>

### BAO-061 — No AO configuration register is cleared by any system, core, watchdog or software reset — attacker-chosen PMU trims, isolation, clock source, wake mask and keypad mux persist across the reset that re-runs secure boot

**Severity: Medium**

**Location:** `rtl/modules/ao/rtl/ao_sysctrl.sv:434`

*Surfaced by the independent verifier, not the original domain reviewer.*

**Description.** Every SFR in ao_sysctrl (and in dkpc and aobureg) takes its reset from the local `resetn`, which is `porresetn`, which is derived solely from `por = ~pmu_POR & padresetn` - a true power-on reset or the external PAD_XRSTn pin. The SoC's own reset sources do not reach the AO domain at all: sysctrl's software reset registers (sfr_rcurst0/sfr_rcurst1 at 0x4004_0080/0084, magic 0x55AA), the SoC watchdog (`wdtresetn`, soc_top.sv:519) and the CM7/Vex reset requests all terminate at `sysresetgen`/`coreresetgen` inside sysctrl (sysctrl.sv:790-803) and never propagate into ao_sysctrl. The consequence is that a warm reset - including the one that re-runs the boot ROM and the secure-boot chain - leaves the entire AO configuration at whatever values the previous (potentially compromised) software left there: PMU_CR/PMU_TRM0/1 and, more importantly, the PMU_CRLP/PMU_TRMLP0/1 and PMU_CRPD shadow registers that ao_sysctrl.sv:245 and :251 apply automatically to the analog rails on every subsequent sleep or power-down entry; AO_RSTCR_MASK (the brown-out reset mask); AO_CR (isolation enable and 32 kHz source select); AO_WKUPMASK; AO_IOX (keypad/GPIO mux); AO_PADPU; and the AO oscillator trims. Boot firmware therefore cannot rely on reset defaults for any of these, and because there is no lock bit anywhere in the AO domain (`assign sfrlock = '0;`) it also cannot seal them once it has set them. This turns every other AO register weakness into a persistent one that survives the security boundary a reset is supposed to re-establish.

**Evidence.**
```systemverilog
rtl/modules/ao/rtl/ao_sysctrl.sv:422
    assign por = ~pmu_POR & padresetn ;
rtl/modules/ao/rtl/ao_sysctrl.sv:431
    assign porresetn = cmsatpg ? atpgrst : porresetn_undft;
rtl/modules/ao/rtl/ao_sysctrl.sv:434
    assign resetn = porresetn;
rtl/modules/ao/rtl/ao_sysctrl.sv:362
    assign sfrlock = '0;
rtl/modules/ao/rtl/ao_sysctrl.sv:251 (the persisted shadow is re-applied on every sleep)
    assign pmu_trm  =  cmsatpg ? pmutrmreg : ipsleep | aopdreg ? sfrpmutrmlp : pmutrmreg;
rtl/modules/ao/rtl/ao_sysctrl.sv:245
    assign pmu_ctrl  = cmsatpg ? pmucrreg : ipsleep ? sfrpmucrlp : aopdreg ? sfrpmucrpd : pmucrreg;
rtl/modules/sysctrl/rtl/sysctrl.sv:790-803 (SoC reset sources terminate inside sysctrl)
    resetgen #(.ICNT(4),.EXTCNT(RCUEXTCNT))sysresetgen(
        .resetn      ( socresetn ),
        .resetnin    ( { socresetn, vdresetn, secresetn, ~sysreset_sw } ),
    ...
    resetgen #(.ICNT(5),.EXTCNT(RCUEXTCNT))coreresetgen(
        .resetnin    ( { padresetn, sysresetn, cmsresetn, wdtresetn, ~corereset_sw } ),
rtl/modules/sysctrl/rtl/sysctrl.sv:872-874 (the software reset registers)
    apb_ar #(.A('h80), .AR('h55aa))        sfr_rcurst0    (.ar(sysreset_sw),   .*);
    apb_ar #(.A('h84), .AR('h55aa))        sfr_rcurst1    (.ar(corereset_sw),  .*);
```

**Attack scenario.** T1: compromised application code writes a hostile value into the low-power PMU shadow registers - PMU_TRMLP0/1 at 0x4006_0028/0x4006_002C and PMU_CRLP at 0x4006_0014 - and, to remove the hardware backstop, leaves AO_RSTCR_MASK at its permissive 0x1F default. It then triggers a software reset by writing 0x55AA to 0x4004_0084 (or simply lets the SoC watchdog fire). Both CPUs, the SCE, the fabric and every SoC-domain register are reset and the boot ROM re-runs the secure-boot chain from scratch - but ao_sysctrl.sv:434 means not one AO register moved. The freshly attested firmware now runs on a machine whose analog trim shadow, brown-out reset mask, power-domain isolation bit, always-on clock source, wake-source mask and keypad pin ownership were all chosen by the attacker before the reset, and it has no lock bit available to seal them afterwards. The first time that firmware executes a WFI with the IP low-power path enabled, ao_sysctrl.sv:251 substitutes the attacker's `sfrpmutrmlp` onto the core-rail reference. The same persistence lets an attacker pre-position AO_IOX=0 so the keypad pins come back under SoC-pinmux control after the reset, or pre-position AO_WKUPMASK so that post-reset power management has no wake path.

**Verification.** No independent verdict recorded for this entry.

---

<a id="bao-062"></a>

### BAO-062 — sysctrl's write-protect input `sfrlock` is an undriven net in soc_top: every CGU, PLL, clock-gate and software-reset register is permanently unlocked

**Severity: Medium** | CWE-1233 Security-Sensitive Hardware Controls with Missing Lock Bit Protection | Threat actor: T1 (software execution on either CPU, or control of the BIO/BDMA peripheral master) | Confidence: High

**Location:** `rtl/asic_top/rtl/soc_top.sv:217`

**Description.** `sysctrl` exposes an `sfrlock` port that is threaded into every one of its SFRs via the `.*` connection, and apb_sfr2 uses it as the sole write-enable qualifier (`assign apbwr = ~sfrlock & apbslave.psel & apbslave.penable & apbslave.pwrite;`, apb_sfr.sv:333). In soc_top.sv the signal `sfrlock` is declared at line 217 and connected at line 361 — those are the only two occurrences of the identifier in the entire file. It has no assignment anywhere, so it is a floating net (synthesised as a constant 0, or X in simulation). The result is that there is no write-protection mechanism at all on the sysctrl register block at 0x4004_0000: the clock-cipher seed, CGUSEL0/1 source selects, all CGUFD_* dividers, the clock sub-gates CGUACLKGR/CGUHCLKGR/CGUICLKGR/CGUPCLKGR, the PLL M/N/F/Q registers, the internal-oscillator trim, and both software reset action registers RCURST0/RCURST1 are writable by any bus master that can reach the peripheral APB. There is no coreuser check on this path either (rrc.sv:666-671 is the only coreuser consumer on the bus, and it only covers ReRAM), and no APB slave in the design consumes `pprot`. That the design idiom exists elsewhere makes this clearly an omission: the WDT has a real unlock register (docs/src/system-control.md:590, WDT_LOCKCR write 0x1ACEE551), and other blocks drive sfrlock from real logic (e.g. aes.sv:135 `theregrn( sfrlock ) <= optlock ? 1'b1 : mfsm_done ? '0 : sfrlock;`). This single dangling net is the enabler for the two findings below.

**Evidence.**
```systemverilog
soc_top.sv:215-218
    logic               sysresetn;
//    logic               coreresetn;
    logic               sfrlock;
    logic [3:0]          brready;

soc_top.sv:359-363
                                    .ipt_socset    (ipt_socset),
                                    .ipt_socreg    (ipt_socreg),
    /*        input logic      */   .sfrlock     (sfrlock|'0     ),
    /*        apbif.slave      */   .apbs         (apbsys[0]   ),
    /*        apbif.slave      */   .apbx         (apbsys[0]   ),

rtl/modules/amba/rtl/apb_sfr.sv:333
    assign apbwr = ~sfrlock & apbslave.psel & apbslave.penable & apbslave.pwrite;

rtl/modules/sysctrl/rtl/sysctrl.sv:119
        input logic sfrlock,
```

**Preconditions.** Any bus master able to issue an APB write into the apb1-system block at 0x4004_0000. Per the address map (daric_cfg_pkg.sv:51, soc_top.sv:362) that is reachable from the CM7 AHB-P port (hauser 0x8), the Vex AHB-P port (hauser 0xD), the MDMA (0x7) and the BDMA/BIO peripheral AHB master (hauser 0x0) — none of which is subject to any privilege or coreuser filter on this path.

**Attack scenario.** Attacker with code execution on either CPU (or with control of the BIO/BDMA, which any code that can write 0x5012_4000 has) issues a single 32-bit APB store into 0x4004_00xx. Because `sfrlock` is stuck at 0, apb_sfr.sv:333 unconditionally asserts apbwr and the register updates. There is no way for firmware to close this door after boot: the intended latch-and-lock mechanism exists in the port list but has no driver, so a hardened boot ROM cannot freeze the clock tree, the PLL, or the reset controller before handing control to less-trusted firmware. Concrete downstream consequences are the mesh-clock kill and the CLKSCREW primitive described in the next two findings.

**Mitigation.** RTL fix: drive `sfrlock` from a sticky, set-only flop in soc_top that is set by a write-once 'CGU lock' action register and cleared only by socresetn, e.g. the same pattern already used at aes.sv:135. Better still, split it so that the RCU action registers and the frequency-control registers have independent lock bits. On fabricated silicon there is no software workaround — the net has no driver — so the only mitigation is architectural: keep every bus master that must not be able to reprogram the clock tree off the peripheral AHB entirely (in practice this means not enabling the BDMA peripheral master, and treating any code that reaches the CM7-P/Vex-P port as fully trusted).

**Verification.** Independently confirmed by a second reviewer. Verified directly. `grep -n sfrlock rtl/asic_top/rtl/soc_top.sv` returns exactly two hits: line 217 `logic sfrlock;` and line 361 `/*        input logic      */   .sfrlock     (sfrlock|'0     ),`. No procedural or continuous assignment anywhere in the file, and no other file drives it (soc_top_no_cm7_rv.sv:225/369 has the identical dangling pattern). sysctrl.sv:119 `input logic sfrlock,` threads it into every apb_cr/apb_ar/apb_sr via `.*`, and apb_sfr.sv:333 `assign apbwr = ~sfrlock & apbslave.psel & apbslave.penable & apbslave.pwrite;` is the sole write qualifier. I also confirmed the reachability claim: there is no coreuser, hauser or pprot consumer on the APB path — amba_components.sv:311 and :1067 pass pprot straight through, apb_sfr.sv:270 and amba_components.sv:538 tie it to 0, and no APB slave reads it. The consequence — CGUSEL0/1, CGUFD_*, CGUACLKGR/HCLKGR/ICLKGR/PCLKGR, the PLL M/N/F/Q registers, the OSC trim and RCURST0/1 are all writable by any master reaching 0x4004_0000 — is real and is the enabler for findings 3 and 4.

**Corrections applied by the verifier.** The dangling-net fact is exactly right, but the framing overstates it. `sfrlock` in this codebase is not a security lock facility — it is a generic 'freeze SFRs while the engine is busy' signal, hard-tied to '0 in ~25 blocks (apb_sfr.sv:33 and :283 in the generic wrappers themselves, evc.sv:140, mesh.sv:46, trng.sv:52, bio.sv:219, mdma.sv:100, ao_sysctrl.sv:362, rbist_wrp.sv:161, duart.sv:30, mbox.sv:104, ...). The only drivers that do anything are the crypto engines' busy-freeze (aes.sv:135, alu.sv:131, pke.sv:287, combohasha.sv:203 — `optlock ? 1'b1 : mfsm_done ? '0 : sfrlock`), which is not a boot-time lock. So the correct statement is 'the sysctrl register block has no write protection, and the sysctrl-level port that could have provided it has no driver', not 'the intended latch-and-lock mechanism was omitted'. Also, in 4-state simulation the X does not propagate: apb_sfr's ports are declared `input bit sfrlock` (apb_sfr.sv:90/142/196/243/317/368), so the X is coerced to 0 at the port boundary and writes are enabled in sim as well as in synthesis. Severity reduced to medium because the precondition (peripheral-APB write access) already implies a privileged compromise on both CPUs.

---

<a id="bao-063"></a>

### BAO-063 — The anti-tamper mesh detector's only clock is behind an unlocked software clock gate: writing CGUPCLKGR[7]=0 silently and permanently freezes tamper detection

**Severity: Medium** | CWE-1247 Improper Protection Against Voltage and Clock Glitches | Threat actor: T1 to disable the detector, then T2 to exploit the disabled detector (decapsulation / probing) | Confidence: High

**Location:** `rtl/modules/sysctrl/rtl/sysctrl.sv:867`

**Description.** The mesh tamper detector (rtl/modules/sec/rtl/mesh.sv) is entirely synchronous: it samples the mesh aperture lines into `aptreg` on its clock, and registers the resulting alarm into `irq` on that same clock. Its clock port is driven from `pclkmesh` (secsub.sv:55), which soc_top.sv:702 wires to `pclksub[7]`. `pclksub[7]` is produced by an ICG whose enable is `pclken & pclksubgate[gvi]` (sysctrl.sv:635), and `pclksubgate` is nothing more than a plain APB control register at 0x4004_006C with reset value 0xFF and — because of the previous finding — no write protection whatsoever. Documented as 'CGUPCLKGR bit [7] = mesh clock enable' (docs/src/clock-generation.md). Clearing that one bit stops the mesh's clock: `aptreg` stops updating, `apterr` freezes at its last (all-zero) value, `sr_mlsr` freezes, and `irq` freezes at 0. There is no interlock anywhere in the design that detects the tamper block's clock has stopped — no heartbeat, no watchdog on the mesh, no comparison against the freqmeter, and no fail-safe that treats a stopped tamper clock as a tamper event. The identical construction applies to the SCE clock (CGUHCLKGR[0] -> hclksub[1] -> soc_top.sv:573 `.clksce ( hclksub[1] )`), which lets software freeze the crypto engine mid-operation while its RAMs remain on the ungated `clk`, and to the QFC (CGUACLKGR[4]) and BIO (CGUICLKGR[7]).

**Evidence.**
```systemverilog
rtl/modules/sysctrl/rtl/sysctrl.sv:867
    apb_cr #(.A('h6c), .DW(PCKCNT),   .IV('hff)) sfr_pclkgr     (.cr(pclksubgate),.prdata32(),.*);

rtl/modules/sysctrl/rtl/sysctrl.sv:634-636
    for (gvi = 0; gvi < PCKCNT; gvi++) begin: genpclksub
             ICG upclksub ( .CK (clktop   ), .EN ( pclken & pclksubgate[gvi] ), .SE(cmsatpg), .CKG ( pclksub_unmux[gvi] ));
             CLKCELL_MUX2 u_scanmux_clkpsub  (.A(pclksub_unmux[gvi]),.B(clkocc5_50m),.S(atpg_ascapen),.Z(pclksub[gvi]));

rtl/asic_top/rtl/soc_top.sv:702
                           .pclkmesh (pclksub[7]),

rtl/modules/sec/rtl/secsub.sv:54-55
	)meshc(
	    .clk 		( pclkmesh ),

rtl/modules/sec/rtl/mesh.sv:67-68
			`theregrn( aptreg[i][j] ) <= apt[i][j];
			assign apterr[i][j] = cr_mlie[i] & ( aptreg[i][j] != cr_mldrv[i] );

rtl/modules/sec/rtl/mesh.sv:76
	`theregrn( irq ) <= | sr_mlsr;
```

**Preconditions.** Ability to perform one APB write to 0x4004_006C. Reachable from the CM7 AHB-P port, the Vex AHB-P port, the MDMA, or the BDMA peripheral AHB master (hauser=0x0, which matches no check anywhere). Requires the `sfrlock` defect above, i.e. it is unconditional on this silicon.

**Attack scenario.** 1. Attacker obtains code execution on either CPU, or programs the BIO to issue a peripheral write (bio_bdma peripheral AHB master, hauser=0). 2. Writes 0x0000007F to 0x4004_006C (CGUPCLKGR), clearing only bit 7. 3. The ICG at sysctrl.sv:635 stops pclksub[7]. mesh.sv's `aptreg` and `irq` flops stop clocking; the mesh alarm output is frozen low. Note that the mesh's own APB slave also runs on this clock, so a monitor task reading MESH_MLSR at 0x4005_2020 sees a stale all-zero status and cannot tell the block is dead — apbx.pready is combinational (`apbs_common`), so the read completes normally. 4. The attacker now decapsulates / drills / probes through the mesh with tamper detection disabled. This composes with the fact that mesh.sv:53-54's `cr_mldrv` and `cr_mlie` reset to 0 (mesh detection is OFF at reset until firmware enables it) and with the fact that the mesh IRQ is routed to `err[3] = |secirq` -> evc, whose NMI mask resets to 0 (see finding below), so even a working mesh raises nothing by default.

**Mitigation.** RTL fix: remove pclksub[7] from the software-writable gate — clock the mesh (and sensorc/gluechain) from an ungateable branch of pclk, or hard-tie pclksubgate[7] to 1. If a gate must exist, add a lock bit (see previous finding) and add a heartbeat: a counter in the always-on or sysctrl domain that asserts a tamper reset if the mesh clock has not toggled for N cycles. Firmware workaround on fabricated silicon: (a) have the boot ROM / trusted firmware never hand off with the tamper block reachable — but the register is unlockable, so this is not enforceable; (b) periodically prove liveness from a different clock domain, e.g. set MESH_MLDRV to a known pattern with MESH_MLIE enabled and confirm MESH_MLSR changes as expected within a bounded time measured on clksys, treating a stale value as a tamper event; (c) additionally enable EVC_ERRCR bit 3 so |secirq escalates to NMI (see next finding), which at least removes the silent-failure mode for a live mesh.

**Verification.** Independently confirmed by a second reviewer. Every link verified. sysctrl.sv:867 is verbatim `apb_cr #(.A('h6c), .DW(PCKCNT),   .IV('hff)) sfr_pclkgr     (.cr(pclksubgate),.prdata32(),.*);` — a plain control register at offset 0x6C, reset 0xFF, with the undriven sfrlock from finding 2 as its only write qualifier. sysctrl.sv:635 is verbatim `ICG upclksub ( .CK (clktop   ), .EN ( pclken & pclksubgate[gvi] ), .SE(cmsatpg), .CKG ( pclksub_unmux[gvi] ));`. soc_top.sv:702 `.pclkmesh (pclksub[7]),` and secsub.sv:54-55 `)meshc(  .clk ( pclkmesh ),` complete the path to the mesh. I confirmed the absence of any interlock: the freqmeter's clkin bundle (sysctrl.sv:650) is `{fclk, clkpke, aoclk, clkaoram, clkosc, clk32m, clkpll0, clkpll1}` — no pclksub branch is measured — and grep shows no other consumer of pclksubgate. The composition claim also holds: mesh.sv cr_mldrv/cr_mlie are plain apb_cr with default IV=0, so detection is off until firmware enables it, and secsub.sv:100 `assign irq8 = {meshirq, sensorcirq, glcirq} | '0;` is the mesh's only output — unlike the sensor branch, which has an independent hardware path via `vdresetn` -> `secresetn` -> sysctrl.sv:794 sysresetgen. The identical construction on hclksub[1] (SCE) and the other sub-gates is likewise real.

**Corrections applied by the verifier.** Two small mechanical corrections: `sr_mlsr` and `apterr` are purely combinational (mesh.sv:68-73), so they do not 'freeze' independently — they hold because their input `aptreg` holds; only `aptreg` (mesh.sv:67) and `irq` (mesh.sv:76) are the stopped flops. Severity reduced to medium: the precondition is the same privileged peripheral-APB write access as finding 2, and the payoff still requires a physical (T2) attack, so this is a defence-in-depth failure rather than a direct asset compromise. The finder's supporting claim about silent readback is correct and I verified it: `apbs_common` (apb_sfr.sv:19-22) is `assign apbx.pready = 1'b1;`, so a MESH_MLSR read completes combinationally with a stale value even with the block's clock stopped.

---

<a id="bao-064"></a>

### BAO-064 — CLKSCREW: PLL ratio, oscillator trim and every clock divider are software-writable with no bound, no lock, and a frequency monitor that is advisory only

**Severity: Medium** | CWE-1247 Improper Protection Against Voltage and Clock Glitches | Threat actor: T1 (software on either CPU or control of the BIO/BDMA), giving a T2-class fault-injection capability without physical access | Confidence: High

**Location:** `rtl/modules/sysctrl/rtl/sysctrl.sv:881`

**Description.** Every knob that sets the operating frequency of the crypto and security logic is a plain, unlocked APB control register in the sysctrl block: PLL feedback/pre-divider (`sfr_ipcpllmn`, 17 bits, 0x4004_00A0), PLL post-dividers (`sfr_ipcpllq`, 0x4004_00A8), PLL charge-pump/VCO bias (`sfr_ipccr`, 0x4004_00AC), the internal 32 MHz oscillator trim (`sfr_ipcosc`, 0x4004_009C), the clktop/clksys source selects (`sfr_cgusel0`/`sfr_cgusel1`), and the per-domain frequency dividers (`sfr_cgufd` for FCLK/ACLK/HCLK/ICLK/PCLK, plus PKE and PER). Nothing in the RTL bounds any of them. The design contains a frequency meter — `freqmeter` (freqmeter.sv), measuring FCLK, CLKPKE, CLKAO, CLKAORAM, OSC, XTAL, PLL0 and PLL1 — but its outputs `fsvld`/`fsfreq` are consumed by exactly two read-only status registers and by nothing else in the entire design (verified by grep across rtl/: the only consumers are sysctrl.sv:849-850). It gates no clock, triggers no reset, and raises no interrupt. It is purely advisory. Furthermore, the one structure that looks like a hardware frequency floor is dead: `cgufdsync` declares `parameter FD0 = 2**(FDW-1)-1` and cgucore.sv:177/210 instantiate it with `.FD0('h7F)`/`.FD0('hF)`, but the identifier `FD0` is never referenced in the module body — the only 'min cycle' limit that has any effect is the runtime `fd0` input, which comes from CGUFD_*[23:16] and resets to 0 (no limit) for FCLK/ACLK/HCLK/ICLK/PCLK. docs/src/clock-generation.md publishes hard maxima (FCLK 700 MHz, ACLK 350, HCLK 175, PCLK 43.75, PKECLK 175/300) that exist only as documentation.

**Evidence.**
```systemverilog
rtl/modules/sysctrl/rtl/sysctrl.sv:876-884
    apb_ar #(.A('h90), .AR('h32))              sfr_ipcarpll       (.ar(ipc_setcfgpll),                .*);
    apb_ar #(.A('h90), .AR('h57))              sfr_ipcaripflow    (.ar(ipflow_setar),                .*);
    apb_cr #(.A('h94), .DW(16), .IV('h01) )    sfr_ipcen    (.cr(ipc_en),    .prdata32(),.*);
    apb_cr #(.A('h98), .DW(16), .IV('h01) )    sfr_ipclpen  (.cr(ipc_lpen),  .prdata32(),.*);
    apb_cr #(.A('h9c), .DW(7),  .IV(IV_OSC32MTRM))    sfr_ipcosc   (.cr(ipc_osc),   .prdata32(),.*);
    apb_cr #(.A('ha0), .DW(17), .IV(PLLMNIV))  sfr_ipcpllmn (.cr(ipc_pllmn), .prdata32(),.*);
    apb_cr #(.A('ha4), .DW(25), .IV('hff) )    sfr_ipcpllf  (.cr(ipc_pllf),  .prdata32(),.*);
    apb_cr #(.A('ha8), .DW(15), .IV('0)   )    sfr_ipcpllq  (.cr(ipc_pllq),  .prdata32(),.*);
    apb_cr #(.A('hac), .DW(16), .IV('h53) )    sfr_ipccr    (.cr(ipccr),     .prdata32(),.*);

rtl/modules/sysctrl/rtl/sysctrl.sv:849-851   (the ONLY consumers of the frequency meter)
    apb_sr #(.A('h40), .DW(32), .SFRCNT(4)   )  sfr_cgufssr   (.sr(fsfreq),     .prdata32(),.*);
    apb_sr #(.A('h50), .DW(8)            )      sfr_cgufsvld  (.sr(fsvld),      .prdata32(),.*);
    apb_cr #(.A('h54), .DW(16), .IV('d48))      sfr_cgufscr   (.cr(fsintv),     .prdata32(),.*);

rtl/modules/sysctrl/rtl/sysctrl.sv:257   (OSC trim path, driven from sfr_ipcosc via the ipflow action register)
        `theregfull( clksys, sysresetn, osc_osc32m_cfgreg, IV_OSC32MTRM ) <= ipflow_settrim ? osc_osc32m_nvr : ipflowfsm_setipcr ? ipc_osc : osc_osc32m_cfgreg;

rtl/modules/sysctrl/rtl/cgufdsync.sv:28-31   (FD0 declared and never used in the body)
#(
    parameter FDW = 8,
    parameter FD0 = 2**(FDW-1)-1
)(
```

**Preconditions.** One or more APB writes into 0x4004_0000-0x4004_00AF. Same reach as the previous findings (CM7-P, Vex-P, MDMA, BDMA-AHB), and unconditional because `sfrlock` has no driver. No coreuser, hauser or pprot check exists on this path.

**Attack scenario.** CLKSCREW-style software-only fault injection against the SCE. 1. Attacker code (on either CPU, or via a BIO peripheral write) starts a victim crypto operation — e.g. an AES or an HMAC/trust-state check in the SCE, which is clocked from hclksub[1] derived from clktop. 2. Attacker writes an out-of-spec PLL ratio into 0x4004_00A0 / 0x4004_00A8, commits it with the action register (write 0x32 to 0x4004_0090), and/or writes CGUFD_HCLK at 0x4004_001C with normal-FD = 0xFF (CLKTOP x 1/1 per the documented encoding) and min-cycle = 0. Alternatively, and without touching the PLL at all, the attacker retunes the root 32 MHz oscillator by writing `sfr_ipcosc` at 0x4004_009C and committing with 0x57 to 0x4004_0090 (sysctrl.sv:257) — clksys feeds clktop by default (CGUSEL0 resets to 0), so this directly overclocks every synchronous block including the SCE. 3. The target domain now runs above its timing closure point; setup violations produce a faulted computation. Nothing intervenes: the freqmeter records the excursion in a read-only register that no logic reads, `cgufdsync`'s only floor (`fd0`) is 0, and there is no reset, interrupt or clock kill. 4. Classic exploitation follows — a faulted RSA-CRT signature in the PKE leaks the private factors; a faulted comparison in combohasha.sv:483-490 flips `chkprepass` and sets a trust-state bit (sce_sec.sv:117), which unlocks a ReRAM key slot (rrc.sv:717 `!trustkey[akeyid]`).

**Mitigation.** RTL fix: (1) clamp `pll_m`/`pll_n`/`pll_q*` and the CGUFD values in hardware to the documented maxima before they reach cgupll/cgufdsync, or at minimum bound the resulting fd0 min-cycle to a non-zero safe floor per domain (make the existing FD0 parameter actually drive the reset value of `fd0reg` instead of being dead); (2) close the freqmeter loop — compare fsfreq against per-domain hardware limits and assert `secresetn` (which already feeds sysresetgen at sysctrl.sv:794) on an over-frequency excursion, and separately on `fsvld` deasserting for a clock that is supposed to be running; (3) put the whole IPC/CGU register bank behind the (currently undriven) sfrlock. On fabricated silicon: firmware must treat 0x4004_0000-0x4004_00AF as a privileged region and prevent any less-trusted code from reaching the peripheral APB at all — but note there is no hardware enforcement available to do this, so the practical workaround is to never enable the BDMA peripheral master and to keep all code with peripheral-bus access inside the trusted boundary; additionally, software can poll CGUFSFREQ0-3 and CGUFSVLD before and after each sensitive crypto operation and discard the result if the measured frequency changed, which detects (but does not prevent) the attack.

**Verification.** Independently confirmed by a second reviewer. All cited RTL is accurate. sysctrl.sv:876-884 matches verbatim including `apb_cr #(.A('h9c), .DW(7), .IV(IV_OSC32MTRM)) sfr_ipcosc`, `.A('ha0) .DW(17) sfr_ipcpllmn`, `.A('ha8) sfr_ipcpllq`, `.A('hac) sfr_ipccr`. sysctrl.sv:257 is verbatim `theregfull( clksys, sysresetn, osc_osc32m_cfgreg, IV_OSC32MTRM ) <= ipflow_settrim ? osc_osc32m_nvr : ipflowfsm_setipcr ? ipc_osc : osc_osc32m_cfgreg;`. The freqmeter-is-advisory claim is correct: grep for fsvld/fsfreq across rtl/ (excluding testbenches) returns only freqmeter.sv itself and sysctrl.sv:651-652 (the port connection) and :849-850 (the two read-only SFRs) — nothing gates a clock or asserts a reset. The dead-FD0 claim is correct: cgufdsync.sv:30 declares `parameter FD0 = 2**(FDW-1)-1` and the identifier never appears again in the module body (lines 32-78); the only floor is the runtime `fd0` input, and sysctrl.sv:838-839 `apb_cr #(.A('h14), .DW(8*4), .IV('h00000f7f), .SFRCNT(5)) sfr_cgufd` unpacked at sysctrl.sv:450-455 as `{ cfgfd0lp, cfgfd0, cfgfdlp, cfgfd }` gives cfgfd0 = 0x00 for FCLK/ACLK/HCLK/ICLK/PCLK. docs/src/clock-generation.md:168 independently confirms this: 'Min cycle: 0x00 = 1 clk', with reset value 0x0000_7F7F. The documented maxima (FCLK 700 MHz at line 159, ACLK 350 at 171, HCLK 175 at 183) exist only in prose.

**Corrections applied by the verifier.** Two of the three attack paths are damped by controls the finder missed, and this matters for the write-up. (1) The PLL path is not a transient-fault primitive: cgupll.sv:100-107 gate both PLL outputs on lock (`clko0ensync <= { clko0ensync, setcfgextlock & lock }`, `ICG i0(.CK(clko0), .EN(clko0en), ...)`), and cgupll.sv:115 drops setcfgextlock on every setcfg, so writing a wild M/N turns the PLL output OFF until it re-locks — the result is a clock stop (self-DoS), not an over-frequency transient. (2) The OSC-trim path is sequenced: sysctrl.sv:710 `assign ipflowfsm_setipcr = ipflowfsm_fdoff & ipflowfsm_setipcrflag;` applies the new trim only in the FDOFF phase of the ipflow FSM, i.e. with the dividers already forced slow (cfgsetdpslp), so it yields a sustained overclock after FDON rather than a glitch. (3) The genuinely unmitigated transient primitive is the one the finder listed second: CGUFD_* + CGUSET (0x4004_0014..0x24 then 0x32 to 0x2C), which reloads fd0reg/fd2reg immediately with no lock, no ramp and no floor. Severity reduced to medium on the same privileged-precondition grounds as finding 2.

---

<a id="bao-065"></a>

### BAO-065 — The CGU 'clock cipher' side-channel countermeasure is a fixed-IV LFSR with one bit of software seed entropy, and the level field is inverted relative to the documentation so the documented 'slowest' setting disables it entirely

**Severity: Medium** | CWE-1241 Use of Predictable Algorithm in Random Number Generator | Threat actor: T2 (power/EM side-channel measurement); the fail-open half needs only a documentation-following integrator | Confidence: High

**Location:** `rtl/modules/sysctrl/rtl/sysctrl.sv:667`

**Description.** docs/src/clock-generation.md states: 'The clock cipher scrambles the system clock by skipping pulses according to the state of an LFSR configured by CGU_SEED. This feature can harden the system against side channel analysis.' Two RTL defects void that claim. (a) PREDICTABILITY: both cipher instances are `drng_lfsr` with compile-time-constant initial vectors ('h55aa_aa55_5a5a_a5a5 for clktop, 'hfedcba9876543210 for clkpke). The only reseed path is `swr`, and insauth.v:38 implements it as `sdin[LFSR_IW-1] ^ sdata` — a single bit (bit 31 of the 32-bit CGU_SEED word) XORed against a 59-bit state, which by Verilog width extension flips only bit 0. The entire 32-bit seed register therefore injects exactly ONE bit of entropy, so the pulse-skip sequence has only two possible trajectories, both derivable from the public RTL. Worse, `sen` is tied to the enable bit (`.sen(clkcipheren)`), so while the cipher is off the LFSR is frozen at its IV and the seed write is ignored — every enable event restarts from the identical state, making the skip pattern perfectly reproducible and trace-alignable across power cycles. CGU_SEED is also plainly bus-readable (sfr_seed.prdata32 is ORed into apbx.prdata at sysctrl.sv:820). (b) INVERTED SEMANTICS / FAIL-OPEN: the documented CGUSEC table says '[3:0] clkcipher level: 0xF = full speed, 0x0 = slowest'. The RTL computes `clkcipherdat >= clkcipherlevel * 16` over an 8-bit LFSR output, so level=0x0 gives threshold 0, the comparison is always true, and NO pulses are ever skipped — level 0 is full speed with the countermeasure silently doing nothing, while level 0xF skips ~94% of pulses. An integrator following the register documentation and writing level=0x0 to select 'slowest / maximum scrambling' gets zero mitigation, with the enable bit reading back as set.

**Evidence.**
```systemverilog
rtl/modules/sysctrl/rtl/sysctrl.sv:667-668  (clktop cipher, fixed IV)
    drng_lfsr #( .LFSR_W(59),.LFSR_NODE({ 10'd57, 10'd55, 10'd52 }), .LFSR_OW(8), .LFSR_IW(32), .LFSR_IV('h55aa_aa55_5a5a_a5a5) )
        ua( .clk(clktop), .sen(clkcipheren), .resetn(sysresetn), .swr(clkcipherseedupd), .sdin(clkcipherseed), .sdout(clkcipherdat) );

rtl/modules/sysctrl/rtl/sysctrl.sv:673,676-677  (inverted level compare)
    `theregfull( clktop, coreresetn, clktopenin_sec, '1 ) <= clkcipheren ? ( clkcipherdat >= clkcipherlevel * 16 ) : '1;
...
    assign clkcipherlevel = cgusec[3:0];
    assign clkcipheren = cgusec[4];

rtl/modules/sysctrl/rtl/sysctrl.sv:549-550,555  (clkpke cipher, same construction, protects the RSA/ECC engine)
    drng_lfsr #( .LFSR_W(59),.LFSR_NODE({ 10'd57, 10'd55, 10'd52 }), .LFSR_OW(8), .LFSR_IW(32), .LFSR_IV('hfedcba9876543210) )
        ub( .clk(clkpketop), .sen(clkpkecipheren), .resetn(sysresetn), .swr(clkpkecipherseedupd), .sdin(clkpkecipherseed), .sdout(clkpkecipherdat) );
...
    `theregfull( clkpketop, coreresetn, clkpketopenin, '1 ) <= clkpkecipheren ? ( clkpkecipherdat >= clkpkecipherlevel * 16 ) : '1;

rtl/modules/common/rtl/insauth.v:38  (the one-bit reseed)
    `theregfull( clk, resetn, sdata, LFSR_IV ) <= sen ? ( swr ? ( sdin[LFSR_IW-1] ^ sdata ) : sdatapre ) : sdata ;

rtl/modules/sysctrl/rtl/sysctrl.sv:834  (seed register, readable at 0x4004_0008)
    apb_cr #(.A('h08), .DW(32))       sfr_seed    (.cr(clkcipherseed),   .prdata32(),.*);
```

**Preconditions.** For the fail-open case: firmware configures CGUSEC per the published register documentation. For the predictability case: the attacker has the (public, CERN-OHL licensed) RTL and can capture power/EM traces; no software access is needed at all since the IV is a compile-time constant.

**Attack scenario.** Case (b), fail-open: firmware enabling the countermeasure for the PKE writes CGUSEC = 0x1000 (enable, level 0) intending 'slowest / most scrambling' per the documented table. sysctrl.sv:555 evaluates `clkpkecipherdat >= 0` which is always true, so `clkpketopenin` stays 1 and the ICG at sysctrl.sv:545 never gates a pulse. The RSA/ECC private-key operation runs with a perfectly regular clock while the status register reports the countermeasure as enabled. Case (a), predictability: even with a correct level, the attacker reads the LFSR polynomial and IV out of the published RTL, simulates 59 bits of state forward from the enable event, and knows exactly which clock cycles were skipped. He resamples/realigns his power traces to remove the skipping and recovers the same leakage he would have had with the countermeasure off. The bus-readable CGU_SEED at 0x4004_0008 removes even the need to guess which of the two possible trajectories is live. Note this composes with the PKE's other masking defect: pke.sv:788-805 uses the same `drng_lfsr` with `.LFSR_IV('h5a5a_a5a5)` and `sen(optsec)`, so the PKE's data masking is deterministic from reset too.

**Mitigation.** RTL fix: (1) reseed the LFSR properly — replace `sdin[LFSR_IW-1] ^ sdata` in insauth.v:38 with a full-width XOR (`{{(LFSR_W-LFSR_IW){1'b0}}, sdin} ^ sdata` or better, load the full seed) so the seed register actually carries 32 bits of entropy; (2) source the seed from the TRNG rather than from a bus-writable/bus-readable register, and make CGU_SEED write-only; (3) let the LFSR free-run (`sen` tied 1) so its state is not reproducible from the enable event; (4) fix the level polarity in sysctrl.sv:673/555 or fix the documentation — and in either case make level=0 the maximally-scrambled setting so the fail-safe direction is 'more mitigation', not 'none'. Firmware workaround on fabricated silicon: treat the level field as inverted with respect to the documentation — write CGUSEC[3:0] = 0xF (and CGUSEC[11:8] = 0xF for PKE) to get maximum pulse skipping, never 0x0. Reseed CGU_SEED from the TRNG with bit 31 varied (only bit 31 has any effect) before every sensitive operation, and re-toggle CGUSEC[4]/[12] so the enable edge is at an unpredictable time. Understand that the countermeasure provides at best trace-misalignment against an attacker who does not have the RTL, and essentially nothing against one who does; do not rely on it as the sole DPA defence.

**Verification.** Independently confirmed by a second reviewer. Both halves verified independently. Predictability: insauth.v:38 is verbatim `theregfull( clk, resetn, sdata, LFSR_IV ) <= sen ? ( swr ? ( sdin[LFSR_IW-1] ^ sdata ) : sdatapre ) : sdata ;`. With LFSR_IW=32, `sdin[31]` is a single bit; Verilog zero-extends it to the 59-bit width of sdata, so a seed write flips only bit 0 — one bit of entropy out of a 32-bit register. `sen` is tied to the enable (sysctrl.sv:668 `.sen(clkcipheren)`, :550 `.sen(clkpkecipheren)`), so the state is frozen at the compile-time IV while disabled and every enable edge restarts from the identical state; the IVs are the literal constants 'h55aa_aa55_5a5a_a5a5 and 'hfedcba9876543210. sysctrl.sv:834 `apb_cr #(.A('h08), .DW(32)) sfr_seed (.cr(clkcipherseed), .prdata32(),.*);` with sfr_seed.prdata32 ORed into apbx.prdata at sysctrl.sv:820 makes the seed bus-readable. Inversion: sysctrl.sv:673 `clkcipheren ? ( clkcipherdat >= clkcipherlevel * 16 ) : '1` with clkcipherdat 8 bits wide (LFSR_OW(8)) means level=0 gives threshold 0, the compare is unconditionally true, and clktopenin_sec never deasserts — zero pulses skipped; level=0xF gives threshold 240, i.e. ~6% of pulses pass. docs/src/clock-generation.md:110 and :112 state the exact opposite: '0xF = full speed, 0x0 = slowest (does not stop)'. This is a documented-guarantee vs. implementation mismatch that fails open, which is the strongest class of finding here.

**Corrections applied by the verifier.** Add one aggravating fact the finder missed: sysctrl.sv:561 `assign clkpkecipherseed = clkcipherseed;` — the PKE cipher and the clktop cipher share the same seed register and the same update pulse (cross-synced at sysctrl.sv:564-570), so the single bit of entropy is common to both LFSRs rather than independent. One mitigating fact: the vendor already discloses reduced confidence in this feature at docs/src/clock-generation.md:117 ('This feature has not yet been thoroughly characterized. It's not recommended to turn it on for clktop as instability has been observed in some settings'), so it is not presented as a load-bearing DPA defence. Severity medium is right.

---

<a id="bao-066"></a>

### BAO-066 — WDT_LOCKCR is bypassable: the watchdog's timebase is pclk, whose divider (CGUFD_PCLK) is an unlocked APB register in the CGU

**Severity: Medium**

**Location:** `rtl/modules/sysctrl/rtl/sysctrl.sv:839`

*Surfaced by the independent verifier, not the original domain reviewer.*

**Description.** The watchdog is the one block in this domain that has a real, documented lock: docs/src/system-control.md:590 says WDT_LOCKCR requires the magic `0x1ACE_E551` to unlock, otherwise 'registers become read-only'. That lock protects WDOGLOAD and WDOGCONTROL, so trusted firmware can arm the watchdog and freeze it before handing off. But the watchdog's counting clock is not protected: soc_top.sv:510-516 instantiates `wdg_intf wdt(.clk(pclk), .resetn(coreresetn), .wdgclk(pclk), ...)` and apbsys_intf.sv:33-34 passes it straight through as `.WDOGCLK(wdgclk), .WDOGCLKEN(1'b1)`. `pclk` is cgucore's clkout[4], whose divide ratio comes from CGUFD_PCLK at 0x4004_0024 — bits [7:0] of cfgfdcr[4], a plain apb_cr with no lock (and, per the confirmed finding above, no sfrlock driver at all). In cgufdsync the FD field is an accumulator step: `fd2cnt <= fd2cnt[FDW-1:0] + fd2reg[FDW-1:0] + 1` with `fd2rdy = fd2cnt[FDW]` (cgufdsync.sv:66-70), so the reset value 0x7F yields one enable every 2 clktop cycles while 0x00 yields one every 256 — a 128x slowdown of the watchdog with a single 32-bit store plus the CGUSET action write, and with no effect on FCLK, so the attacker's own code keeps running at full speed. The documented WDT timeout in milliseconds becomes 128x longer while WDT_LOCKCR still reads locked and WDOGLOAD still reads its trusted value. Nothing in the design cross-checks the watchdog's clock rate (the freqmeter does not measure pclk — sysctrl.sv:650 measures only fclk, clkpke, aoclk, clkaoram, clkosc, clk32m, clkpll0, clkpll1).

**Evidence.**
```systemverilog
rtl/modules/sysctrl/rtl/sysctrl.sv:838-839
    apb_cr #(.A('h14), .DW(8*4),
             .IV('h00000f7f), .SFRCNT(5))         sfr_cgufd       (.cr(cfgfdcr[0:4]),   .prdata32(),.*);

rtl/modules/sysctrl/rtl/sysctrl.sv:845
    apb_ar #(.A('h2c), .AR('h32))   sfr_cguset  (.ar(cfgsetar),               .*);

rtl/modules/sysctrl/rtl/sysctrl.sv:454
    assign { cfgfd0lp[4], cfgfd0[4], cfgfdlp[4], cfgfd[4] } = cfgfdcr[4];

rtl/asic_top/rtl/soc_top.sv:510-516
    wdg_intf wdt(
            .clk    (pclk),
            .resetn (coreresetn),
            .wdgclk (pclk),
            .apbs   (apbsys[1]),
            .wdgintr(wdgintr),
            .wdgrst (wdtreset)
        );

rtl/modules/sysctrl/rtl/apbsys_intf.sv:33-34
    .WDOGCLK           (wdgclk),
    .WDOGCLKEN         (1'b1),

rtl/modules/sysctrl/rtl/cgufdsync.sv:66-70
    `thereg( fd2cnt ) <= clk0en ?
                            ( fdload ? '0 : fd2cnthold ? fd2cnt : ( fd2cnt[FDW-1:0] + fd2reg[FDW-1:0] + 1 )) :
                        fd2cnt;
    assign fd2cnthold = fd2cnt[FDW] && ~clk2en0;
    assign fd2rdy = fd2cnt[FDW];

docs/src/system-control.md:590
| \[31:0\] | VAL | Write `0x1ACE_E551` to unlock all WDT registers. Write any other value to lock them (registers become read-only). Bit \[0\] reads `1` when locked. |
```

**Attack scenario.** Trusted boot arms the watchdog (WDOGLOAD = N, WDOGCONTROL = enable-reset) and locks it by writing a non-magic value to WDT_LOCKCR at 0x4004_1C00, then hands control to less-trusted firmware. That firmware cannot touch any WDT register. It instead issues two stores into the CGU: `*(u32*)0x40040024 = 0x0000_0000` (CGUFD_PCLK: normal FD = 0, min-cycle = 0) followed by `*(u32*)0x4004002C = 0x32` (CGUSET, the fdload action register). cgufdsync reloads fd2reg = 0 on the next clk0en, and pclk drops from clktop/2 to clktop/256. The watchdog now counts 128x slower, so a hang or a stalled operation that was supposed to trigger a reset within N milliseconds instead runs for 128N — long enough to complete a multi-step attack that the watchdog was placed there to bound. WDT_LOCKCR still reads locked, WDOGVALUE still decrements, and no register anywhere reports the change; the freqmeter does not sample pclk, so even a firmware self-check has no signal to poll.

**Verification.** No independent verdict recorded for this entry.

---

<a id="bao-067"></a>

### BAO-067 — BDMA whitelist, DISABLE_FILTER bits and gutter registers have no lock bit and no privilege check — sfrlock is hardwired to zero, so the containment mechanism can be disabled by the code it is meant to contain

**Severity: Medium** | CWE-1233 Security-Sensitive Hardware Controls with Missing Lock Bit Protection | Threat actor: T1 | Confidence: High

**Location:** `rtl/modules/bio_bdma/rtl/bio_bdma.sv:459`

**Description.** docs/src/ch02-00-bio-overview.md:70 states the whitelist "helps prevent abuse of the BDMA as a method for bypassing host CPU security features". For that guarantee to hold, the whitelist must be programmable by a strictly more privileged entity than the one it constrains. In the RTL there is no such asymmetry. Every configuration register in bio_bdma — SFR_CONFIG (which carries DISABLE_FILTER_MEM), the four FILTER_BASE/FILTER_BOUNDS pairs, both GUTTER registers, the instruction-RAM pages and SFR_CTRL (machine enable/restart) — is instantiated through `apb_cr`/`apb_ac2r` with `sfrlock` hardwired to zero at line 459. `apb_sfr2` gates writes solely on `~sfrlock & psel & penable & pwrite`; it does not examine `pprot`. No slave on the ifsub APB path consumes `pprot` or `hprot`, and there is no `coreuser` or `hauser` check anywhere between the AHB matrix and apbper[4] (soc_ifsub.sv:158-168, 361-362). There is therefore no write-once/lock-after-boot path in the RTL at all: the whitelist cannot be frozen after a secure boot stage configures it, and every register is re-writable for the lifetime of the reset domain. Reset value of all filter registers is 0 (apb_cr default IV=32'h0), which does make the whitelist empty at reset as documented — but an empty whitelist is worth nothing if the whitelist is freely rewritable.

**Evidence.**
```systemverilog
bio_bdma.sv:457-460
    // SFR bank
    logic apbrd, apbwr, sfrlock;
    assign sfrlock = '0;
    `apbs_common;

bio_bdma.sv:562-563 (gutters, unlocked)
    apb_cr #(.A('hA0), .DW(32))      sfr_mem_gutter           (.cr(mem_gutter), .prdata32(),.*);
    apb_cr #(.A('hA4), .DW(32))      sfr_peri_gutter          (.cr(peri_gutter), .prdata32(),.*);

bio_bdma.sv:619-627 (whitelist, unlocked)
    /////////////////////// address filtering
    apb_cr #(.A('hE0), .DW(20))      sfr_filter_base_0        (.cr(filter_base[0]), .prdata32(),.*);
    apb_cr #(.A('hE4), .DW(20))      sfr_filter_bounds_0      (.cr(filter_bounds[0]), .prdata32(),.*);
    ...
    apb_cr #(.A('hFC), .DW(20))      sfr_filter_bounds_3      (.cr(filter_bounds[3]), .prdata32(),.*);

rtl/modules/amba/rtl/apb_sfr.sv:333 (the only write gate — no pprot term)
    assign apbwr = ~sfrlock & apbslave.psel & apbslave.penable & apbslave.pwrite;

docs/src/ch02-00-bio-overview.md:70
As a side-note, access to main memory is blocked by a whitelist, which by default is empty. So, before attempting to use the BDMA feature, one must first declare which regions of memory the BIO is allowed to access. This also helps prevent abuse of the BDMA as a method for bypassing host CPU security features.
```

**Preconditions.** APB write access to 0x5012_4000 (Path B), or a whitelist window that overlaps 0x5012_4000 (Path A). No debug mode, no lifecycle state, and no glitching is required.

**Attack scenario.** Path A (self-escalation by the BIO program, does not depend on the OS memory map): firmware whitelists any window that covers a page inside 0x5012_0000-0x5012_FFFF so the BIO can service a peripheral — the ifsub APB peripherals are packed at 4 KB stride inside that 64 KB region (soc_ifsub.sv:131 `'{idx: 32'd1 , start_addr: 32'h5012_0000, end_addr: 32'h5012_ffff}`), and with only four shared windows a coarse whole-block window is the natural configuration. The attacker's BIO program then stores to 0x5012_4008 setting DISABLE_FILTER_MEM, which by the companion defect at line 1478 disables both filters, and to 0x501240A0/A4 to repoint the gutters. From that point the BIO is an unfiltered read/write master over 0x4000_0000-0x7FFF_FFFF.
Path B (direct): any code on either CPU that has 0x5012_4000 mapped writes SFR_CONFIG bit[7] directly, loads a program into the BIO imem at 0x5012_5000, and writes SFR_CTRL at 0x5012_4000 to start it. It now owns a bus master whose ReRAM accesses carry `aruser=0x7` rather than its own identity (see the separate AMBAID finding), and which is not subject to the requesting core's MMU/MPU translation at all — precisely the "bypassing host CPU security features" the documentation claims is prevented.
In both paths there is no hardware event: the BIO block exposes no violation status bit or interrupt for a filtered access, and axil_filter returns the downstream OKAY response verbatim (bio_bdma.sv:2572 `assign s_axi_bresp = m_axi_bresp;`, 2582 `assign s_axi_rresp = m_axi_rresp;`), so neither the host nor an audit routine can observe that the whitelist was ever consulted or overridden.

**Mitigation.** RTL fix: drive `sfrlock` from a sticky write-once bit (e.g. `theregrn(sfrlock) <= sfrlock | cr_lock;`) covering SFR_CONFIG, the eight FILTER registers and both GUTTER registers, and additionally qualify writes to those specific SFRs on `coreuser`/`pprot[0]` so that only boot- or machine-mode code can program them. Firmware workaround on fabricated silicon: treat the whole 0x5012_4000-0x5012_8FFF range as a machine-mode-only resource, unmap it from every user/supervisor address space, never whitelist any window that overlaps 0x5012_0000-0x5012_FFFF (in particular do not use a single coarse window for the ifsub APB block — use 4 KB-granular windows on the specific peripheral pages the BIO needs), and program the whitelist only from the earliest boot stage.

**Verification.** Verified as written; exploitability not fully established. The quoted RTL is accurate: bio_bdma.sv:458-459 `logic apbrd, apbwr, sfrlock; assign sfrlock = '0;`; :562-563 gutters via apb_cr; :620-627 the eight FILTER registers via apb_cr; the write gate in amba_components.sv:1187 `assign apbwr = ~sfrlock & apbslave.psel & apbslave.penable & apbslave.pwrite;` has no pprot/hauser term. I confirmed independently that no slave on the ifsub APB path consumes hauser or pprot: a repo-wide grep for `hauser ==` yields only sce_sec.sv:61-62 and :73, nothing in ifsub. So the factual claims hold. What weakens it to "plausible" rather than "confirmed" is context the finder did not weigh: `assign sfrlock = '0` is a design-wide convention in this SoC, not a bio_bdma-specific slip — evc.sv:140, mdma.sv:100, duart.sv:30, coresub_sramtrm.sv:41, qfc.sv:176, ahb_sfr.sv:31/503, and every rrc.sv SFR (`.sfrlock(1'b0)`) do the same. The architectural expectation is clearly that the CPU MMU/MPU keeps 0x5012_4000 out of untrusted address spaces, and Path B therefore describes an attacker who already fully owns the BIO — no escalation. The genuinely new teeth are Path A (a BIO program reprogramming its own whitelist through a peripheral window overlapping 0x5012_4000), and that is real: the BIO's peripheral master does reach its own SFR block, and once finding #1's copy-paste bug is in play one store to 0x5012_4008 opens everything. But Path A is contingent on a firmware misconfiguration (a coarse window over 0x5012_0000-0x5012_FFFF), not on a hardware default. The claim that a filtered access is silently indistinguishable is correct (bio_bdma.sv:2572 `assign s_axi_bresp = m_axi_bresp;`, :2582 `assign s_axi_rresp = m_axi_rresp;`, no violation status bit anywhere in the block).

**Corrections applied by the verifier.** Severity lowered from high to medium. Two corrections to the framing: (1) the missing lock bit is a systemic SoC convention, not a bio_bdma-specific defect, and the report should say so or the vendor will reasonably respond "that is how every peripheral in this chip works"; (2) Path B is not a privilege escalation — an attacker who can write 0x5012_4000 already owns the BIO by definition. The defensible finding is narrower: the whitelist cannot be frozen after boot, so it provides no protection against a BIO program that has been granted any peripheral window covering its own control block, and there is no way for firmware to hand the BIO to a less-trusted phase.

---

<a id="bao-068"></a>

### BAO-068 — Out-of-range BDMA accesses are re-addressed to a software-programmable, filter-exempt "gutter" address rather than blocked, and reads from it return real bus data — the filter has no deny primitive

**Severity: Medium** | CWE-1220 Insufficient Granularity of Access Control | Threat actor: T1 | Confidence: High

**Location:** `rtl/modules/bio_bdma/rtl/bio_bdma.sv:2562`

**Description.** The documentation describes the whitelist as blocking: "access to main memory is blocked by a whitelist" (ch02-00-bio-overview.md:70) and "By default, all base/bounds are set to 0, which effectively disables BIO DMA access to the rest of the system" (ch02-00-bio-overview.md, FILTER_BASE_0 section). The RTL never blocks anything. `axil_filter` passes AWVALID/ARVALID/WVALID and all data unconditionally to the master port and only substitutes the address: a non-matching transfer is issued to `gutter` instead of being suppressed or errored. `gutter` is `mem_gutter`/`peri_gutter`, two plain 32-bit read/write APB registers (lines 562-563) that are NOT themselves range-checked against the whitelist. The read data path is a straight wire (line 2581 `assign s_axi_rdata = m_axi_rdata;`), so a "blocked" read returns whatever the gutter address holds. The gutter is therefore not a bit-bucket, it is a filter-exempt one-word read/write aperture at an address of the programmer's choosing. There is also no violation status bit, interrupt or error response anywhere in the block — the response channels are passed through verbatim (lines 2572, 2582), so a filtered access is indistinguishable from a legitimate one to both the BIO and the host.

**Evidence.**
```systemverilog
bio_bdma.sv:2543-2557 (comparison, and the 'allow' terms)
    generate
        for(genvar k = 0; k<RANGES; k = k + 1) begin: ranges
            always_comb begin
                // unchecked bounds
                bounds_unchecked[k] = base[k] + length[k];
                // bounds saturated at max_u32
                bounds[k] = bounds_unchecked[k] > 21'h0_FFFF_F ? 20'hFFFF_F : bounds_unchecked[k][19:0];
                match_write[k] = (s_axi_awaddr[31:12] >= base[k]) && (s_axi_awaddr[31:12] < bounds[k]);
                match_read[k] = (s_axi_araddr[31:12] >= base[k]) && (s_axi_araddr[31:12] < bounds[k]);
            end
        end
    endgenerate
    always_comb begin
        allow_write = |match_write | disable_filter;
        allow_read = |match_read | disable_filter;
    end

bio_bdma.sv:2560-2562, 2565, 2574-2576, 2579-2582 (redirect, not block; data passes both ways)
    assign m_axi_awvalid = s_axi_awvalid;
    assign s_axi_awready = m_axi_awready;
    assign m_axi_awaddr = allow_write ? s_axi_awaddr : gutter;
    ...
    assign m_axi_wvalid = s_axi_wvalid;
    ...
    assign m_axi_arvalid = s_axi_arvalid;
    assign s_axi_arready = m_axi_arready;
    assign m_axi_araddr = allow_read ? s_axi_araddr: gutter;
    ...
    assign s_axi_rvalid = m_axi_rvalid;
    assign m_axi_rready = s_axi_rready;
    assign s_axi_rdata = m_axi_rdata;
    assign s_axi_rresp = m_axi_rresp;

bio_bdma.sv:561-563 (the gutter is a plain unlocked CR, never range-checked)
    // this is part of address filtering, but stuck here because we're running out of bits
    apb_cr #(.A('hA0), .DW(32))      sfr_mem_gutter           (.cr(mem_gutter), .prdata32(),.*);
    apb_cr #(.A('hA4), .DW(32))      sfr_peri_gutter          (.cr(peri_gutter), .prdata32(),.*);
```

**Preconditions.** Write access to 0x501240A0/0x501240A4 (unlocked — see the sfrlock finding) and the ability to run a BIO program. No whitelist entry, no DISABLE_FILTER bit and no debug mode required. Reachability of a given gutter address is bounded by the downstream fabric decode: the memory gutter reaches ReRAM/SRAM/QFC via nic400, the peripheral gutter reaches all of 0x4000_0000-0x5FFF_FFFF via bmx33.

**Attack scenario.** With the whitelist entirely empty (the documented "access disabled" configuration) an attacker writes 0x603F_0000 to SFR_MEM_GUTTER at 0x501240A0 — a single 32-bit APB store, no whitelist window and no DISABLE_FILTER bit touched. A BIO program then reads any address at all in 0x6000_0000-0x7FFF_FFFF; every such read fails the whitelist, is re-addressed to 0x603F_0000, and returns the ReRAM key-slot word to the BIO core, which forwards it to the host through the BIO output FIFO at 0x50124020. Sweeping the gutter register across a range of addresses gives word-by-word read-out of any region the BDMA master reaches; the same applies to writes. On the peripheral side, writing 0x4000_00F0 to SFR_PERI_GUTTER at 0x501240A4 and having the BIO store 0x2468 to any out-of-range peripheral address triggers the ReRAM mass-erase action register (rrc.sv:286, `.sfrlock(1'b0)`) — a permanent denial of service — even though the whitelist is empty and the peri filter is nominally enforcing. Because the gutter register is not part of the "whitelist" in the documentation's or an auditor's mental model, a firmware review that verifies the four base/bounds pairs and the two DISABLE_FILTER bits will not catch this. It also means a well-behaved system that sets a scratch gutter has to treat that scratch address as attacker-writable and attacker-readable, which the documentation does not say.

**Mitigation.** RTL fix: on a filter miss, suppress the transfer and synthesise a SLVERR response locally instead of re-addressing (i.e. deassert `m_axi_awvalid`/`m_axi_arvalid` and drive `s_axi_bresp`/`s_axi_rresp` = 2'b10 from a small local response FSM), and add a sticky violation status bit plus an interrupt so the host can observe attempts. If the gutter concept is retained, run the gutter address through the same `match_*` comparison so it cannot point outside the whitelist. Software workaround on fabricated silicon: at the earliest boot stage, program both SFR_MEM_GUTTER (0x501240A0) and SFR_PERI_GUTTER (0x501240A4) to a harmless dedicated scratch page that is inside a whitelist window and contains nothing sensitive, and then protect 0x5012_4000-0x5012_40FF from all non-boot code — but note this is only effective if the register cannot subsequently be rewritten, which the hardware does not enforce.

**Verification.** Independently confirmed by a second reviewer. The RTL behaves exactly as described. axil_filter (bio_bdma.sv:2543-2583) never deasserts a valid: :2560 `assign m_axi_awvalid = s_axi_awvalid;`, :2562 `assign m_axi_awaddr = allow_write ? s_axi_awaddr : gutter;`, :2565 `assign m_axi_wvalid = s_axi_wvalid;`, :2579 `assign m_axi_araddr = allow_read ? s_axi_araddr: gutter;`, :2581 `assign s_axi_rdata = m_axi_rdata;`, :2572/:2582 pass bresp/rresp through verbatim. The gutter is a plain apb_cr at :562-563 and is not run through the match_* comparison, so it is genuinely filter-exempt: a contained BIO program (one that controls only the instruction RAM, not the SFRs) gets a one-page read/write aperture at whatever address firmware picked, outside the whitelist, and reads from it return live bus data rather than zeros. There is no violation status bit, interrupt, or SLVERR anywhere in the block — I checked the whole SFR bank and the response paths.

**Corrections applied by the verifier.** The documentation claim is overstated and must be fixed before this goes to the vendor: ch02-00-bio-overview.md:1280 and :1294 explicitly document the redirect — "Sets the physical address for the DMA 'gutter' on memory-range accesses. Any attempt to access addresses that are not in the whitelist are routed to the gutter." The redirect is intended behavior, not a hidden bug. The finder's attack scenario also does not escalate: an attacker who can write SFR_MEM_GUTTER at 0x501240A0 can equally write SFR_FILTER_BASE_0 at 0x501240E0, so pointing the gutter at ReRAM buys nothing over just whitelisting ReRAM. Severity lowered from high to medium, and the defensible core should be restated as: (a) the gutter address is not itself range-checked, so it is an escape hatch for a BIO program that is otherwise correctly confined by a firmware-set whitelist, and reads return real data rather than a bit-bucket; (b) the filter has no deny primitive and no violation reporting, so an out-of-range access is indistinguishable from a legitimate one to both the BIO and the host, defeating any attempt to detect a misbehaving BIO program; (c) the reset value of both gutter registers is 0x0000_0000, an address decoded by neither crossbar window.

---

<a id="bao-069"></a>

### BAO-069 — Whitelist, gutter and DISABLE_FILTER policy registers are write-only — their prdata32 outputs are omitted from the APB read mux, so software always reads back zero and cannot audit or safely modify the BDMA containment policy

**Severity: Medium**

**Location:** `rtl/modules/bio_bdma/rtl/bio_bdma.sv:461`

*Surfaced by the independent verifier, not the original domain reviewer.*

**Description.** The APB read data for the bio_bdma SFR bank is built as one explicit OR-reduction at bio_bdma.sv:461-500. That list omits sfr_mem_gutter, sfr_peri_gutter and all eight sfr_filter_base_*/sfr_filter_bounds_* instances (it also omits sfr_dbg_padout and sfr_dbg_padoe). Every one of those instantiations additionally leaves the .prdata32 output unconnected — `(.cr(filter_base[0]), .prdata32(),.*)`. Nothing else drives apbx.prdata, so a read of 0x501240A0, 0x501240A4 or 0x501240E0-0x501240FC returns 0x00000000 regardless of what has been programmed. The vendor documentation acknowledges the FILTER half of this as a known erratum (ch02-00-bio-overview.md: "there is a bug in the Baochip-1x which prevents the FILTER series of registers from being read back") but does not state the root cause, does not mention that the two GUTTER registers have the identical defect, and does not draw the security consequence. The consequence is that the entire BDMA containment policy is write-only in silicon: it cannot be verified, attested, or read-modify-written. Any defensive firmware routine that reads the whitelist to confirm the BIO is contained observes all-zero, which is exactly the encoding of the documented safe state ("By default, all base/bounds are set to 0, which effectively disables BIO DMA access"), so an attacker-programmed wide-open window is indistinguishable from a locked-down chip. Combined with the absent lock bit and the absent violation status bit, there is no hardware means whatsoever — neither prospective nor retrospective — for privileged software to establish what the BDMA is currently permitted to reach.

**Evidence.**
```systemverilog
bio_bdma.sv:461-500 (the complete read mux; sfr_filter_*, sfr_mem_gutter, sfr_peri_gutter are absent)
    assign  apbx.prdata = '0 |
            sfr_ctrl         .prdata32 |
            sfr_config       .prdata32 |
            ...
            sfr_dmareq_map   .prdata32 |
            sfr_dmareq_stat  .prdata32
            ;

bio_bdma.sv:562-563 (gutters: .prdata32 left unconnected)
    apb_cr #(.A('hA0), .DW(32))      sfr_mem_gutter           (.cr(mem_gutter), .prdata32(),.*);
    apb_cr #(.A('hA4), .DW(32))      sfr_peri_gutter          (.cr(peri_gutter), .prdata32(),.*);

bio_bdma.sv:620-627 (whitelist: .prdata32 left unconnected)
    apb_cr #(.A('hE0), .DW(20))      sfr_filter_base_0        (.cr(filter_base[0]), .prdata32(),.*);
    apb_cr #(.A('hE4), .DW(20))      sfr_filter_bounds_0      (.cr(filter_bounds[0]), .prdata32(),.*);
    ...
    apb_cr #(.A('hFC), .DW(20))      sfr_filter_bounds_3      (.cr(filter_bounds[3]), .prdata32(),.*);

docs/src/ch02-00-bio-overview.md (FILTER_BASE_0 section)
    By default, all base/bounds are set to 0, which effectively disables BIO DMA access to the rest of the system.
    NOTE: there is a bug in the Baochip-1x which prevents the `FILTER` series of registers from being read back.
```

**Attack scenario.** A secure-boot or runtime-attestation routine wants to prove the BIO is contained before handing control to a less-trusted stage. It reads 0x501240E0-0x501240FC and 0x501240A0/A4, observes all zeros, and concludes the whitelist is empty and both gutters are benign — the documented safe configuration. In fact an earlier attacker-controlled write may have programmed filter_base[0]=0x60000 / filter_bounds[0]=0xFFFFF (whitelisting all of ReRAM, which per the AMBAID finding gives the BDMA an unchecked path to the ReRAM ACRAM at 0x603D_C000) and pointed the memory gutter at a key slot. The attestation cannot see any of it. Symmetrically, defensive firmware that tries to narrow a window with a read-modify-write reads 0, ORs in its new bits, and silently destroys the other three windows' configuration without any error indication.

**Verification.** No independent verdict recorded for this entry.

---

<a id="bao-070"></a>

### BAO-070 — Inter-CPU mailbox endpoint has no access control at all: any bus master can forge messages into, and destructively drain messages out of, the CM7<->Vex channel

**Severity: Medium** | CWE-1262 Improper Access Control for Register Interface | Threat actor: T1 (unprivileged software on either CPU is sufficient); also reachable by any DMA master under T1 control | Confidence: High

**Location:** `rtl/modules/mbox/rtl/mbox.sv:104`

**Description.** `mbox_apb` is the sanctioned channel between the two CPUs. It is mapped on the coresub APB at 0x4001_3000 (soc_coresub.sv:467-468 binds it to `coresubapbs[3]`; `apb_mux #(.PAW(16),.DECAW(4))` at soc_coresub.sv:649 decodes paddr[15:12], and the base 0x4001_0000 comes from `coreahb_demux_map` entry idx 1 in daric_cfg_pkg.sv:54; confirmed independently by verilate/bao_common.py:112 `"mbox_apb" : [0x4001_3000, 0x0_1000]`).

The module hard-ties its own write-protect to zero (line 104) and performs NO check on who is issuing the access. It cannot perform one even if it wanted to: the transaction has already crossed `apb_bdg` (amba_components.sv:935-985), and `apbif` (amba_interface_def.sv:365-380) has no user/master-id field whatsoever - hauser/hwuser simply do not exist on APB. `pprot` does survive the bridge and is forwarded by `apb_mux` (amba_components.sv:311), but I verified by grep that no APB slave in this SoC consumes `pprot`, and `mbox_apb` does not reference it.

The consequence is that both directions of the channel are open to anyone on the core AHB. Writing 0x4001_3000 injects a word into the CM7->Vex stream that the Vex will attribute to the CM7's firmware. Worse, reading 0x4001_3004 is DESTRUCTIVE: `sfr_rdata` is an `apb_asr` whose read strobe becomes `mbox_r_ready`, which is wired straight to the read-enable of the Vex's transmit FIFO. So a single load instruction from any agent both reads and permanently removes a word of the Vex->CM7 message. Writes to 0x4001_3018 / 0x4001_301C likewise let an unrelated agent assert abort/done on the CM7's behalf.

**Evidence.**
```systemverilog
rtl/modules/mbox/rtl/mbox.sv:103-115
```
    logic apbrd, apbwr, sfrlock;
    assign sfrlock = '0;
    `apbs_common;
    assign  apbx.prdata = '0 |
            sfr_wdata         .prdata32 |
            sfr_rdata         .prdata32 |
            sfr_status        .prdata32;

    apb_acr #(.A('h0), .DW(32))      sfr_wdata             (.cr(wdata), .ar(wdata_written), .prdata32(),.*);
    apb_asr #(.A('h4), .DW(32))      sfr_rdata             (.sr(rdata), .ar(rdata_read), .prdata32(),.*);
    apb_asr #(.A('h8), .DW(6) )      sfr_status            (.sr({rx_err, tx_err, abort_ack, abort_in_progress, tx_free, rx_avail}), .ar(status_read), .prdata32(),.*);
    apb_ar  #(.A('h18), .AR(32'h1))  sfr_abort             (.ar(abort),.*);
    apb_ar  #(.A('h1C), .AR(32'h1))  sfr_done              (.ar(done),.*);
```

The read is a destructive pop - rtl/modules/mbox/rtl/mbox_client.v:269-270
```
assign sfr_sr_rdata = mbox_r_dat;
assign mbox_r_ready = (sr_rdata_read_aclk & (~rdata_read_r));
```
and on the peer side, rtl/modules/vexriscv/rtl/cram_axi.sv:5632, :5607, :12745
```
        w_ready <= mbox_r_ready;
...
assign mailbox_w_ready = w_ready;
...
assign mailbox_syncfifobufferedmacro0_syncfifobufferedmacro0_re = mailbox_w_ready;
```

APB carries no identity - rtl/modules/common/rtl/amba_interface_def.sv:365-380
```
interface apbif #(
    parameter PAW=16,
    parameter DW=32
)();

    wire               psel;
    wire   [PAW-1:0]    paddr;
    wire               penable;
    wire               pwrite;
    wire   [3:0]       pstrb;
    wire   [2:0]       pprot;
    bit    [31:0]      pwdata;
```
(no hauser/coreuser equivalent), and the bridge that discards it - rtl/modules/amba/rtl/amba_components.sv:967-973
```
       .PADDR         ( apbmaster.paddr         ),     // APB Address
       .PENABLE       ( apbmaster.penable       ),// APB Enable
       .PWRITE        ( apbmaster.pwrite        ),// APB Write
       .PSTRB         ( apbmaster.pstrb         ),// APB Byte Strobe
       .PPROT         ( apbmaster.pprot         ),// APB Prot
       .PWDATA        ( apbmaster.pwdata        ),// APB write data
       .PSEL          ( apbmaster.psel          ),// APB Select
```

**Preconditions.** The ability to issue a single load or store to 0x4001_3000-0x4001_301C. Given that the CM7 MPU configuration is unverifiable in this repo (daric_cfg::CM7CFG is inside a comment block at daric_cfg_pkg.sv:116-128 while soc_coresub.sv:321 references it), and that neither the coreuser tag nor pprot is checked anywhere on this path, this is available to unprivileged software on either CPU, to any SCE DMA channel, and to the BDMA. No lock bit exists to close it.

**Attack scenario.** Message theft: 1. The Vex's secure task computes a result (e.g. a derived key, a PIN-verification verdict, a signature) and pushes it word by word into its mailbox TX FIFO, expecting the CM7's secure firmware to drain it. 2. Attacker code polls 0x4001_3008 for rx_avail and then executes `LDR r0,[0x4001_3004]`. That single load returns the head word AND asserts mbox_r_ready, popping it out of the Vex's FIFO. 3. The attacker repeats until the FIFO drains, obtaining the whole message. The CM7's legitimate consumer never sees it and cannot tell it was taken - reading 0x4001_3004 on an empty FIFO returns stale `mbox_r_dat` with only an error status bit that is itself mis-wired (see the rx_err/tx_err swap finding).\n\nMessage forgery: 1. Attacker writes a crafted word to 0x4001_3000. 2. `mbox_client` drives it onto mbox_w_dat/mbox_w_valid, the Vex's RX FIFO accepts it, and the Vex's secure task processes it as a command issued by the CM7's boot/firmware region. There is no sender identity anywhere in the datapath for the Vex to check.\n\nDenial/desync: writing 0x2468-style action registers is not needed here - a single write of 0x1 to 0x4001_3018 (`sfr_abort`) forces the abort FSM, and on the peer side `mailbox_w_fifo_reset_sys = ((~mailbox_reset_n) | mailbox_abort)` and `mailbox_r_fifo_reset_sys` (cram_axi.sv:12727, :12750) flush BOTH FIFOs, discarding an in-flight message.\n\nRelevant masters: the CM7 AHB-P port and the Vex AHB-P port both reach core_ahb32 via bmx33s[2] (bmxcore.sv:270) and the 0x4001_0000 demux slot (soc_coresub.sv:626-643), so the Vex can drive the CM7's mailbox endpoint and vice-versa. The SCE DMA's AHB path (bmxcore.sv:138-148, bmx33s[0]) covers 0x0000_0000-0x5FFF_FFFF with fully software-chosen addresses and no whitelist, so an SCE DMA channel can be programmed to stream 0x4001_3004 straight into SCERAM. The BDMA peripheral AHB master (bmx33s[1] via bmxcore.sv:225-233) reaches the same space with hauser hard-tied to 0.

**Mitigation.** RTL: extend `apbif` with a user/coreuser sideband (or, at minimum, wire `hauser` through `apb_bdg` into a per-slave qualifier) and gate mbox_apb's `apbwr`/`apbrd` on it, so that only the CM7's own port may touch the CM7-side endpoint; drive `sfrlock` from a real, one-way-settable lock rather than `assign sfrlock = '0;`. Separately, make 0x4001_3004 non-destructive on read and require an explicit pop action register, so that a stray or speculative read cannot consume a message. As an interim, at least honour `pprot[0]` (privileged) on the wdata/rdata/abort registers.\nFirmware workaround on fabricated silicon: the mailbox must be treated as an untrusted, unauthenticated transport. Every message must carry an application-layer MAC keyed by a secret shared only between the two secure firmwares, plus a monotonic sequence number, so that forged words are rejected and stolen/dropped words are detected. Confidential payloads must be encrypted before being placed in the mailbox - never send raw key material or PIN verdicts through it. If the platform can be configured to do so, place the 4 KB page at 0x4001_3000 outside every unprivileged MPU/PMP region on both CPUs and forbid SCE-DMA and BDMA descriptors that name addresses in 0x4001_0000-0x4001_FFFF.

**Verification.** Verified as written; exploitability not fully established. Verified mbox.sv:103-115 verbatim, including `assign sfrlock = '0;` at line 104 and the register bank at 111-115. Verified mbox_client.v:269-270 verbatim: `assign sfr_sr_rdata = mbox_r_dat;` / `assign mbox_r_ready = (sr_rdata_read_aclk & (~rdata_read_r));`. I traced the read-pop mechanism to its source: mbox.sv:183-238 defines apb_asr, whose `ar` output is `theregfull(pclk,resetn,ar,'0) <= sfrapbrd;` driven by apb_sfrop2's read strobe - so a plain load from 0x4001_3004 does assert mbox_r_ready and pop the peer FIFO. Destructive read confirmed.
Verified apbif carries no user/master-id field (amba_interface_def.sv:365-380 - psel, paddr, penable, pwrite, pstrb, pprot, pwdata only) and that apb_bdg (amba_components.sv:935-985) forwards PPROT but nothing else. I independently grepped every pprot reference in rtl/ (excluding testbench): the only hits are apb_sfr.sv:270 and amba_components.sv:538 (`assign apbmaster.pprot = 0` in null masters), amba_components.sv:311/455/487/1067 (pure pass-through), the interface declarations, and BIO wrapper port maps. No APB slave anywhere consumes pprot for access control. Confirmed.
Verified addressing: daric_cfg_pkg.sv:54 `'{idx: 32'd1 , start_addr: 32'h4001_0000, end_addr: 32'h4002_0000}` feeds soc_coresub.sv:643 `apb_bdg #(.PAW(16)) u1(.ahbslave(coreahbmux[1]),.apbmaster(coresubapb),...)`; soc_coresub.sv:649 `apb_mux #(.PAW(16),.DECAW(4))` decodes paddr[15:12]; soc_coresub.sv:467-468 binds mbox_apb to coresubapbs[3] => 0x4001_3000. Matches verilate/bao_common.py:112.
Verified master reach: rtl/modules/bmxcore/rtl/bmxcore.sv:268 `ahb_thru bmx33s2 ( .ahbslave(cm7_ahbp), .ahbmaster( bmx33s[2] ));` with cm7_ahbp = core_ahbp = ahb_mux3 of {cm7_ahbp, vex_ahbp} (soc_coresub.sv:612-624), bmx33s[0] = sce_ahb from the SCE's axi_ahb_bdg (bmxcore.sv:139-147), bmx33s[1] = bdma/mdma mux (bmxcore.sv:225-233), all feeding bmx33m[1] -> core_ahb32 -> coreahb_mux. So the routing claim holds.
I checked for compensating controls and found none on this path: coreuser exists in the design but is consumed only by sce_sec.sv:61-73 and rrc.sv; there is no coreuser or hauser qualifier anywhere between core_ahb32 and mbox_apb, and sfrlock is hard-zero. There is no lock bit to close it. The only thing separating unprivileged code from the mailbox is CPU-side MPU/PMP configuration, which is not in this repo - hence plausible rather than confirmed.

**Corrections applied by the verifier.** Every code fact asserted is correct and I reproduced all of them. What is not established is the exploitability premise: nothing in this repository shows that unprivileged code can actually reach 0x4001_3000 - that depends on CM7 MPU / Vex PMP configuration held in firmware. Note also that the Vex reaching the CM7-side endpoint is largely self-harm (writing 0x4001_3000 pushes into the Vex's own RX FIFO; reading 0x4001_3004 drains the Vex's own TX FIFO), so the cross-CPU forgery narrative is weaker than stated. The real content is 'no hardware defence-in-depth on the inter-CPU channel, plus a destructive-on-read register', which is medium, not high. Minor citation errors: bmxcore is at rtl/modules/bmxcore/rtl/bmxcore.sv (not rtl/modules/soc_coresub/rtl/), and the cited lines are approximate (bmx33s2/cm7_ahbp is at line 268, the SCE axi_ahb_bdg at 139-147, the DMA mux at 225-233).

---

<a id="bao-071"></a>

### BAO-071 — ahb_ar silently ignores its sfrlock write-protect input, so the ReRAM mass-erase trigger can never be locked

**Severity: Medium**

**Location:** `rtl/modules/amba/rtl/ahb_sfr.sv:340`

*Surfaced by the independent verifier, not the original domain reviewer.*

**Description.** `ahb_ar` is the AHB action-register primitive in the shared AMBA SFR library. It declares a `sfrlock` write-protect input at line 294 but never references it anywhere in the module body: the write enable at line 340 is built only from the address decode, and the action pulse at line 344 fires on any matching write. This is unique among the SFR primitives in this library - `ahb_cr`, `ahb_sr` and `ahb_fr` all pass sfrlock down to `ahb_sfr2`, which applies it at line 256 (`assign reg_write_en = ~sfrlock & reg_write_en0;`), and the APB twin `apb_ar` (apb_sfr.sv:234-262) applies it via `apb_sfrop2` (apb_sfr.sv:378). `ahb_ar` is the only one that drops it. Consequently there is no way, ever, to write-protect an ahb_ar action register: the input exists and is silently discarded. The design's only instance of ahb_ar is the ReRAM mass-erase (`suicide`) trigger in the ReRAM controller, rrc.sv:286, which also passes `sfrlock(1'b0)` - so today the behaviour is identical, but the RTL removes the ability to fix it with a lock bit, and it removes the one write-protect hook that a firmware or ECO could have used to gate the single most destructive register in the SoC.

**Evidence.**
```systemverilog
rtl/modules/amba/rtl/ahb_sfr.sv:286-345 (sfrlock is a port, never used)
```
module ahb_ar #(
        parameter AW=12,
        parameter A=0,
        parameter AR=32'h5a
     )(
        input  logic  hclk,
        input  logic  resetn,
        ahbif.slavein                       ahbs        ,
        input  bit                          sfrlock     ,
...
    assign sfrsel = ( reg_addr[AW-1:0] == A[AW-1:0] );
    assign reg_write_en = reg_write_en0 & sfrsel;

    `theregfull(hclk, resetn, ar, '0) <= reg_write_en & ( reg_wdata == AR );
```
Contrast, the same library's ahb_sfr2 which does honour it - rtl/modules/amba/rtl/ahb_sfr.sv:256
```
    assign reg_write_en = ~sfrlock & reg_write_en0;
```
and the APB twin which does honour it - rtl/modules/amba/rtl/apb_sfr.sv:378
```
    assign apbwr = ~sfrlock & apbslave.psel & apbslave.penable & apbslave.pwrite & sfrsel;
```
The sole instantiation in the design - rtl/modules/rrc/rtl/rrc.sv:256 and :286
```
    localparam PM_RRAM_SUICIDE = 16'h2468;
...
    ahb_ar #(.A('hF0), .AR(PM_RRAM_SUICIDE))    sfr_rrcar       (.ar(rrcar_suicide), .resetn(coreresetn), .sfrlock(1'b0), .*);
```
and what that pulse does - rtl/modules/rrc/rtl/rrc.sv:307
```
    `theregfull(clktop, sysresetn, suicide_start, '0) <= ((cmscode == CMS_SCDE) | rrcar_suicide) & (!suicide_reg) & (!suicide_start) & (suicide_adr_main == 'h0) ? 1'b1 :
```

**Attack scenario.** A single 32-bit store of 0x2468 to the RRC action register at 0x4000_00F0 (RRC is coreahb_demux_map idx 0, daric_cfg_pkg.sv:55, base 0x4000_0000) asserts rrcar_suicide, which starts the ReRAM erase walk over the whole main array and then the IFR (rrc.sv:307-322). There is no lock bit, no coreuser qualifier on this register, no magic-sequence beyond the single 0x2468 value, and - because ahb_ar discards sfrlock - no way to add one without an RTL change. Any AHB master that can reach 0x4000_00F0 (CM7 AHB-P, Vex AHB-P via the same core_ahbp mux, the SCE DMA's AHB path, or the BDMA/MDMA peripheral master) permanently bricks the device. The absent sfrlock also means that even if firmware wanted to lock the register down after boot - the pattern used everywhere else in this library - the hardware would ignore it.

**Verification.** No independent verdict recorded for this entry.

---

<a id="bao-072"></a>

### BAO-072 — ReRAM one-way (monotonic/anti-rollback) counters can be incremented by any bus master with no access-control check whatsoever

**Severity: Medium** | CWE-1233 Security-Sensitive Hardware Controls with Missing Lock Bit Protection | Threat actor: T1 (unprivileged software on either CPU); also reachable from T3 if an external peripheral can drive the BIO/BDMA, whose whitelist registers at 0x5012_40E0+ are themselves unlocked. | Confidence: High

**Location:** `rtl/modules/rrc/rtl/rrc.sv:576`

**Description.** The RRC implements one-way counters at 0x603D_A000 and 0x603D_B000 as a read-modify-program sequence. A write to that region is detected by `oneway_counter_update_ahb` (rrc.sv:496-497) and is deliberately excluded from the normal write path: `ahb_array_write` masks it (rrc.sv:539) and, critically, `ahb_write_flag` is forced to 0 for such a transfer (rrc.sv:546). Since all five access-error terms (`key_access_error_pre` rrc.sv:712, `data_access_error_pre` rrc.sv:722, `code_access_error_*` rrc.sv:770-774, `info_access_error_pre` rrc.sv:781-782, `cfg_access_error_pre` rrc.sv:818-819) are qualified by `ahb_read_flag` and/or `ahb_write_flag`, they all evaluate identically to 0 for a counter update. Address decode confirms no region check applies either: `keysel`/`datasel` require 0x603F/0x603E, `codesel = (haddr_reg[31:12] < 20'h603D_A)` is false for 0x603DA/0x603DB, the CFG region requires haddr_reg[15:14]==2'b11, and `axi_info = haddr_reg[22]` is 0. Independently, the two-cycle sequencing explicitly bypasses `cmd_user_write_dis` for the counter branch while correctly applying it to the adjacent prog-only-data branch in the very same expression (rrc.sv:576-577). The result is that the increment reaches TRC_LOAD/TRC_WRITE unconditionally. Separately, the event-driven counter-burn path is disabled at reset: `oneway_counter_update_ev = |(evin_trigger[15:0] & rrccr[31:16])` (rrc.sv:513) and rrccr is `ahb_cr_ECO #(.A('h00), .DW(32))` whose IV defaults to 32'h0 (rrc.sv:274, 1144), on an SFR with `.sfrlock(1'b0)`.

**Evidence.**
```systemverilog
rrc.sv:496  assign oneway_counter_update_ahb = ahb_array_trans & ahbarray.hwrite & ahbarray.hsel
rrc.sv:497                                      & (ahbarray.haddr[23:16] == 8'h3D) & (ahbarray.haddr[15:13] == 3'b101);    // 3D_Axxx | 3D_Bxxx One-way counter region
rrc.sv:546  `theregfull(clktop, coreresetn, ahb_write_flag, '0) <= ahb_array_trans ? ahbarray.hsel & ahbarray.hwrite & (!oneway_counter_update_ahb) : ahb_write_flag;
rrc.sv:547  `theregfull(clktop, coreresetn, ahb_read_flag, '0) <= ahb_array_trans ? ahbarray.hsel & !ahbarray.hwrite : ahb_read_flag;
rrc.sv:575  assign two_cycle_read = ( rrcfsm == 0 ) & (oneway_counter_update | prog_only_data_write);
rrc.sv:576  assign two_cycle_load = ( rrcfsm == 1 ) & trc_dout_ready_done & (oneway_counter_write_reg | (prog_only_data_write_reg & (!cmd_user_write_dis)));
rrc.sv:577  assign two_cycle_write = ( rrcfsm == 3 ) & rramclken & (oneway_counter_write_reg | (prog_only_data_write_reg & (!cmd_user_write_dis)));
rrc.sv:868                      oneway_counter_write_reg ? (ahb_rd_buf + 'h1) :
--- the event path that could have made this self-defending is off at reset ---
rrc.sv:513  assign oneway_counter_update_ev = |(evin_trigger[15:0] & rrccr[31:16]);
rrc.sv:274  ahb_cr_ECO #(.A('h00), .DW(32))                 sfr_rrccr       (.cr(rrccr), .hrdata32(), .resetn(coreresetn), .sfrlock(1'b0), .*);
rrc.sv:1144       parameter IV=32'h0,
```

**Preconditions.** Write access to any address in 0x603D_A000-0x603D_BFFF on the ReRAM AXI slave. Available to the CM7 AXI master, both Vex AXI masters, both SCE DMA masters, and the BIO/BDMA AXI master. No privilege level, no coreuser value, and no AxPROT setting is required — the checks are structurally bypassed, not merely permissive. `brdone` must be set (boot read complete), which is always true in normal operation.

**Attack scenario.** 1. Unprivileged code on the CM7 or Vex (or the BDMA, whose AXI master reaches the ReRAM via nic400 .m0 per bmxcore.sv:199,292) performs a single store of any value to 0x603D_A000 (or any 32-byte-aligned offset up to 0x603D_BFFF).
2. `oneway_counter_update_ahb` asserts. `ahb_write_flag` and `ahb_read_flag` are both driven to 0 for this transfer, so key/data/code/info/cfg access-error logic is inert; `cmd_user_write_dis` is 0.
3. rrcfsm 0->1 reads the current 256-bit counter word into `ahb_rd_buf`; `two_cycle_load` (unqualified by cmd_user_write_dis) takes rrcfsm 1->3 with `axi_din = ahb_rd_buf + 'h1`; `two_cycle_write` takes rrcfsm 3->4 and programs the incremented value into ReRAM.
4. Repeat in a loop. Each iteration permanently advances a counter that is, by name and by construction (read-modify-increment, program-only, no decrement path — a direct write to the region is intercepted by step 2 and never reaches `ahb_wr_buf`), intended to be monotonic and therefore intended to be irreversible.
Impact depends on what the counters are used for, but the only sensible uses are anti-rollback / secure-version, provisioning-attempt limits, or tamper-event accounting. Advancing the secure-version counter past the version of the installed firmware permanently bricks the device (the installed image now fails its own anti-rollback check) — an unprivileged, one-instruction, unrecoverable DoS on a fabricated part. If a counter gates a provisioning or lifecycle transition, an attacker can burn through it to force a state change. Conversely, because `rrccr[31:16]` resets to 0 and lives in an unlocked SFR, an attacker can clear it to stop genuine security events (evc.sv:90 `rrc_ev[m] <= rrc_even[m] & evin[rrc_evsel[m]]`) from ever burning a counter — so the counters are simultaneously freely advanceable by an attacker and not advanced by real tamper events unless software opted in.

**Mitigation.** RTL fix: evaluate the access-control checks for the one-way counter region instead of suppressing them. Concretely, (a) do not force `ahb_write_flag` to 0 for counter transfers at rrc.sv:546 — use a separate qualifier so the error logic still sees a write; (b) add a dedicated region term (e.g. `onewaysel = (haddr_reg[31:13] == {16'h603D,3'b101})`) to the access-error expressions, minimally requiring `coreuser_in[5]|coreuser_in[4]` (boot0/boot1) and `pri_op`/`vex_mm_reg` exactly as `cfg_prev_dis` does at rrc.sv:815; and (c) qualify the counter branch of rrc.sv:576-577 with `(!cmd_user_write_dis)` for symmetry with the prog_only_data branch on the same lines. Also give `rrccr[31:16]` a write-once lock so the event-driven burn cannot be disabled after boot, and give it a non-zero (fail-safe) reset value.
Firmware workaround on fabricated silicon: none within the RRC. The only containment is to deny all non-boot code access to 0x603D_A000-0x603D_BFFF via the CM7 MPU / Vex PMP (the CM7 MPU config at daric_cfg_pkg.sv:117-127 is currently commented out and must be enabled), and to have boot0 set rrccr[31:16] before handing off. Systems relying on these counters for anti-rollback should treat them as untrusted against a compromised application core.

**Verification.** Independently confirmed by a second reviewer. Quotes are verbatim (rrc.sv:496-497, 546, 575-577, 868, 513, 274, 1144). I re-derived the bypass independently rather than taking the finder's word. For a store to 0x603D_A000: `oneway_counter_update_ahb`=1, so rrc.sv:546 drives `ahb_write_flag<=0` and rrc.sv:547 gives `ahb_read_flag<=0` (hwrite=1). I then checked each of the five error terms against that address rather than assuming: key needs `keysel` (haddr[31:16]==0x603F) = 0; data needs `datasel` (==0x603E) = 0; `codesel = (haddr_reg[31:12] < 20'h603D_A)` is false for 0x603DA/0x603DB; `axi_info = haddr_reg[22]` = 0 for 0x603D_A000; cfg needs haddr[15:14]==2'b11 but 0x603DA/B give haddr[15:14]==2'b10. So all five are structurally 0, not merely permissive — the finder is right. The one term in key_access_error_pre that is NOT flag-qualified (`!trustkey[akeyid] & (haddr_reg[15:6] != 10'h0)`, rrc.sv:717) is still killed by `& keysel`. rrc.sv:576-577 do apply `(!cmd_user_write_dis)` to `prog_only_data_write_reg` but not to `oneway_counter_write_reg`, exactly as quoted. The FSM path 0->1(read)->3(LOAD, axi_din=ahb_rd_buf+1)->4(WRITE) is reachable with a single store; rrccr[1] is not even required. No compensating control exists.

**Corrections applied by the verifier.** Overstated at 'high'. The primitive is real and unauthenticated, but the impact is entirely firmware-dependent (nothing in this repo shows what the counters gate) and it is destroy-only — no secret is disclosed and no access control is bypassed. Also, rrc.sv:547 does not 'force' ahb_read_flag to 0 for the counter write; it is 0 simply because hwrite=1. I would report this as an unauthenticated permanent-state-advance / DoS primitive, not as an anti-rollback break, since anti-rollback usage is assumed rather than shown.

---

<a id="bao-073"></a>

### BAO-073 — An event-driven one-way-counter burn that lands one cycle before a ReRAM access converts that access into an unchecked read-modify-write of the accessed address

**Severity: Medium**

**Location:** `rtl/modules/rrc/rtl/rrc.sv:541`

*Surfaced by the independent verifier, not the original domain reviewer.*

**Description.** The event-triggered counter path is supposed to redirect the operation to a counter address, but the address register gives priority to a concurrently arriving AHB transfer while the counter mode flag is latched unconditionally. rrc.sv:541-542 select `ahbarray.haddr` over the counter address whenever a new transfer is accepted, whereas rrc.sv:516-517 set `oneway_counter_write_reg` from `oneway_counter_update` with no such arbitration. If `oneway_counter_update_ev` (rrc.sv:513) is high in the same cycle that a new ReRAM transfer is accepted, the machine ends up with haddr_reg = the requester's address and oneway_counter_write_reg = 1. rrc.sv:575 then drives rrcfsm to 1 (read of the requester's address), rrc.sv:576 `two_cycle_load` fires on `oneway_counter_write_reg` — with no `(!cmd_user_write_dis)` qualifier, unlike the prog_only branch on the same line — taking rrcfsm to 3 (TRC_LOAD) with `axi_din = ahb_rd_buf + 'h1` (rrc.sv:868), and rrc.sv:577 takes it to 4 (TRC_WRITE) at `axi_xadr = haddr_reg[21:10]` / `axi_yadr = haddr_reg[9:5]` (rrc.sv:871-872). The requester's target word is permanently reprogrammed to value+1, and because the whole oneway branch is exempt from `cmd_user_write_dis`, no key/data/code/info/cfg check is consulted for that write. The event source is fully software-selectable and the enable mask is unlocked: evc.sv:90 `rrc_ev[m] <= rrc_even[m] & evin[rrc_evsel[m]]` with evc.sv:160-161 `apb_cr ... sfr_rrcevsel` / `sfr_rrceven`, and rrc.sv:513 ANDs against `rrccr[31:16]` in the unlocked `sfr_rrccr` (rrc.sv:274, `.sfrlock(1'b0)`).

**Evidence.**
```systemverilog
rrc.sv:508             `theregfull(clktop, coreresetn, evin_trigger[j],  '0) <= evin_trigger[j] ? 1'b0 :
rrc.sv:509                                                                     ahbarray.hready & clken & (!(ahbarray.htrans[1] & ahbarray.hsel)) ? evin_reg[j] : evin_trigger[j];
rrc.sv:513     assign oneway_counter_update_ev = |(evin_trigger[15:0] & rrccr[31:16]);
rrc.sv:516     `theregfull(clktop, coreresetn, oneway_counter_write_reg, '0) <= oneway_counter_update ? 1'b1 :
rrc.sv:517                                                                         ( rrcfsm == 0 ) ? 1'b0 : oneway_counter_write_reg;
rrc.sv:541     `theregfull(clktop, coreresetn, haddr_reg, '0) <= ahb_array_trans & ahbarray.hsel ? ahbarray.haddr :
rrc.sv:542                                                             oneway_counter_update_ev ? {20'h603D_B, 3'b111, oneway_counter_adr_ev} : haddr_reg;
rrc.sv:575     assign two_cycle_read = ( rrcfsm == 0 ) & (oneway_counter_update | prog_only_data_write);
rrc.sv:576     assign two_cycle_load = ( rrcfsm == 1 ) & trc_dout_ready_done & (oneway_counter_write_reg | (prog_only_data_write_reg & (!cmd_user_write_dis)));
rrc.sv:868                         oneway_counter_write_reg ? (ahb_rd_buf + 'h1) :
rrc.sv:871     assign axi_xadr = suicide_reg ? suicide_xadr : haddr_reg[21:10];
--- attacker-controlled event routing ---
rtl/modules/sec/rtl/evc.sv:90              `theregrn( rrc_ev[m] ) <= rrc_even[m] & evin[rrc_evsel[m]];
rtl/modules/sec/rtl/evc.sv:160    apb_cr #(.A('h90), .DW(EVCNTW*4), .REVY(1), .SFRCNT(RRCEVCNT/4))  sfr_rrcevsel  (.cr(rrc_evsel),   .prdata32(),.*);
```

**Attack scenario.** Attacker is unprivileged software with peripheral-bus access (T1).
1. Program evc sfr_rrcevsel/sfr_rrceven (evc.sv:160-161, unlocked APB CRs) to route a system event the attacker can raise on demand into rrc `evin[j]`, and set rrccr[31:16] bit j via the unlocked RRC_SFR_RRCCR at 0x4000_0000.
2. Keep the ReRAM AXI slave continuously busy so that `evin_trigger[j]` cannot arm (rrc.sv:509 requires `ahbarray.hready & !(htrans[1] & hsel)`), then raise the event so `evin_reg[j]` latches.
3. Release the bus for exactly one idle cycle — `evin_trigger[j]` arms at the end of that cycle — and present the target ReRAM transfer in the immediately following cycle. In that cycle both `ahb_array_trans` and `oneway_counter_update_ev` are high; rrc.sv:541 latches the attacker's address, rrc.sv:516 latches the counter-write mode, and rrc.sv:575 starts the two-cycle sequence.
4. The RRC reads the attacker-chosen word, adds 1, and programs it back with no access-control evaluation. The attacker repeats until the alignment lands (each miss is a harmless normal access), giving a permanent, unauthenticated corruption primitive against any ReRAM word — including boot0 code, key slots, and the CFG descriptor lines that back the ACRAM.
Even without an attacker, a genuine tamper event that coincides with a ReRAM access silently corrupts that access's target instead of incrementing the counter, which is itself a tamper-integrity defect. Fix: arbitrate the two sources — hold the event pending until rrcfsm==0 with no AHB transfer accepted in the same cycle, and qualify the oneway branch of rrc.sv:576-577 with `(!cmd_user_write_dis)` as the prog_only branch already is.

**Verification.** No independent verdict recorded for this entry.

---

<a id="bao-074"></a>

### BAO-074 — MDMA (pl230) is a fully unauthenticated bus master: its control registers have no lock and no privilege check, and its address map reaches the CM7's ITCM and DTCM

**Severity: Medium** | CWE-1189 Improper Isolation of Shared Resources on System-on-a-Chip (DMA master with no address whitelist or requester authentication) | Threat actor: T1 (unprivileged software on either CPU that can reach the coresub APB window), and any other AHB master that reaches core_ahb32 - including the BIO/BDMA AHB port whose hauser is hardwired 0 | Confidence: Medium

**Location:** `rtl/modules/core/rtl/mdma.sv:100`

**Description.** The MDMA wrapper hardwires its SFR lock to zero (`assign sfrlock = '0;`) and passes the pl230's own APB port straight through with no lock at all (`.psel(apbs_dma.psel)` etc., mdma.sv:71-76). No consumer of `hprot`/`pprot` exists anywhere on this path, so there is no privileged-vs-unprivileged distinction on the MDMA control interface. The MDMA then emits a constant, non-authenticating master tag `assign ahbm.hauser = AHBMID4 |'0;` = 4'h7, identical for every requester and identical to the value the BIO's BDMA AXI master emits (bio_bdma.sv:1360/1373 with the un-overridden default `AHBMID4 = daric_cfg::AMBAID4_MDMA`), so a downstream checker cannot tell who programmed the transfer. In rrc.sv the value 4'h7 matches none of `cm7sel`/`vexsel`/`scesel` (rrc.sv:666-668) and therefore falls through the defaultless mux at rrc.sv:670-671 to `coreuser_cm7`.
The MDMA's only containment is the address map in bmxcore. That map deliberately carves ReRAM out of the nic400 path with the comment `// to nic_1, but no ReRAM`, but the other rule sends the ENTIRE 0x0000_0000-0x5FFF_FFFF space to `ahb_bmx33`, whose master port 0 is the CM7's AHB slave port (`ahb_thru bmx33m0 ( .ahbslave(bmx33m[0]), .ahbmaster(cm7_ahbs ));`). 0x0000_0000-0x1FFF_FFFF is the CM7 ITCM and 0x2000_0000-0x3FFF_FFFF is the CM7 DTCM (daric_cfg_pkg.sv:65-66). The CM7's AHBS port is instantiated with `.AHBSPRI(1'b0)` (cm7sys.sv:530) and the CM7 MPU does not apply to AHBS traffic, so nothing in the design gates DMA access to the TCMs. The same map also delivers the MDMA to the SCE window, sysctrl (including the software-reset action registers), secsub/tamper and the AO/PMU bridge.

**Evidence.**
```systemverilog
rtl/modules/core/rtl/mdma.sv:79-86
	assign ahbm.hsel = '1;
	assign ahbm.hmaster = AHBMID4;
	assign ahbm.hreadym = ahbm.hready;//'1;
	assign ahbm.hauser = AHBMID4 |'0;
	assign ahbm.hwuser = '0;

	assign apbs_dma.pready = '1;
	assign apbs_dma.pslverr = '0;

rtl/modules/core/rtl/mdma.sv:97-100
    logic apbrd, apbwr;
    `apbs_common;
    logic sfrlock;
    assign sfrlock = '0;

rtl/modules/bmxcore/rtl/bmxcore.sv:162-165
    localparam rule32_t [1:0] mdma_ahb_demux_map = '{
        '{idx: 32'd1 , start_addr: 32'h0000_0000, end_addr: 32'h6000_0000}, // to ahb_bmx33
        '{idx: 32'd0 , start_addr: 32'h6100_0000, end_addr: 32'ha000_0000}  // to nic_1, but no ReRAM
    };

rtl/modules/bmxcore/rtl/bmxcore.sv:271
    ahb_thru bmx33m0 ( .ahbslave(bmx33m[0])         , .ahbmaster(cm7_ahbs ));

rtl/modules/soc_coresub/rtl/soc_coresub.sv:576-578 (MDMA APB at 0x4001_1000 / 0x4001_2000)
        .apbs_dma   (coresubapbs[1]),
        .apbs       (coresubapbs[2]),
        .apbx       (coresubapbs[2])
```

**Preconditions.** Attacker can issue APB writes to 0x4001_1000-0x4001_1FFF (pl230 channel control) and 0x4001_2000-0x4001_2FFF (mdmareq event select). Reachable from the CM7 AHB-P port, the Vex AHB-P port (soc_coresub.sv:613 -> coreahbpmux -> bmxcore .cm7_ahbp), the BDMA AHB master and the SCE AHB path - none of which is filtered by hprot/pprot anywhere in the design.

**Attack scenario.** 1. Attacker runs unprivileged code on the Vex (or unprivileged CM7 code, or drives the BIO/BDMA AHB master, whose hauser is 0 and matches no check anywhere). All of these reach core_ahb32 and therefore 0x4001_1000.
2. He writes a pl230 channel control-structure base pointer into the pl230 register block at 0x4001_1000, pointing at a scratch buffer in SRAM he owns, and programs a channel descriptor with source = 0x2000_0000 (the CM7's D0/D1TCM) and destination = that SRAM buffer. There is no sfrlock (mdma.sv:100), no privilege qualification, and no requester check, so the write succeeds.
3. He arms the request path by writing `cr_en`/`cr_reqen` in `sfr_cr` and selecting a trigger event with `cr_evsel` at 0x4001_2000 (mdma.sv:105-106, 111), or uses the pl230's own software-request register.
4. The MDMA issues AHB reads at 0x2000_xxxx. The bmxcore demux (bmxcore.sv:163) routes 0x0000_0000-0x5FFF_FFFF to ahb_bmx33, whose master 0 is `cm7_ahbs` (bmxcore.sv:271). The CM7 AHBS port services the read from the DTCM with no privilege or coreuser check. The CM7's stack, heap and any key material it has loaded into DTCM are copied into the attacker's buffer.
5. Reversing source and destination writes attacker-chosen bytes into the CM7's ITCM at 0x0000_xxxx - direct code injection into the other CPU, at a moment of the attacker's choosing (e.g. while the CM7 is halted in WFI, cm7sys.sv:331).
6. The same primitive also reaches sysctrl at 0x4004_0080/0084 (the `sfr_rcurst0/1` software-reset action registers) and the AO/PMU bridge, so it doubles as a fault/reset primitive.

**Mitigation.** RTL fix: (a) give the MDMA the same base/bounds whitelist the BIO/BDMA has, applied to `ahbm.haddr` before the demux, with the whitelist and the pl230 control registers behind a real `sfrlock` that boot code sets and only a full reset clears; (b) drive `sfrlock` on both `apbs_dma` and `apbx` from a lockable register rather than `'0`, and gate the MDMA APB on `hprot[1]`/`pprot[0]` so unprivileged code cannot program it; (c) remove 0x0000_0000-0x3FFF_FFFF (ITCM/DTCM) from `mdma_ahb_demux_map` unless DMA-to-TCM is a required feature, or assert `AHBSPRI` and add an AHBS-side filter; (d) give the MDMA a distinct AMBAID (it currently collides with the BDMA's 4'h7) and add a `default:` deny arm to `coreuser_mux` in rrc.sv:670-671.
Silicon workaround: boot0/boot1 must, before handing control to application firmware, permanently gate the MDMA - the only lever available is the clock/reset: hold the MDMA in reset or disable its clock enable via the sysctrl clock-gate registers, and then set the sysctrl SFR lock. Note that `soc_top.sv:217` declares `logic sfrlock;` with no driver anywhere in the file, so the sysctrl write-protect that would normally hold that configuration is itself inert - firmware must verify empirically whether the clock gate can be re-enabled by an attacker before relying on it. Additionally, never leave key material in DTCM across a call into untrusted code.

**Verification.** Verified as written; exploitability not fully established. mdma.sv:79-86 and 97-100 quoted verbatim and correct. bmxcore.sv:162-165 and 271 quoted verbatim and correct. soc_coresub.sv:576-578 correct; coresubapbs is a 16-way apb_mux over a PAW(16) bridge (soc_coresub.sv:643,649-651), so index 1 = 0x4001_1000 and index 2 = 0x4001_2000 as claimed. I traced mdma_ahb32demux[1] -> ahb_mux_slave[1] -> ahb_mux3 -> bmx33s[1] -> ahb_bmx33 -> bmx33m[0] -> cm7_ahbs (bmxcore.sv:224-226, 231-234, 269-282) and that chain is real, but the decode inside ahb_bmx33 is missing from the tree (verified with `find . -name 'ahb_bmx33*'` -> nothing). cm7sys.sv:530 `.AHBSPRI(1'b0)` verified. I found no privilege, coreuser or whitelist gate anywhere on the MDMA path, and no lock on its APB, so the primitive is real; only its reach into the TCMs is unverified and its reach into ReRAM is refuted.

**Corrections applied by the verifier.** Three corrections. (1) The ReRAM claim is wrong in the attacker's favour but the finder also mis-stated the demux: bmxcore.sv:162-165 leaves 0x6000_0000-0x60FF_FFFF matched by NEITHER rule, and ahb_demux.sv:96-97/119-132 shows an unmatched address asserts no hsel, so `ahbslave.hready` is forced to 1'b1, `hresp`=0 and `hrdata`='0 — a silent OKAY-with-zero deny, not a hang. The 'to nic_1, but no ReRAM' comment is correctly implemented; the MDMA genuinely cannot touch the ReRAM key/CFG array, which removes the highest-value target. (2) The ITCM/DTCM claim CANNOT be independently confirmed from this tree: bmxcore.sv:276 instantiates `ahb_bmx33_intf`, whose source is included from `ips/ahb_bmx33/ahb_bmx33_intf.sv` (rtl/asic_top/include/bmxcore_inc.sv:20) and is absent from the repository. The bmx33 address decode — the thing that decides whether 0x0000_0000-0x3FFF_FFFF reaches bmx33m[0]=cm7_ahbs — is therefore unreadable. The finder asserted this routing as established fact; it is an inference. (3) 'unprivileged software on either CPU' is overstated: the design has no bus-level pprot/hprot filter (confirmed — no consumer of hprot/pprot exists outside pass-through wiring), but the CM7 MPU and the Vex MMU are the intended controls on reaching 0x4001_1000, so this reduces to 'MDMA is not a second line of defence', not 'unprivileged code owns the MDMA'. The genuinely solid core of the finding is: mdma.sv:100 `assign sfrlock = '0;` (no lockable control registers), mdma.sv:82 `assign ahbm.hauser = AHBMID4 |'0;` = 4'h7 constant, soc_ifsub.sv:344 `bio_bdma #()` leaves bio_bdma.sv:122 `parameter AHBMID4 = daric_cfg::AMBAID4_MDMA` unoverridden so the BDMA emits the SAME 4'h7, and rrc.sv:670-671 `assign coreuser_mux = scesel ? sceuser : vexsel ? coreuser_vex : coreuser_cm7;` has no default-deny arm — so a 4'h7 (or the BDMA AHB port's hardwired 4'h0, bio_bdma.sv:1579/1670) transaction that does reach the ReRAM AXI slave is adjudicated with the CM7's live PC-derived identity. That is a real, confirmed defect.

---

<a id="bao-075"></a>

### BAO-075 — A single unlocked APB bit permanently disables ITCM/DTCM parity and read/write verification, removing the CM7's only fault-injection detector on its instruction memory

**Severity: Medium** | CWE-1256 Improper Restriction of Software Interfaces to Hardware Features (software-controlled disable of a hardware integrity check) | Threat actor: T1 to set the bit; T2 (laser / EM / voltage fault injection on the TCM macros) to exploit the resulting blind spot | Confidence: High

**Location:** `rtl/modules/core/rtl/cm7sys_tcm.sv:105`

**Description.** `cm7sys_tcm` selects between two TCM datapaths with a bit derived from the SRAM trim register: `fastmode <= fastmode | sramtrm[0]`. This is a set-only sticky flop - once set it cannot be cleared until `resetn` (= `sysresetn_cm7`) de-asserts. In the non-fast path the TCM traffic goes through `gnrl_sramc`, which generates a per-byte parity bit on write and recomputes and compares it on read (`gnrl_sramc.sv:328-336`, `assign prerr0[gvi] = prbit0[gvi] ^ prbitreg[gvi];`) and additionally performs a read-back verify of every write and every read (`gnrl_sramc.sv:136-144`). In fast mode the whole `gnrl_sramc` instance is clock-gated off (`ICG ramc0_icg ( .CK (clk), .EN ( ~fastmode ), ...)`) and traffic is routed through `tcmramc_thru`, which writes a CONSTANT parity bit of 0 and discards the stored parity bit on read. Crucially, `verifyerr` and `prerr` are also explicitly forced to 0 in fast mode. `err_o = verifyerr | prerr` (cm7sys_tcm.sv:75) is the CM7's `ITCMERR`/`D0TCMERR`/`D1TCMERR` input (cm7sys.sv:432, 446, 459, 1003), i.e. the only mechanism by which a corrupted TCM word raises a fault instead of being silently executed or consumed. The controlling register is a plain APB CR with `assign sfrlock = '0;` and no lock bit of any kind (coresub_sramtrm.sv:41, 57-58); the same block also exposes `sfr_ramsec` (coresub_sramtrm.sv:63, IV 4'h0) which gates the background scrub/verify engine (`gnrl_sramc.sv:163 assign evenable = ipdone & even;`) and is likewise unlocked and OFF at reset.

**Evidence.**
```systemverilog
rtl/modules/core/rtl/cm7sys_tcm.sv:104-105
    logic fastmode;
    `theregrn(fastmode) <= fastmode | sramtrm[0];// | 1;

rtl/modules/core/rtl/cm7sys_tcm.sv:74-75
    assign wait_o = ~ramready;
    assign err_o = verifyerr | prerr;

rtl/modules/core/rtl/cm7sys_tcm.sv:180-181
    assign verifyerr = fastmode ? 1'b0 : verifyerr0;
    assign prerr = fastmode ? 1'b0 : prerr0;

rtl/modules/core/rtl/cm7sys_tcm.sv:194 (the checker is clock-gated away in fast mode)
    ICG ramc0_icg ( .CK (clk), .EN ( ~fastmode ),.SE(cmsatpg), .CKG ( clkramc0 ));

rtl/modules/core/rtl/cm7sys_tcm.sv:234-239 (fast path stores a constant parity bit and ignores it on read)
    generate
        for(genvar gvi=0; gvi<DW/8; gvi++) begin : gg
            assign rammaster.ramwdata[gvi*9+8:gvi*9] = { ramslave.ramwdata[gvi*8+7:gvi*8], 1'b0 };
            assign ramslave.ramrdata[gvi*8+7:gvi*8] = rammaster.ramrdata[gvi*9+8:gvi*9+1];
        end
    endgenerate

rtl/modules/core/rtl/coresub_sramtrm.sv:40-41, 57-58, 63 (no lock, and the trim/ramsec CRs)
    logic sfrlock;
    assign sfrlock = '0;
...
	apb_cr #(.A('h04), .DW(5), .IV('h4))  sfr_itcm    (.cr(cr_itcm   ),   .prdata32(),.*);
	apb_cr #(.A('h08), .DW(5), .IV('h4))  sfr_dtcm    (.cr(cr_dtcm   ),   .prdata32(),.*);
...
	apb_cr #(.A('h30), .DW(4), .IV('h0))  sfr_ramsec  (.cr(ramsec ),   .prdata32(),.*);

rtl/modules/core/rtl/coresub_sramtrm.sv:66
	assign { itcmwaitcyc,itcmsramtrm } = cr_itcm;
```

**Preconditions.** Attacker can perform one APB write to 0x4001_4004 (ITCM trim) or 0x4001_4008 (DTCM trim) with bit 0 set. `coresub_sramtrm` is `coresubapbs[4]` (soc_coresub.sv:477) inside the 0x4001_0000 window, reachable from the CM7 AHB-P port, the Vex AHB-P port, the MDMA, the BDMA AHB master and the SCE AHB path. No privilege or coreuser check exists on that path.

**Attack scenario.** 1. The CM7 has been running secure-boot-verified code out of ITCM (INITTCMEN is hardwired to 2'b11, cm7sys.sv:417, so the TCMs are enabled from reset). At reset `cr_itcm = 5'h04`, so `itcmsramtrm = 3'b100`, `sramtrm[0] = 0` and the verified/parity-protected path is active - a single-bit fault injected into an ITCM word would raise ITCMERR and fault the core.
2. The attacker issues one APB write of 0x05 to 0x4001_4004 from unprivileged CM7 code, from the Vex, or via the MDMA (finding 2). `sfrlock` is `'0`, so the write lands. `fastmode` latches to 1 and, because the flop ORs with itself, can never be cleared without a full `sysresetn_cm7`.
3. From this point `prerr` and `verifyerr` are hardwired to 0 and the parity bit written to the macro is a constant 0. Every stored word's parity is now meaningless and no read-back verify occurs.
4. The attacker applies a laser or EM fault to the ITCM macro during a security-critical instruction fetch (e.g. the branch after a signature comparison, or the loop bound of a key-copy routine). The corrupted instruction is fetched and executed with no ITCMERR, no bus fault and no NMI - the chip has been made blind to exactly the fault class the parity/verify logic exists to catch.
5. The same write to 0x4001_4008 covers both DTCM banks, removing the integrity check on data (including any key material staged in DTCM) as well.

**Mitigation.** RTL fix: make `fastmode` a two-way register driven directly from `sramtrm[0]` rather than a sticky OR, and - more importantly - decouple error reporting from the datapath choice: `verifyerr`/`prerr` must be computed and reported in BOTH modes (the fast path should still generate and check the per-byte parity in `tcmramc_thru` instead of writing `1'b0`). Put `coresub_sramtrm` behind a real `sfrlock` (a set-only bit cleared only by reset) and add a separate, independently lockable enable for error reporting so that a performance trim change cannot silently disable an integrity check. `sfr_ramsec` should default to all-ones (scrub enabled) rather than 4'h0.
Silicon workaround: boot0/boot1 must program the ITCM/DTCM trims to their final values with bit 0 CLEAR (keeping the verified path) and must not use fast mode for any TCM that holds security-critical code or data; then, because `coresub_sramtrm` cannot be locked, firmware must periodically re-read 0x4001_4004/0x4001_4008 and treat a set bit 0 as a tamper event, and must avoid leaving any bus master (MDMA, BDMA, Vex) able to reach 0x4001_4000 - see the MDMA mitigation. Note that once an attacker sets the bit, only a `sysresetn` clears it, so the check must be an active periodic poll, not a one-time boot check.

**Verification.** Independently confirmed by a second reviewer. Every quoted line is verbatim correct. cm7sys_tcm.sv:104-105 `logic fastmode; \`theregrn(fastmode) <= fastmode | sramtrm[0];// | 1;` — set-only, cleared only by resetn. cm7sys_tcm.sv:74-75 `assign err_o = verifyerr | prerr;`. cm7sys_tcm.sv:180-181 forces both to 1'b0 in fastmode. cm7sys_tcm.sv:194 clock-gates gnrl_sramc off. cm7sys_tcm.sv:234-239 tcmramc_thru writes a constant 1'b0 parity bit and discards the stored one on read. coresub_sramtrm.sv:40-41 `logic sfrlock; assign sfrlock = '0;` with no lock anywhere, sfr_itcm/sfr_dtcm at 'h04/'h08 with IV 'h4 (so sramtrm=3'b100, bit0=0 at reset — the checked path IS the default, a point in the design's favour), and sfr_ramsec at 'h30 with IV 4'h0 so the background scrub is off by default. I traced the consumer: cm7sys.sv:993/1003 (ITCM), 1023/1033 (D0TCM), 1053/1063 (D1TCM) wire err_o to sys_iterr/sys_d0err/sys_d1err, which are cm7sys.sv:432/446/459 .ITCMERR/.D0TCMERR/.D1TCMERR on the CORTEXM7INTEGRATIONCS instance, so this really is the only TCM corruption reporting path. I searched for a compensating control and found none: no lock bit, no redundant checker, no assertion, and coresub_sramtrm is coresubapbs[4] = 0x4001_4000 (soc_coresub.sv:477) behind the same unfiltered APB bridge as everything else.

**Corrections applied by the verifier.** Severity down from high to medium: the bit alone reads and writes nothing — it only removes a detector, so it must be chained with T2 fault injection to produce an effect, and the attacker already needs an arbitrary APB write to set it. Two small evidence corrections: the quoted 'gnrl_sramc.sv:328-336 / 136-144' line numbers are approximately right (the parity compare is gnrl_sramc.sv:323-338, `assign prerr0[gvi] ... <= prbit0[gvi] ^ prbitreg[gvi];` at 336 and `assign prerr = |prerr0;` at 345; the read/write verify is at gnrl_sramc.sv:120-145 with `assign verifyerr = verifywrerr | verifyrderr;` at 145). Also note the bit is overloaded: `sramtrm` is simultaneously the physical macro trim passed to tcmram (cm7sys_tcm.sv:132), so a legitimate silicon trim change to bit 0 disables the checker as a side effect — arguably worse than the deliberate-attack framing.

---

<a id="bao-076"></a>

### BAO-076 — CM7 coreuser debounce filter holds the PREVIOUS (possibly higher-privilege) identity for up to 255 cycles after the PC leaves a code region, creating a fail-open privilege window on every boot->firmware transition

**Severity: Medium**

**Location:** `rtl/modules/core/rtl/cm7sys.sv:776`

*Surfaced by the independent verifier, not the original domain reviewer.*

**Description.** The instantaneous region-hit vector `coreuserreg0` is passed through a change-debounce filter before it becomes the `coreuser` sideband that rrc.sv adjudicates against. The filter updates `coreuser` only on `coreuser_keepcnthit`, which is cleared for `coreuser_filtercyc` cycles every time the region changes. During that window `coreuser` retains its OLD value while the CPU is already executing in the NEW region. The direction of failure is wrong: on a boot1 -> fw1 transition the filter holds the boot1 identity (coreuser[5]) into fw1 execution, and rrc.sv:815 `cfg_prev_dis = ((!(coreuser_in[5]|coreuser_in[4])) & (cm7sel|vexsel)) | ...` grants the ReRAM CFG/ACRAM region exactly when coreuser[5] or coreuser[4] is set. A safe filter would drop to the least-privileged identity (or to 8'h00, which is fail-closed here) during the settling window rather than latching the outgoing one. `coreuser_filtercyc` is an 8-bit field sourced from ReRAM NVR config (soc_coresub.sv:277 `\`theregfull( hclk, resetn, coreuser_filtercyc , '0 ) <= nvrcfgdata.cfgcore.coreuser_filtercyc;`), so the window can be up to 255 hclk cycles depending on provisioning; note also that an unprovisioned/erased value of 0xFF gives the maximum window rather than the minimum.

**Evidence.**
```systemverilog
rtl/modules/core/rtl/cm7sys.sv:769-776
    `theregrn( coreuserreg1 ) <= coreuserreg0;
    assign coreuser_change = ~(coreuserreg1==coreuserreg0);
    assign coreuser_unchange = (coreuserreg1==coreuserreg0);
    `theregrn( coreuser_keepcnt ) <= coreuser_change ? '0 : ~coreuser_keep ? coreuser_keepcnt + 1 : coreuser_keepcnt;
    `theregrn( coreuser_keep ) <= coreuser_change ? '0 : coreuser_keepcnthit ? '1 : coreuser_keep;
    assign coreuser_keepcnthit = (coreuser_keepcnt == coreuser_filtercyc);

    `theregrn(coreuser) <= coreuser_keepcnthit ? coreuserreg0 : coreuser;

rtl/modules/rrc/rtl/rrc.sv:815-816 (the consumer that the stale value unlocks)
    assign cfg_prev_dis = (((!(coreuser_in[5] | coreuser_in[4])) & (cm7sel|vexsel)) | cm7sel&(!pri_op) | vexsel&(!vex_mm_reg) | scesel)
                             & ((haddr_reg[31:14] == PM_CFGD_REGION) | (haddr_reg[31:14] == PM_CFGK_REGION));

rtl/modules/soc_coresub/rtl/soc_coresub.sv:277
    `theregfull( hclk, resetn, coreuser_filtercyc   , '0 ) <= nvrcfgdata.cfgcore.coreuser_filtercyc;
```

**Attack scenario.** Attacker controls the entry point of fw1 (or any fw region entered from boot code) — e.g. he has replaced or corrupted the application image but not the boot images. At the moment boot1 branches to the fw1 entry vector, `coreuserreg0` flips to the fw1 encoding but `coreuser` still presents boot1 (coreuser[5]=1) for `coreuser_filtercyc` cycles. The attacker places, as the very first instructions at the fw1 entry point, a privileged store to the ReRAM CFG/ACRAM window at 0x603D_C000+N*32. If the transaction's address phase reaches rrc within the filter window, rrc.sv:815 evaluates `!(1|0)` = 0, cfg_prev_dis = 0, cfg_access_error = 0, and the ACRAM descriptor for a key slot is rewritten with `userid_k[7:4]=4'h0` — which per rrc.sv:717 (`& (userid_k[7:4] != 4'h0)`) disables the entire key-slot access check for that slot. The attacker then reads the raw ReRAM key material at leisure. The window is deterministic and repeatable across resets, so he can simply pad with NOPs and sweep the store's offset until it lands inside it.

**Verification.** No independent verdict recorded for this entry.

---

<a id="bao-077"></a>

### BAO-077 — The RISC-V core has no PMP of any kind; with satp.MODE=Bare every privilege level, including U-mode, has unrestricted physical access to the entire SoC

**Severity: Medium** | CWE-1220 Insufficient Granularity of Access Control | Threat actor: T1 | Confidence: High

**Location:** `VexRiscv/GenCramSoC.scala:96`

**Description.** The plugin list that generated the taped-out core contains no PmpPlugin, and the generated netlist contains no PMP logic at all (`grep -ci pmp VexRiscv_CramSoC.v` returns 0; no pmpcfg0-3 (0x3A0-0x3A3) or pmpaddr0-15 (0x3B0-0x3BF) appear in the exhaustive CSR decode list at VexRiscv_CramSoC.v:8945-9053). The only memory-protection mechanism on the Vex is the Sv32 MmuPlugin, and it is *entirely* disabled whenever satp.MODE == 0: `MmuPlugin_ports_0/1_requireMmuLockupCalc = (... ) && MmuPlugin_satp_mode` (6564, 6691), and when that is low the plugin unconditionally asserts allowRead = allowWrite = allowExecute = 1'b1, exception = 1'b0, and passes the virtual address through as the physical address (6615-6656, 6745-6785). satp.MODE resets to 0 (7701). This means: (a) M-mode always has, and can never be denied, full physical access — there is no way for a secure monitor to sandbox itself or to protect a boot0 key-handling routine from later firmware; (b) any privilege level running with satp.MODE=0 has a flat, unchecked view of the whole address map, including 0x4000_00F0 (the ReRAM mass-erase action register, unlocked per rrc.sv:286), 0x4002_0000 (the SCE crypto RAM, open while scemode==0), 0x4004_0080/84 (software resets), 0x4004_5000 (RAM trim), 0x4006_0000 (AO/PMU voltage trims), 0x5012_40E0 (the BIO/BDMA whitelist) and 0xE000_2000 (the coreuser configuration block, finding #3). Because there is no PMP, every one of those access controls is enforced only by the fabric-side coreuser/hauser scheme — which findings #1-#3 show is itself software-selectable on this core. The four coreuser 'identities' (boot0/boot1/fw0/fw1) that share this CPU therefore have no hardware isolation from each other at the CPU level whatsoever.

**Evidence.**
```systemverilog
VexRiscv/GenCramSoC.scala:88-190 -- complete plugin list, no PmpPlugin present:
          new IBusCachedPlugin(...),
          new DBusCachedPlugin(...),
          new DecoderSimplePlugin(...), new RegFilePlugin(...), new IntAluPlugin,
          new SrcPlugin(...), new FullBarrelShifterPlugin(...), new HazardSimplePlugin(...),
          new MulPlugin, new DivPlugin, new AesZknPlugin,
          new CsrPlugin(CsrPluginConfig.linuxFull(mtVecInit = 0x60000000) ...),
          new BranchPlugin(...), new MmuPlugin(...), new ExternalInterruptArrayPlugin(...),
          new YamlPlugin(...), new DebugPlugin(...)

VexRiscv/VexRiscv_CramSoC.v:6691 (MMU is the only gate, and it is off when satp.MODE==0)
      MmuPlugin_ports_1_requireMmuLockupCalc = ((1'b1 && (! DBusCachedPlugin_mmuBus_cmd_0_bypassTranslation)) && MmuPlugin_satp_mode);

VexRiscv/VexRiscv_CramSoC.v:6761-6767 (fail-open when translation is off)
    always @(*) begin
      if(MmuPlugin_ports_1_requireMmuLockupCalc) begin
        DBusCachedPlugin_mmuBus_rsp_allowWrite = MmuPlugin_ports_1_cacheLine_allowWrite;
      end else begin
        DBusCachedPlugin_mmuBus_rsp_allowWrite = 1'b1;
      end
    end

VexRiscv/VexRiscv_CramSoC.v:6777-6783
      if(MmuPlugin_ports_1_requireMmuLockupCalc) begin
        DBusCachedPlugin_mmuBus_rsp_exception = ...;
      end else begin
        DBusCachedPlugin_mmuBus_rsp_exception = 1'b0;
      end

VexRiscv/VexRiscv_CramSoC.v:7701 (reset state is Bare)
        MmuPlugin_satp_mode <= 1'b0;
```

**Preconditions.** Code execution on the Vex at any privilege level, in any context where satp.MODE == 0 (which is the state at reset and for all M-mode firmware). No physical access needed.

**Attack scenario.** 1. Attacker gains code execution in any Vex context that runs with satp.MODE=0 — which includes all M-mode firmware (boot0, boot1, and any fw that has not yet enabled paging), and includes U-mode in any window where the kernel has not installed page tables. 2. With no PMP there is no second gate: a single store instruction reaches any physical address. 3. Attacker writes 0x2468 to 0x4000_00F0, which rrc.sv:286 (`apb_ar #(.A('hF0), .AR(PM_RRAM_SUICIDE)) sfr_rrcar (.ar(rrcar_suicide), .sfrlock(1'b0), ...)`) turns into a ReRAM mass erase — a permanent, unrecoverable denial of service against a fabricated part. Or the attacker writes 0xE000_2000 to take over the coreuser identity (finding #3), or 0x4006_0020 to retrim the PMU voltage rails, or 0x4004_5000 to retime the SCE key RAMs. 4. Because the same physical CPU hosts all four coreuser identities, fw1 code compromised by a memory-safety bug simply sets satp.MODE=0 and reads boot0's private data structures out of SRAM/TCM directly, without ever going through the RRC.

**Mitigation.** RTL (for any respin): add `new PmpPlugin(regions = 16, granularity = 32, ioRange = ...)` to the plugin list in GenCramSoC.scala, and have boot0 lock M-mode-only regions covering 0x4000_0000-0x400F_FFFF (RRC/SCE control), 0x4004_0000-0x4004_FFFF (sysctrl/rbist), 0x4006_0000 (AO/PMU), 0x5012_4000 (BIO) and 0xE000_0000-0xE003_FFFF (the CPU-internal CSR bank) with the L (lock) bit set so they survive until reset. Software workaround on fabricated silicon: there is no hardware backstop, so the entire burden falls on firmware discipline — boot0 must enable Sv32 paging (satp.MODE=1) before any code it does not fully control executes, must never return to Bare mode, must never map the sensitive physical pages listed above into any address space it does not fully trust, and must set `coreuser_protect` (finding #3) and the RRC `rrccr[12]` code-check bit early. Treat every line of M-mode code on this core as fully privileged over the whole chip.

**Verification.** Independently confirmed by a second reviewer. `grep -ci pmp VexRiscv/VexRiscv_CramSoC.v` returns 0, and I enumerated every CSR literal in the netlist (`grep -o "12'h[0-9a-f]*" | sort -u`): 0x0,100,104,105,140,141,142,143,144,180,300,301,302,303,304,305,340,341,342,343,344,9c0,b00,b02,b80,b82,bc0,c00,c02,c80,c82,cc0,dc0,f11,f12,f13,f14,fc0 — no pmpcfg (0x3A0-3A3) and no pmpaddr (0x3B0-3BF). GenCramSoC.scala:87-193 contains no PmpPlugin. The MMU fail-open behaviour reproduces verbatim at VexRiscv_CramSoC.v:6564 and 6691 (`requireMmuLockupCalc = (...) && MmuPlugin_satp_mode`), 6753/6761/6769 (allowRead/allowWrite/allowExecute forced 1'b1), 6777-6783 (exception forced 1'b0), 6745-6750 (physical = virtual pass-through), and 7701 (`MmuPlugin_satp_mode <= 1'b0` at reset). So with satp.MODE==0 there is no gate of any kind on the Vex's data path, and there is no mechanism by which M-mode can sandbox itself from S-mode. This is a genuine and material weakness in this specific SoC because the fabric-side coreuser bank sits at 0xE000_2000 on that same unchecked path (finding #3).

**Corrections applied by the verifier.** Two calibrations. (1) This is an architectural omission, not an RTL defect: PMP is optional in the RISC-V privileged spec, and a core with no PMP and satp.MODE=0 permitting all accesses is spec-conformant behaviour, so it should be reported as a design weakness rather than a bug. (2) The 'U-mode has unrestricted physical access' framing overstates the realistic case — U-mode only sees flat physical memory if the supervisor runs it with satp.MODE==0, which no real OS does. The substantive, always-true consequence is narrower: S-mode has unrestricted physical read/write of the whole map at any time (one `csrw satp, 0` away), so M-mode firmware cannot be isolated from a compromised kernel, and the four coreuser identities sharing this core have no CPU-level isolation. Minor evidence error carried in the attack scenario: rrc.sv:286 is `ahb_ar #(.A('hF0), .AR(PM_RRAM_SUICIDE)) sfr_rrcar (.ar(rrcar_suicide), .resetn(coreresetn), .sfrlock(1'b0), .*);` — an `ahb_ar`, not an `apb_ar`, and PM_RRAM_SUICIDE is 16'h2468 per rrc.sv:256.

---

<a id="bao-078"></a>

### BAO-078 — sstatus (CSR 0x100) exposes and permits writing mstatus.MPRV, an M-mode-only field, letting Supervisor mode redirect Machine-mode data accesses through Supervisor-controlled page tables

**Severity: Medium** | CWE-1220 Insufficient Granularity of Access Control (S-mode-accessible view of an M-mode-only privileged field) | Threat actor: T1 | Confidence: High

**Location:** `VexRiscv/VexRiscv_CramSoC.v:8271`

**Description.** The RISC-V privileged specification defines `sstatus` as a strictly restricted view of `mstatus` containing only SIE, SPIE, UBE, SPP, VS, FS, XS, SUM, MXR and SD. MPRV (mstatus bit 17) is an M-mode-only field and must not be visible or writable through `sstatus`. In this core it is both: the `sstatus` write block at VexRiscv_CramSoC.v:8264-8272 assigns `MmuPlugin_status_mprv <= CsrPlugin_csrMapping_writeDataSignal[17]`, and the `sstatus` read block at 7356-7363 returns it. Access to CSR 0x100 is permitted for privilege >= 01 (the check at 7467 is `CsrPlugin_privilege < execute_CsrPlugin_csrAddress[9:8]`, and 0x100[9:8] == 2'b01), so any S-mode code can set MPRV. MPRV is consumed by the MMU: `when_MmuPlugin_l131_1 = ((! MmuPlugin_status_mprv) && (CsrPlugin_privilege == 2'b11))` and `when_MmuPlugin_l134 = ((! MmuPlugin_status_mprv) || (CsrPlugin_mstatus_MPP == 2'b11))` (6702, 6704). With MPRV=1 and MPP != 2'b11 (which is exactly the state after a trap from S-mode into M-mode, since MPP is loaded with the previous privilege), `MmuPlugin_ports_1_requireMmuLockupCalc` remains equal to `MmuPlugin_satp_mode` — so Machine-mode data accesses are translated through the S-mode-owned satp page tables. Compounding this, the U/S permission check at 6777 uses `CsrPlugin_privilege` (== 2'b11 in M-mode) rather than the MPRV-effective privilege MPP, so no page-permission bit constrains the redirected M-mode access at all: the S-mode attacker gets a pure address-redirection primitive over the most trusted code on the core. MPRV is correctly cleared on `CsrPlugin_xretAwayFromMachine` (7948-7950), so the window is exactly the duration of the M-mode trap handler — which is when a secure monitor does its key handling.

**Evidence.**
```systemverilog
VexRiscv/VexRiscv_CramSoC.v:8264-8272 (sstatus write -- MPRV is M-mode-only and must not be here)
        if(execute_CsrPlugin_csr_256) begin
          if(execute_CsrPlugin_writeEnable) begin
            CsrPlugin_sstatus_SPP <= CsrPlugin_csrMapping_writeDataSignal[8 : 8];
            CsrPlugin_sstatus_SPIE <= CsrPlugin_csrMapping_writeDataSignal[5];
            CsrPlugin_sstatus_SIE <= CsrPlugin_csrMapping_writeDataSignal[1];
            MmuPlugin_status_mxr <= CsrPlugin_csrMapping_writeDataSignal[19];
            MmuPlugin_status_sum <= CsrPlugin_csrMapping_writeDataSignal[18];
            MmuPlugin_status_mprv <= CsrPlugin_csrMapping_writeDataSignal[17];
          end
        end

VexRiscv/VexRiscv_CramSoC.v:7356-7362 (sstatus read leaks it back)
      if(execute_CsrPlugin_csr_256) begin
        _zz_CsrPlugin_csrMapping_readDataInit_25[8 : 8] = CsrPlugin_sstatus_SPP;
        ...
        _zz_CsrPlugin_csrMapping_readDataInit_25[17 : 17] = MmuPlugin_status_mprv;

VexRiscv/VexRiscv_CramSoC.v:9017 (CSR address is 0x100 -- S-mode)
        execute_CsrPlugin_csr_256 <= (decode_INSTRUCTION[31 : 20] == 12'h100);

VexRiscv/VexRiscv_CramSoC.v:7467 (S-mode passes the privilege gate for 0x100)
  assign when_CsrPlugin_l1625 = (CsrPlugin_privilege < execute_CsrPlugin_csrAddress[9 : 8]);

VexRiscv/VexRiscv_CramSoC.v:6702-6704 (MPRV makes M-mode data accesses use satp)
  assign when_MmuPlugin_l131_1 = ((! MmuPlugin_status_mprv) && (CsrPlugin_privilege == 2'b11));
  assign when_MmuPlugin_l132_1 = (CsrPlugin_privilege == 2'b11);
  assign when_MmuPlugin_l134 = ((! MmuPlugin_status_mprv) || (CsrPlugin_mstatus_MPP == 2'b11));

VexRiscv/VexRiscv_CramSoC.v:6777 (permission check uses CsrPlugin_privilege, not MPP)
      DBusCachedPlugin_mmuBus_rsp_exception = (((! MmuPlugin_ports_1_dirty) && MmuPlugin_ports_1_cacheHit) && ((MmuPlugin_ports_1_cacheLine_exception || ((MmuPlugin_ports_1_cacheLine_allowUser && (CsrPlugin_privilege == 2'b01)) && (! MmuPlugin_status_sum))) || ((! MmuPlugin_ports_1_cacheLine_allowUser) && (CsrPlugin_privilege == 2'b00))));
```

**Preconditions.** Code execution at S-mode on the Vex, plus the existence of M-mode code that performs data accesses after S-mode has run (an ecall-based secure monitor, an M-mode trap/interrupt handler, or resident boot1 services). If the design never re-enters M-mode after handoff, the impact is limited to the pre-handoff window.

**Attack scenario.** 1. Attacker has code execution in the S-mode kernel on the Vex. 2. Attacker builds a malicious Sv32 page table in which the virtual addresses that the M-mode secure monitor is known to use for its stack / scratch buffer / key staging area map to physical pages the attacker controls (e.g. a page in core SRAM at 0x6100_xxxx that the attacker can read afterwards). Attacker installs it with `csrw satp`. 3. Attacker executes `csrsi sstatus, ...` / `csrs sstatus, t0` with bit 17 set — permitted, because 0x100 is an S-mode CSR. `MmuPlugin_status_mprv` becomes 1. 4. Attacker executes `ecall`. Hardware traps to M-mode: privilege becomes 2'b11 and MPP is loaded with 2'b01 (S). 5. Inside the M-mode handler, `when_MmuPlugin_l134` is false (MPRV=1 and MPP != 11) and `when_MmuPlugin_l131_1` is false, so `requireMmuLockupCalc` = satp_mode = 1: every load and store the M-mode monitor performs is translated through the attacker's page table, with no U/S permission enforcement (the check at 6777 sees privilege == 2'b11). 6. When the monitor reads a ReRAM key slot (which it is entitled to do, since vex_mm=1) and stores it to what it believes is its own private buffer, the store is redirected to the attacker's physical page. After `mret` (which clears MPRV at 7949) the attacker reads the key out of that page. The same primitive also lets the attacker corrupt the monitor's saved return address or its ReRAM ACRAM staging data.

**Mitigation.** RTL: remove MPRV from the `sstatus` read and write blocks — delete `MmuPlugin_status_mprv <= CsrPlugin_csrMapping_writeDataSignal[17];` at VexRiscv_CramSoC.v:8271 and the corresponding read at 7362, keeping MPRV only in the `mstatus` (csr_768) blocks at 8195/7206. Separately, when MPRV is active the U/S page-permission check at 6777 should use the MPRV-effective privilege (`CsrPlugin_mstatus_MPP`) rather than `CsrPlugin_privilege`, per the privileged spec. Upstream this should be fixed in VexRiscv's MmuPlugin, which registers mxr/sum/mprv against both mstatus and sstatus. Software workaround on fabricated silicon: every M-mode trap handler must, as its very first instructions and before any load or store other than to a fixed physical scratch, execute `csrci mstatus, (1<<17)` (or `li t0,(1<<17); csrc mstatus,t0`) to clear MPRV, and must not restore it. Because the handler's own prologue stores may already be redirected, the clear must precede the register-save sequence and the handler entry must use `mscratch`-based addressing that is validated after MPRV is cleared. Alternatively, keep the M-mode monitor entirely out of the post-S-mode execution path.

**Verification.** Independently confirmed by a second reviewer. The RTL defect is real and every citation reproduces (with two one-line offsets). VexRiscv_CramSoC.v:8264-8272 is the `execute_CsrPlugin_csr_256` (sstatus) write block and it does contain `MmuPlugin_status_mprv <= CsrPlugin_csrMapping_writeDataSignal[17];` at line 8271; the identical assignment for mstatus is at 8195, confirming MPRV is registered against both CSRs. The read-back leak is at 7362 `_zz_CsrPlugin_csrMapping_readDataInit_25[17:17] = MmuPlugin_status_mprv;`. csr_256 is 12'h100 (line 9017) and the privilege gate is at 7466 (not 7467), `CsrPlugin_privilege < csrAddress[9:8]`, which for 0x100 is `priv < 2'b01` — S-mode passes. I traced the MMU consumption by hand: with MPRV=1 and MPP!=2'b11, `when_MmuPlugin_l131_1` (6702) is false and `when_MmuPlugin_l134` (6704) is false, so neither clear at 6693-6699 fires and `MmuPlugin_ports_1_requireMmuLockupCalc` stays equal to `MmuPlugin_satp_mode` while `CsrPlugin_privilege == 2'b11`. The permission check at 6777 does use `CsrPlugin_privilege` rather than MPP, so no U/S bit constrains the redirected access. MPRV is cleared only at 7948-7950 on `CsrPlugin_xretAwayFromMachine`. This is a genuine deviation from the RISC-V privileged spec (sstatus is defined to contain only SIE/SPIE/UBE/SPP/VS/FS/XS/SUM/MXR/SD) and it is an upstream VexRiscv MmuPlugin issue worth reporting to the vendor.

**Corrections applied by the verifier.** Severity is overstated in this SoC's context. Because there is no PMP and satp.MODE resets to Bare (finding #4, verified), an S-mode attacker already has unrestricted physical read/write over the entire address map, including all M-mode code and data, with a single `csrw satp, x0`. MPRV therefore adds only a redirection primitive against M-mode's own virtual accesses; it does not unlock anything the attacker cannot already reach directly. It is a real spec-conformance defect that would be critical on a core with PMP, but here it is incremental. Downgrading high -> medium.

---

<a id="bao-079"></a>

### BAO-079 — ReRAM key and data regions are cacheable in the Vex's 16 KB write-back D-cache and 16 KB I-cache, and nothing invalidates them on an ASID / coreuser / privilege change, so RRC access control is enforced only on the first fill

**Severity: Medium**

**Location:** `VexRiscv/VexRiscv_CramSoC.v:6801`

*Surfaced by the independent verifier, not the original domain reviewer.*

**Description.** The MmuPlugin's ioRange — the only thing that marks an address non-cacheable — covers physical addr[31:28] in {0x4,0x5,0xA,0xB,0xC,0xD,0xE,0xF} only (GenCramSoC.scala:172-181, synthesized at VexRiscv_CramSoC.v:6671 for the iBus and 6801 for the dBus). ReRAM at 0x6xxx_xxxx is absent, so the ReRAM key window 0x603F_xxxx, the data window 0x603E_xxxx and the CFG/ACRAM window 0x603D_Cxxx are all CACHEABLE, in both the 16 KB 4-way instruction cache and the 16 KB 4-way write-back data cache (GenCramSoC.scala:95-121). Note that `isIoAccess` is computed from the *physical* address unconditionally, so this holds even with satp.MODE==0. The RRC performs its coreuser/vex_mm/ACRAM check per AXI transaction (rrc.sv:660-664, 712-727) — that is, only on a cache fill or a dirty writeback. A subsequent load that HITS in the D-cache never reaches the AXI bus and is therefore never checked. There is no invalidation of the data cache on any security-relevant event: the only flush source in the whole design is `dataCache_1_io_cpu_flush_valid = (execute_arbitration_isValid && execute_MEMORY_MANAGMENT)` (VexRiscv_CramSoC.v:5179), i.e. an explicit cache-management instruction. A satp write invalidates only the MmuPlugin TLB entries (`MmuPlugin_ports_0_cache_N_valid <= 1'b0` at VexRiscv_CramSoC.v:8293-8301) — not the data or instruction caches. `withInvalidate = false` in the DataCacheConfig. Nothing observes `coreuser_vex` or `vex_mm` changing. The CM7 path shows the designers were aware that identity transitions need handling (cm7sys.sv:768-773 implements a `coreuser_keep`/`coreuser_filtercyc` debounce on identity change); the Vex path has no equivalent and, critically, no cache action.

**Evidence.**
```systemverilog
VexRiscv/VexRiscv_CramSoC.v:6801 (0x6 is NOT an io/uncached range -> ReRAM is cached)
  assign DBusCachedPlugin_mmuBus_rsp_isIoAccess = ((((((((DBusCachedPlugin_mmuBus_rsp_physicalAddress[31 : 28] == 4'b0100) || (... == 4'b0101)) || (... == 4'b1010)) || (... == 4'b1011)) || (... == 4'b1100)) || (... == 4'b1101)) || (... == 4'b1110)) || (... == 4'b1111));

VexRiscv/VexRiscv_CramSoC.v:5179 (the ONLY dcache flush trigger in the design)
  assign dataCache_1_io_cpu_flush_valid = (execute_arbitration_isValid && execute_MEMORY_MANAGMENT);

VexRiscv/VexRiscv_CramSoC.v:8288-8301 (satp write invalidates the TLB only, not the caches)
        if(execute_CsrPlugin_csr_384) begin
          if(execute_CsrPlugin_writeEnable) begin
            MmuPlugin_satp_mode <= CsrPlugin_csrMapping_writeDataSignal[31];
            MmuPlugin_satp_asid <= CsrPlugin_csrMapping_writeDataSignal[30 : 22];
            ...
            MmuPlugin_ports_0_cache_0_valid <= 1'b0;

rtl/modules/rrc/rtl/rrc.sv:660-664 (the RRC check is per-AXI-transaction only)
    `theregfull(clktop, coreresetn, axprot_reg, '0) <= axis.arvalid & axis.arready & clken ? axis.arprot : ...
    `theregfull(clktop, coreresetn, vex_mm_reg, '0) <= (axis.arvalid & axis.arready & clken) | (axis.awvalid & axis.awready & clken) ? vex_mm : vex_mm_reg;
```

**Attack scenario.** 1. Privileged Vex firmware running under the boot0 identity (coreuser_vex[4]=1, vex_mm=1) reads a ReRAM key slot at 0x603F_xxxx. The RRC permits the fill; the 32-byte line lands in the D-cache. 2. Control transfers to lower-privilege or different-identity code — an S-mode kernel, a U-mode task, or simply another ASID (`csrw satp` with a different ASID, which the coreuser LUT then maps to fw1). No cache maintenance is performed, because none is architecturally required and the RTL provides no automatic invalidation. 3. The attacker executes an ordinary load from 0x603F_xxxx. With satp.MODE==0 there is no page permission (no PMP, finding #4); the access hits in the physically-tagged D-cache and returns the key bytes without ever generating an AXI transaction, so the RRC's coreuser/vex_mm/core_rd_dis/trustkey checks are never evaluated. 4. The dual also holds for writes: a store that hits an already-resident dirty line is never seen by the RRC, and the eventual writeback carries `vex_mm` sampled at eviction time rather than at store time.

**Verification.** No independent verdict recorded for this entry.

---

<a id="bao-080"></a>

### BAO-080 — The Vex coreuser encoder has no 'no identity' value — every possible ASID maps one-hot onto one of the four privileged ReRAM identities, and both the reset and unmatched-ASID defaults select boot0, the most privileged

**Severity: Medium**

**Location:** `rtl/modules/vexriscv/rtl/cram_axi.sv:5851`

*Surfaced by the independent verifier, not the original domain reviewer.*

**Description.** `coreuser_coreuser_4bit` is produced by a full 2-to-4 one-hot case at cram_axi.sv:5851-5883 whose four arms emit 4'd1, 4'd2, 4'd4 and 4'd8 and which covers all four values of the 2-bit selector, so the initial `coreuser_coreuser_4bit <= 4'd0;` is always overridden and the output can never be 4'b0000. That value becomes `coreuser_vex[7:4]` (cram_axi.sv:20921). Per the RRC's own map (rrc.sv:642 `coreuser [7]:fw1, [6]:fw0, [5]:boot1, [4]:boot0`) and the bit ordering at cram_axi.sv:20921, selector 0 -> coreuser_vex[4] = boot0, 1 -> boot1, 2 -> fw0, 3 -> fw1. There is therefore no way for firmware to express 'this context has no ReRAM identity': every ASID the CPU can install owns exactly one of the four identities and passes the RRC's owner test `(coreuser_in[7:4] & userid_k[7:4])==0` for every slot assigned to it. Worse, the encoding is fail-open in the least-privileged direction: selector 0 — the value every relevant register resets to — is boot0, the identity that also satisfies the CFG/ACRAM gate `coreuser_in[5] | coreuser_in[4]` at rrc.sv:815. The relevant resets are cram_axi.sv:22396 `coreuser_uservalue_storage <= 18'd0;` (all eight LUT uservalues and the default, cram_axi.sv:13194-13205) and cram_axi.sv:22418 `coreuser_user_default <= 2'd0;`. So if firmware sets `coreuser_control.enable` before programming `coreuser_uservalue` (0xE000_2010), or if any ASID fails to match a LUT entry and falls through to `coreuser_user_default` at cram_axi.sv:5840, the resulting identity is boot0 with full access to the boot0-owned key slots and to the 0x603D_Cxxx CFG/ACRAM region. A safe design would reserve one encoding for 'deny' (coreuser == 4'b0000) so that unconfigured and unmatched contexts fail closed.

**Evidence.**
```systemverilog
rtl/modules/vexriscv/rtl/cram_axi.sv:5851-5871
always @(*) begin
    coreuser_coreuser_4bit <= 4'd0;
    if (coreuser_enable1) begin
        case (coreuser_coreuser_2bit)
            1'd0: begin
                coreuser_coreuser_4bit <= 1'd1;
            end
            1'd1: begin
                coreuser_coreuser_4bit <= 2'd2;
            end
            2'd2: begin
                coreuser_coreuser_4bit <= 3'd4;
            end
            2'd3: begin
                coreuser_coreuser_4bit <= 4'd8;
            end
        endcase

rtl/modules/vexriscv/rtl/cram_axi.sv:5840 (unmatched ASID falls through to the software default)
                                    coreuser_coreuser_2bit <= coreuser_user_default;

rtl/modules/vexriscv/rtl/cram_axi.sv:22396 and 22418 (both defaults reset to selector 0 = boot0)
        coreuser_uservalue_storage <= 18'd0;
        coreuser_user_default <= 2'd0;

rtl/modules/vexriscv/rtl/cram_axi.sv:20921 (bit 0 of the one-hot is coreuser_vex[4] = boot0)
      coreuser_vex[7:4] <= coreuser_coreuser_4bit;

rtl/modules/rrc/rtl/rrc.sv:642 and 815
  //    coreuser    [7]:fw1,    [6]:fw0,            [5]:boot1           [4]:boot0
    assign cfg_prev_dis = (((!(coreuser_in[5] | coreuser_in[4])) & (cm7sel|vexsel)) | cm7sel&(!pri_op) | vexsel&(!vex_mm_reg) | scesel)
```

**Attack scenario.** 1. Boot firmware writes `coreuser_control = 0x1` at 0xE000_2000 to enable the coreuser block but has not yet (or does not fully) program `coreuser_map_lo`/`map_hi`/`uservalue` at 0xE000_2008/0x200C/0x2010 — the storage registers are still at their reset value of zero. 2. Any code running with any ASID now resolves through the LUT to selector 0 (either by matching a zero-valued LUT entry or by falling through to `coreuser_user_default`, cram_axi.sv:5840), which encodes to 4'd1 = coreuser_vex[4] = boot0. 3. Because boot0 is the identity that satisfies both the key-slot owner test at rrc.sv:712 for every boot0-owned slot and the `coreuser_in[5] | coreuser_in[4]` gate at rrc.sv:815, that code reads the boot0 key slots and the 0x603D_Cxxx CFG/ACRAM region — which contains the ACRAM ownership descriptors themselves. 4. Even with a fully programmed LUT, firmware has no way to give an untrusted context a null identity; the best available choice is fw1, which still owns whatever slots are tagged fw1, so a compromised fw1 process cannot be demoted below fw1 without reprogramming the ACRAM.

**Verification.** No independent verdict recorded for this entry.

---

<a id="bao-081"></a>

### BAO-081 — uDMA APB decoder drives PREADY=0 for unmapped peripheral slots, permanently deadlocking the AHB/APB bridge (0x5011_5000-0x5011_FFFF)

**Severity: Medium** | CWE-833 Deadlock | Threat actor: T1 | Confidence: High

**Location:** `rtl/ips/udma/udma_core/rtl/common/udma_apb4k_if.sv:68`

**Description.** `udma_apb4k_if` decodes the 128 KB uDMA APB window with a 5-bit slot select `PADDR[16:12]` (32 possible slots) but only generates a PREADY for slot indices below `N_PERIPHS`. In this SoC `N_REAL_PERIPHS` = `N_PERIPHS` + 1 = 21 (udma_sub.sv:173 with N_SPI=4, N_UART=4, N_I2C=4, N_CAM=1, N_I2S=1, N_SDIO=1, N_FILTER=1, N_SPIS=2, N_SCIF=1, N_ADC=1, plus the udma_ctrl block). For slot indices 21..31 the for-loop never matches, so the combinational default `PREADY = 1'b0` survives and the block asserts PREADY=0 forever. There is no default slave, no timeout, and `PSLVERR` is hardwired to 0 (line 64), so there is no way for the transfer to terminate. This APB port is driven by a dedicated `apb_bdg` with no APB mux in front of it (soc_ifsub.sv:151-156), so unlike the `apbper` mux path -- where every unused slot is tied off with `apbs_null` which drives `pready = 1` (amba_components.sv:543-547) -- nothing rescues the transfer. AMBA APB bridges insert wait states until PREADY, so HREADYOUT stays low indefinitely and the AHB slave port never completes.

**Evidence.**
```systemverilog
rtl/ips/udma/udma_core/rtl/common/udma_apb4k_if.sv:61-76
    assign s_periph_sel   = PADDR[APB_ADDR_WIDTH-1:12];
    assign s_periph_valid = PSEL & PENABLE & ( PADDR[11:7] == '0 );

    assign PSLVERR = 1'b0;

    always_comb begin : proc_PRDATA
        PRDATA = 'h0;
        PREADY = 1'b0;
        for (int i=0;i<N_PERIPHS;i++)
        begin
            if (s_periph_sel == i)
            begin
                PRDATA = periph_data_i[i];
                PREADY = periph_ready_i[i];
            end
        end
    end

rtl/ips/udma/udma_core/rtl/core/udma_core4k.sv:174
    localparam N_REAL_PERIPHS         = N_PERIPHS + 1;

rtl/modules/ifsub/rtl/udma_sub.sv:173
    localparam N_PERIPHS = N_SPI + N_HYPER + N_UART + N_MRAM + N_I2C + N_CAM + N_I2S + N_CSI2 + N_SDIO + N_JTAG + N_FILTER + N_FPGA + N_EXT_PER + N_SPIS + N_SCIF + N_ADC;

rtl/modules/ifsub/rtl/soc_ifsub.sv:132 (window that makes the slot reachable)
        '{idx: 32'd0 , start_addr: 32'h5010_0000, end_addr: 32'h5011_ffff}  // udma

rtl/modules/ifsub/rtl/soc_ifsub.sv:151-156 (no apb_mux, no null slaves in this path)
    apb_bdg #(.PAW(17)) uapbudma (
        .hclk(clk),
        .resetn(resetn),
        .pclken(1'b1),
        .ahbslave(bmxifmdemux[0]),
        .apbmaster(apbudma));

Contrast, rtl/modules/amba/rtl/amba_components.sv:543-547
    module apbs_null ( apbif.slave  apbslave );
        assign apbslave.prdata       = 0        ;
        assign apbslave.pready       = 1        ;
        assign apbslave.pslverr      = 0        ;
    endmodule
```

**Preconditions.** Ability to execute a single load or store to a fixed address in the 0x5011_5xxx-0x5011_Fxxx range from any bus master that reaches the ifsub AHB slave. No privilege, no prior configuration, no lock defeat required. Assumes the (out-of-repo) cmsdk_ahb_to_apb bridge follows the AMBA APB rule of waiting for PREADY, which it does.

**Attack scenario.** 1. Unprivileged code running on either CPU (via the CM7 AHB-P port hauser=0x8, or the Vex AHB-P port hauser=0xD) issues a single 32-bit load or store to 0x5011_5000 (slot 21). No coreuser, hprot or pprot check exists anywhere on the ifsub APB path, so the access is not filtered. 2. `ahb_demux_map` routes it to `bmxifmdemux[0]`, `apb_bdg` starts an APB access with PADDR=0x15000. 3. `s_periph_sel` = 21 >= N_REAL_PERIPHS = 21, so the for-loop never matches and PREADY stays 0. 4. The bridge holds HREADYOUT low forever. The issuing CPU stalls in the load/store with no bus fault and no watchdog-visible progress; because the AHB matrix slave port is now occupied indefinitely, every other master that subsequently targets any 0x50xx_xxxx address (the other CPU, the BIO/BDMA AHB master) also stalls. 5. The only recovery is an external reset. The same effect is reachable from the BDMA's AHB peripheral master (hauser=0x0), i.e. a compromised BIO program can hang the whole interface bus. Any of 0x5011_5000-0x5011_FFFF works.

**Mitigation.** RTL fix: give the decoder a default/terminating response, e.g. `PREADY = 1'b1; PRDATA = '0;` as the combinational default in `proc_PRDATA` (and optionally raise PSLVERR for unmapped slots so software sees a fault instead of silent zeros), or add a bus-timeout unit in `apb_bdg`. Silicon workaround: none in hardware. Firmware must (a) never emit an access into 0x5011_5000-0x5011_FFFF, (b) if the CM7 MPU is ever enabled, mark 0x5011_4000-0x5011_FFFF as no-access so a stray pointer faults instead of hanging, and (c) treat the range as a forbidden region in any JIT/driver that computes uDMA register addresses from a peripheral index.

**Verification.** Independently confirmed by a second reviewer. Evidence verified verbatim. rtl/ips/udma/udma_core/rtl/common/udma_apb4k_if.sv:61 `assign s_periph_sel = PADDR[APB_ADDR_WIDTH-1:12];`, :64 `assign PSLVERR = 1'b0;`, :66-77 the always_comb whose default is `PREADY = 1'b0;` (line 68) with a for-loop that only matches i<N_PERIPHS. Parameter chain checked: udma_core4k.sv:174 `localparam N_REAL_PERIPHS = N_PERIPHS + 1;` and :426 `.N_PERIPHS(N_REAL_PERIPHS)` is what the decoder actually gets. udma_sub.sv:173 sums to 20 with the values actually elaborated (soc_ifsub.sv:77-84 N_SPIM=4, N_UART=4, N_I2C=4, N_SPIS=2; udma_sub.sv:146-161 N_CAM=1, N_I2S=1, N_SDIO=1, N_FILTER=1, N_SCIF=1, N_ADC=1, N_EXT_PER=0 since PULP_TRAINING is undefined), so N_REAL_PERIPHS=21 and slot indices 21..31 (PADDR 0x15000..0x1FFFF) match nothing. Every mapped peripheral hardwires ready high (e.g. udma_scif_reg.sv:317 `assign cfg_ready_o = 1'b1;`), so the only PREADY=0 case is the unmapped one. Reachability confirmed: soc_ifsub.sv:404 `parameter PAW = 17;`, soc_ifsub.sv:132 maps 0x5010_0000-0x5011_ffff to bmxifmdemux[0], and soc_ifsub.sv:151-156 `apb_bdg #(.PAW(17)) uapbudma` feeds the uDMA APB directly with no apb_mux and no apbs_null in that path (contrast soc_ifsub.sv:171-172 where the apbper mux slots ARE nulled). apb_bdg (amba_components.sv:935-985) is a bare cmsdk_ahb_to_apb with no timeout logic. I searched rtl/modules/amba for any timeout unit and found none. I could not find a compensating control.

**Corrections applied by the verifier.** Two over-statements. (1) 'every other master that subsequently targets any 0x50xx_xxxx address also stalls' is too broad: rtl/modules/amba/rtl/ahb_demux.sv:119 `assign ahbslave.hready = |hseldataphase ? |hreadyall : 1'b1;` means unmapped AHB addresses complete normally, and only masters that actually target the ifsub AHB slave port are blocked behind the stalled transfer; traffic to other slaves is unaffected. (2) 'The only recovery is an external reset' is wrong: the SoC instantiates a watchdog (rtl/modules/sysctrl/rtl/aoperi.sv:67 `cmsdk_apb_watchdog uwdt` with `.WDOGRES(wdtrst)`, and again at apbsys_intf.sv:24 with the comment '// connect to reset generator'), so an enabled WDT recovers the part. Also note cmsdk_ahb_to_apb itself is not in this repo; the indefinite wait is inferred from the AMBA APB PREADY contract, which that bridge is known to honour. Impact is availability only - no asset is read or written - so medium is too high.

---

<a id="bao-082"></a>

### BAO-082 — Pinmux/GPIO register-file write-protect exists in the RTL but is hardwired disabled at the top level (`.ioxlock('0)`)

**Severity: Medium** | CWE-1233 Security-Sensitive Hardware Controls with Missing Lock Bit Protection | Threat actor: T1 | Confidence: High

**Location:** `rtl/asic_top/rtl/soc_top.sv:772`

**Description.** The `iox` block implements a complete SFR write-protect: it takes an `sfrlock` input (iox.sv:34) which is bound by `.*` into every one of its control registers -- alternate-function select (AFSEL, 0x5012_F000), interrupt/wakeup select (INTCR, 0x100), GPIO output/OE/pull-up (0x130/0x148/0x160), BIOSEL (0x200) and the pad drive/slew/schmitt config (0x230) -- and `apb_sfr2` gates every write with it (`assign apbwr = ~sfrlock & apbslave.psel & apbslave.penable & apbslave.pwrite;`). `soc_ifsub` faithfully plumbs `ioxlock` to that input. But the only two instantiations of `soc_ifsub` in the design tie `ioxlock` to a constant 0, so the lock can never be engaged. There is consequently no point in the boot flow at which boot0/boot1 or a secure kernel can freeze the pin configuration before handing control to lower-trust code, and there is no coreuser/pprot/hprot check anywhere on the path to the ifsub APB either (no ifsub slave consumes `pprot`; `apb_mux` merely forwards it, amba_components.sv:311). Note this is asymmetric with the rest of the design: the mesh, sensorc and gluechain SFR blocks that this lock would parallel also tie their `sfrlock` to 0, but iox is the one block that was given a real top-level lock port and then had it grounded.

**Evidence.**
```systemverilog
rtl/asic_top/rtl/soc_top.sv:772
                                        .ioxlock   ( '0    ),

rtl/modules/ifsub/rtl/soc_ifsub.sv:580 (correctly plumbed)
        .sfrlock    (ioxlock),

rtl/modules/ifsub/rtl/iox.sv:34
    input logic sfrlock,

rtl/modules/ifsub/rtl/iox.sv:75 (AFSEL - pad function select, bound via .*)
	apb_cr #(.A('h00), .DW(16), .SFRCNT(IOC*AFCW/16)) sfr_afsel  (.cr(crafsel), .prdata32(),.*);

rtl/modules/ifsub/rtl/iox.sv:137-138 (interrupt/wakeup source select)
	apb_cr #(.A('h100),      .DW(IOCW+4), .SFRCNT(INTC))  sfr_intcr  (.cr(crint), .prdata32(),.*);
    apb_fr #(.A('h100+INTC*4), .DW(INTC)    )        		 sfr_intfr  (.fr(frint), .prdata32(),.*);

rtl/modules/ifsub/rtl/iox.sv:156-158 (GPIO out / OE / pull-up)
	apb_cr #(.A('h130             ), .DW(16), .SFRCNT(GPIOSFRC)		 ) sfr_gpioout  (.cr(crgo ), .prdata32(),.*);
	apb_cr #(.A('h130+GPIOSFRC*1*4), .DW(16), .SFRCNT(GPIOSFRC)		 ) sfr_gpiooe   (.cr(crgoe), .prdata32(),.*);
	rapb_cr #(.A('h130+GPIOSFRC*2*4), .DW(16), .SFRCNT(GPIOSFRC), .IV(16'hffff)) sfr_gpiopu   (.cr(crgpu), .prdata32(),.*);

rtl/modules/ifsub/rtl/iox.sv:259 (BIOSEL - hands 32 pads to the BIO)
    apb_cr #(.A('h200), .DW(32), .REVX(1) ) sfr_piosel   (.cr(piosel), .prdata32(),.*);

rtl/modules/amba/rtl/apb_sfr.sv:333 (the lock that is never engaged)
    assign apbwr = ~sfrlock & apbslave.psel & apbslave.penable & apbslave.pwrite;
```

**Preconditions.** Write access to the ifsub APB window at 0x5012_F000 from any bus master (CM7 AHB-P, Vex AHB-P, or the BIO/BDMA AHB peripheral master). No privilege level is checked on this path.

**Attack scenario.** 1. Secure boot brings the chip up, configures PB13/PB14 as the SCIF (smart-card) clock/data via AFSEL (soc_ifsub.sv:664-665 wires scif_sck/scif_dat as AF2 on those pads) and PE10-PE13 as SPI-slave 0 (soc_ifsub.sv:709-712), and hands off to application firmware. It has no way to lock the configuration because `sfrlock` is grounded. 2. Any subsequently-running code -- or the BIO/BDMA AHB peripheral master, which drives `hauser = '0` and matches no identity check on this path -- writes 0x5012_F000..0x5012_F02C (AFSEL) to steal a pad from the peripheral that a higher-privileged context is using, or writes 0x5012_F200 (BIOSEL) to hand PB[15:0]/PC[15:0] to the BIO so the BIO's output-enable overrides the pinmux (per docs/src/ch03-00-io-configuration.md: "When selected, the BIO will override the 'output enable' control for the pad"). 3. Concretely it can: force a pad low/high via GPIOOUT+GPIOOE mid-transaction on the smart-card or SPI-slave link to corrupt or truncate an authentication exchange; retarget an INTCR wakeup source (0x5012_F100) so the `wkupvld_async` path -- which is a raw combinational function of the pad, iox.sv:111,128,134 -- fires or stops firing; or change GPIOCFG drive strength/slew (0x5012_F260) on a pad. 4. Because the same registers also select which pad each of the 8 IO interrupts watches, an attacker can silently detach a pin that firmware believes is being monitored.

**Mitigation.** RTL fix: drive `.ioxlock` from a sticky, write-once-to-1 register in sysctrl (or from a coreuser[5]/coreuser[4] boot-stage qualifier) rather than tying it to '0, so boot firmware can freeze the pin configuration; ideally split it into a per-port lock so late-boot code can still own its own pins. On already-fabricated silicon there is no way to enable the lock -- the mitigation is entirely software: treat the whole 0x5012_F000 page as a privileged resource, keep every code path that can reach it inside the trusted boundary, and re-verify (read back and compare) AFSEL/BIOSEL/GPIOOE before and after every security-relevant transaction on a pad-attached peripheral.

**Verification.** Independently confirmed by a second reviewer. Every link of the chain checks out. rtl/asic_top/rtl/soc_top.sv:772 is exactly `.ioxlock   ( '0    ),` and the only other instantiation, rtl/asic_top/rtl/soc_top_no_cm7_rv.sv:788, is identical - a repo-wide grep for `ioxlock` returns only those two ties plus the port declaration (soc_ifsub.sv:39, :837) and the single consumer soc_ifsub.sv:580 `.sfrlock    (ioxlock),`. iox.sv:34 `input logic sfrlock,` is real, and the register instances do pick it up through `.*`: apb_cr declares `input bit sfrlock` (apb_sfr.sv:90) and forwards it (apb_sfr.sv:114 `.sfrlock (sfrlock | '0 )`) into apb_sfr2, where apb_sfr.sv:333 `assign apbwr = ~sfrlock & apbslave.psel & apbslave.penable & apbslave.pwrite;` is the only write enable. So AFSEL (iox.sv:75), INTCR (iox.sv:137), GPIOOUT/OE/PU (iox.sv:156-158) and BIOSEL (iox.sv:259) are all gated by a signal that is provably stuck at 0 in silicon. I also confirmed the absence of any compensating access control on the path: iox sits on apbper[15] (soc_ifsub.sv:582) behind apb_mux, which only forwards pprot (amba_components.sv:311) and has no consumer, and grepping `coreuser` across rtl/ shows it exists only in soc_coresub/cm7sys/vexsys/sce - nothing filters the ifsub AHB or APB. So the grounded lock is the only protection mechanism that was ever designed for this page.

**Corrections applied by the verifier.** The severity is overstated. Because there is no privilege filtering anywhere on the ifsub bus, the lock would not have been separating two existing privilege domains - it is a missing hardening/lock-bit feature (defense in depth for a boot-stage freeze), not the bypass of a control that otherwise works. The attack described (steal a pad from SCIF/SPIS, hand pads to the BIO via BIOSEL, detach a wakeup source) is accurate but is available to any code that can reach the peripheral bus at all, with or without this port being tied off.

---

<a id="bao-083"></a>

### BAO-083 — SCIF (smart-card interface): externally-driven SCK pin becomes an internal functional clock, combined with the internal clock by a bare OR gate instead of a glitch-free mux

**Severity: Medium** | CWE-1247 Improper Protection Against Voltage and Clock Glitches in Hardware | Threat actor: T3 (plus T1 to set the register, or T2 if firmware already selects the mode) | Confidence: Medium

**Location:** `rtl/modules/ifsub/rtl/udma_scif.sv:217`

**Description.** In SCD mode the SCIF datapath clock `clkscif` is derived directly from the external `scif_sck_i` pad, gated by an ICG. In SCC mode it is derived from the internally divided `clkscc`. The two are merged with `assign clkscif_undft = clkscc | clkscd;` -- an ordinary OR gate, not a glitch-free clock mux (contrast the very next line, which does use a proper `CLKCELL_MUX2` for the DFT selection). The two enables `clksel[0]` (SCD) and `clksel[1]` (SCC) come from two independent bits of the same software register (`s_scif_clksel`, udma_scif.sv:184 -> udma_scif_reg.sv) and nothing prevents both from being set at once. The SCIF register file's `sfrlock` is never asserted (the uDMA peripheral register files have no lock at all -- they are plain always_ff decoders, e.g. udma_scif_reg.sv), so this is a software-reachable state. `clkscif` clocks `udma_scif_tx`, `udma_scif_rx`, the destination side of the TX dual-clock FIFO and the source side of the RX dual-clock FIFO (udma_scif.sv:292,320,335) -- i.e. glitches on it propagate into the token-ring pointer flops of a CDC FIFO whose other side runs on `sys_clk_i`. Note also that in mode 2'b11 the chip does not drive SCK (`scif_sck_oe` is only asserted for `s_scif_clksel == 2'h2`, line 240), so the external device has sole control of one leg of the OR.

**Evidence.**
```systemverilog
rtl/modules/ifsub/rtl/udma_scif.sv:204-219
    logic scif_sck_dft, clkscif_undft, scif_sck_dft_unbuf;
    assign scif_sck_dft_unbuf = dft_i ? periph_clk_i : scif_sck_i;
    CLKCELL_BUF buf_scif_sck_dft(.A(scif_sck_dft_unbuf),.Z(scif_sck_dft));
...
    assign clkscden = clksel_scdregs[2];

    ICG uclkscd ( .CK (scif_sck_dft), .EN ( clkscden ), .SE(dft_i), .CKG ( clkscd ));
    assign clkscif_undft = clkscc | clkscd;

    CLKCELL_MUX2 u_clkscif (.A(clkscif_undft),.B(periph_clk_i),.S(dft_i),.Z(clkscif));

rtl/modules/ifsub/rtl/udma_scif.sv:239-240 (chip stops driving SCK unless clksel==2)
    assign scif_sck_o = clksccen & clkscc;
    `theregfull( sys_clk_i, sys_rstn_i, scif_sck_oe, '0 ) <= ( s_scif_clksel == 2'h2 );

rtl/modules/ifsub/rtl/udma_scif.sv:318-330 (glitchy clock feeds a CDC FIFO whose far side is sys_clk)
    udma_dc_fifo #(8,4) u_dc_fifo_rx
    (
        .src_clk_i    ( clkscif            ),
        .src_rstn_i   ( s_per_combo_rstn   ),
...
        .dst_clk_i    ( sys_clk_i          ),
```

**Preconditions.** `s_scif_clksel` must be 2'b11 (both clock sources enabled) -- software-reachable at any time because the uDMA peripheral register files have no write-protect. The attacker must be able to drive the SCIF SCK pad, i.e. hold the connector or sit between the chip and the smart card. In mode 2'b11 the chip itself does not drive SCK, so no contention resolution is needed.

**Attack scenario.** 1. Firmware (or an attacker with T1 who can write the unlocked SCIF register file at the uDMA APB window) sets `s_scif_clksel = 2'b11`, enabling both the SCD and SCC clock sources. 2. `clksccen` and `clkscden` both become 1 after their 3-flop sync, so `clkscif_undft = clkscc | clkscd` becomes the OR of the internally divided clock and the free-running external SCK pin. 3. An attacker with physical access to the smart-card connector (T2/T3) drives SCK with arbitrary timing -- including edges placed a few hundred picoseconds from `clkscc` edges -- producing runt pulses and double-edges on `clkscif`. 4. Those runt pulses clock `udma_scif_rx` and the source side of `u_dc_fifo_rx`, whose gray/token-ring pointers are read from the `sys_clk_i` domain. Setup/hold violations on the ring pointers can make the FIFO report valid data that was never written, drop bytes, or stick, so the byte stream the CPU reads from the smart-card link no longer corresponds to what was on the wire. Because the SCIF is the natural transport for a PIN/authentication exchange with an external secure element, an attacker who can decide which bytes the host actually observes is attacking the authentication result, not merely availability. 5. The same primitive gives a targeted clock-glitch injection point into the SoC clock tree that does not require touching the main clock pin.

**Mitigation.** RTL fix: replace `assign clkscif_undft = clkscc | clkscd;` with a glitch-free clock mux (the CLKCELL_MUX2 already used one line below, driven by a synchronized select, or a standard two-stage handshake clock switch), and make `s_scif_clksel` one-hot-decoded so 2'b11 is illegal (e.g. `clkscden = clksel==2'h1`, `clksccen = clksel==2'h2`). Additionally add a proper reset synchronizer on `s_per_combo_rstn` for the FIFO. Silicon workaround: firmware must never write 2'b11 to the SCIF clksel field, and should verify the field after every write; treat the SCIF register page as privileged and validate all smart-card responses cryptographically (MAC/signature over the whole exchange) so that a corrupted byte stream cannot be mistaken for a successful authentication.

**Verification.** Verified as written; exploitability not fully established. The quoted RTL is exact: rtl/modules/ifsub/rtl/udma_scif.sv:217 `assign clkscif_undft = clkscc | clkscd;`, with the proper cell used one line later at :219 `CLKCELL_MUX2 u_clkscif (...S(dft_i)...)`, and :240 `theregfull( sys_clk_i, sys_rstn_i, scif_sck_oe, '0 ) <= ( s_scif_clksel == 2'h2 );`. The 2'b11 state is genuinely reachable: udma_scif_reg.sv:250 `r_scif_clksel <= cfg_data_i[15:14];` is a plain 2-bit field in an always_ff register file with no one-hot decode and no lock, and udma_scif.sv:214/226 derive clkscden and clksccen from bit[0] and bit[1] independently. With both set, an OR of the free-running external pad and the internally divided clock does produce runt pulses, and clkscif does clock the source side of the RX dual-clock FIFO (udma_scif.sv:320-326) whose destination is sys_clk_i - that part of the claim, unlike the SPIS one, is correct.

**Corrections applied by the verifier.** Impact is overstated on two points. (1) 'a targeted clock-glitch injection point into the SoC clock tree' is not supported: every consumer of clkscif is inside this peripheral (udma_scif.sv:292, 300, 320, 335, 353, 362, 371, 396) - it reaches no other block, so the blast radius is the SCIF byte stream only. (2) The entry condition requires software to write an illegal mode (clksel=2'b11) to the SCIF register file, i.e. the attacker must already have T1 code execution, at which point that same code already owns the SCIF datapath, its DMA descriptors and its buffers; corrupting the received byte stream buys nothing extra. The residual real defect is the non-glitch-free clock combining and the non-one-hot clksel decode, which is worth reporting as an RTL quality/robustness issue rather than as an authentication bypass.

---

<a id="bao-084"></a>

### BAO-084 — SPI slave: the external chip-select pad is used as the asynchronous reset of a dual-clock CDC FIFO in both of its clock domains, with no reset synchronizer

**Severity: Medium** | CWE-1298 Hardware Logic Contains Race Conditions | Threat actor: T3 | Confidence: Medium

**Location:** `rtl/modules/ifsub/rtl/udma_spis.sv:220`

**Description.** `fiforesetn` is built combinationally from the raw external chip-select pad `spis_cs_i` and is then used as the asynchronous reset of (a) the TX side `io_tx_fifo` clocked by `sys_clk_i`, and (b) BOTH the source (`periph_clk` == `sys_clk_i` here) and destination sides of `u_dc_fifo_rx`, a `udma_dc_fifo` token-ring CDC FIFO. In the same block `udma_spis_txrx.sv:70-72` also builds `spiresetn` from `~scsn` and derives both shift-register clocks directly from the external `sclk` pad. `udma_dc_fifo` contains no reset synchronizer of any kind (it just forwards `src_rstn_i`/`dst_rstn_i` into `dc_token_ring_fifo_din`/`_dout`), so an external SPI master fully controls the assertion AND the deassertion edge of a reset applied to one-hot token-ring flops that are sampled across a clock domain boundary. Reset removal is therefore asynchronous to `sys_clk_i` and violates recovery/removal timing on every CS edge the attacker chooses to place.

**Evidence.**
```systemverilog
rtl/modules/ifsub/rtl/udma_spis.sv:218-230
    logic fiforesetn, data_tx_req_o0;
    logic [2:0] data_tx_reqen;
    assign fiforesetn = cmsatpg ? rstn_i : rstn_i & ~spis_cs_i;

    `theregfull( sys_clk_i, fiforesetn, data_tx_reqen, '0 ) <= { data_tx_reqen , 1'b1 };
    assign data_tx_req_o = data_tx_req_o0 & data_tx_reqen[2];

    io_tx_fifo #(
      .DATA_WIDTH(8),
      .BUFFER_DEPTH(2)
      ) u_fifo (
        .clk_i   ( sys_clk_i       ),
        .rstn_i  ( fiforesetn          ),

rtl/modules/ifsub/rtl/udma_spis.sv:283-295 (same external pin resets both sides of the CDC FIFO)
    udma_dc_fifo #(8,4) u_dc_fifo_rx
    (
        .src_clk_i    ( periph_clk       ),
        .src_rstn_i   ( fiforesetn  ),
...
        .dst_clk_i    ( sys_clk_i          ),
        .dst_rstn_i   ( fiforesetn  ),

rtl/modules/ifsub/rtl/udma_spis_txrx.sv:68-72 (external pins as reset and as both datapath clocks)
    assign smisooe = ~scsn;

    assign spiresetn = cmsatpg ? resetn : ~scsn;
    assign clktx = cmsatpg ? clk : clktx0;
    assign clkrx = cmsatpg ? clk : clkrx0;

rtl/ips/udma/udma_core/rtl/common/udma_dc_fifo.sv:47-70 (no reset synchronizer anywhere)
 dc_token_ring_fifo_din #(
...
    .clk(src_clk_i),
    .rstn(src_rstn_i),
...
 dc_token_ring_fifo_dout #(
...
    ) u_dout (.clk(dst_clk_i),
    .rstn(dst_rstn_i),
```

**Preconditions.** Physical access to the SPI-slave chip-select line (the attacker is the SPI bus master, which is the block's normal operating assumption). Requires only that firmware has enabled the SPI slave and its RX DMA channel. No software cooperation and no privilege on the chip is needed.

**Attack scenario.** 1. Firmware enables SPI slave 0 and arms its uDMA RX channel to receive a command frame into IFRAM. 2. An attacker on the SPI bus (T3 -- the chip is the slave, so the external master owns CS and SCLK entirely) drives CS with deliberately short, repeated assert/deassert pulses whose deasserting edge is swept in fine steps relative to the internal `sys_clk_i` edge. 3. Each such edge asynchronously removes the reset on the `dst` side token-ring pointer flops of `u_dc_fifo_rx` while `sys_clk_i` is switching, violating recovery/removal. A metastable resolution can leave the write token and the read pointer inconsistent -- e.g. the destination side believing a slot is full when the source side never wrote it. 4. The result is that `data_rx_valid_o` asserts with the stale contents of a FIFO slot from the previous CS period, so the uDMA writes into the software's receive buffer a byte the attacker did not send in this frame, or drops/duplicates bytes so that the received frame no longer matches what was on the wire. Combined with a protocol where the host authenticates a command by inspecting the first N bytes, this gives the attacker a way to make a replayed byte from an earlier (possibly legitimate) frame appear inside a new frame. 5. Repeating the CS sweep gives many trials per second, so the low per-edge probability is not a defence.

**Mitigation.** RTL fix: do not use a raw pad as a flop reset. Synchronize `spis_cs_i` into `sys_clk_i` with a two-flop synchronizer before deriving `fiforesetn`, and use a proper asynchronous-assert/synchronous-deassert reset synchronizer on each side of `udma_dc_fifo` (one per clock domain). Keep the datapath shift-register reset (`spiresetn` in udma_spis_txrx.sv) on the pad if it must be, but drive the FIFO resets from the synchronized version, and use `cfg_rx_clr_o`/`clr_i` (already present as an unused input, tied 1'b0 at udma_spis.sv:231) for the per-frame flush instead of a reset. Software workaround on fabricated silicon: never trust framing or byte ordering from the SPI slave; require every command frame to carry a MAC or CRC plus a monotonic nonce computed over the whole frame, and discard any frame whose length or sequence number does not match, so replayed/duplicated bytes cannot be accepted.

**Verification.** Verified as written; exploitability not fully established. The quotes are accurate: udma_spis.sv:220 `assign fiforesetn = cmsatpg ? rstn_i : rstn_i & ~spis_cs_i;`, feeding u_fifo (:228) and both sides of u_dc_fifo_rx (:284-292); udma_spis_txrx.sv:68-72 `assign smisooe = ~scsn; assign spiresetn = cmsatpg ? resetn : ~scsn; assign clktx = cmsatpg ? clk : clktx0;`; and udma_dc_fifo.sv:47-70 does forward src_rstn_i/dst_rstn_i straight into the token-ring halves with no synchronizer. So the raw pad genuinely is an asynchronous reset on sys_clk_i flops with an unsynchronized release edge, which is a real recovery/removal exposure the attacker can sweep.

**Corrections applied by the verifier.** The central mechanism is misdescribed. udma_spis.sv:216 `assign periph_clk = sys_clk_i;` - u_dc_fifo_rx is instantiated with src_clk_i = periph_clk = sys_clk_i and dst_clk_i = sys_clk_i, so there is NO clock-domain boundary in this instance and no cross-domain pointer inconsistency is possible; both ring halves share one clock and one reset net. The described failure ('destination side believing a slot is full when the source side never wrote it', 'a byte from an earlier frame appears inside a new frame') cannot arise that way. Two further compensating facts the finder missed: io_generic_fifo.sv:88-100 explicitly clears the whole buffer array on reset (`for (loop1 = 0; loop1 < BUFFER_DEPTH; loop1++) buffer[loop1] <= 0;`), so a CS pulse cannot leave stale bytes to be replayed; and the genuine sclk->sys_clk handoff in udma_spis_txrx.sv:108-113 does use two-flop synchronizers on rxdatwr/txdatrdtog. What is left is a per-flop metastability risk on reset removal in a single clock domain, whose only realistic outcome is a corrupted or dropped frame - i.e. availability/integrity of data the attacking SPI master is itself supplying.

---

<a id="bao-085"></a>

### BAO-085 — SCIF SCC clock generator can latch stuck-at-1, permanently stopping the SCIF datapath clock and freezing the smart-card SCK pad

**Severity: Medium**

**Location:** `rtl/modules/ifsub/rtl/udma_scif.sv:236`

*Surfaced by the independent verifier, not the original domain reviewer.*

**Description.** The SCC clock waveform generator and its divider counter compare against two different signals. The counter wraps on `s_scif_div` (the live software register), while the high/low transitions of `clkscc` are decided by `r_scif_div`, a stale copy that is loaded ONLY on the rising edge of en_tx/en_rx (udma_scif.sv:259-262) and resets to 0. `clkscc` has no default branch - it holds its previous value whenever neither compare matches - and it is the only source that can clear `clkscif` (line 217 `clkscif_undft = clkscc | clkscd`). Two software-reachable inputs leave it latched at 1 forever: (a) divider = 0, where clksccdivcnt is pinned at 0 and the first branch (clksccdivcnt == r_scif_div/2 == 0) wins every cycle; (b) writing a new, smaller divider while the channel is enabled, so the counter wraps below r_scif_div/2 and neither compare is ever reached again. With clkscc stuck high, clkscif is a constant 1: udma_scif_tx/rx and both SCIF FIFO ports (lines 292-396) never clock again, and the pad output `scif_sck_o = clksccen & clkscc` (line 239) is frozen high, stopping the clock supplied to the external smart card outside of any negotiated clock-stop protocol. Recovery requires per_rstn_i, not just a register rewrite.

**Evidence.**
```systemverilog
rtl/modules/ifsub/rtl/udma_scif.sv:234-236
    else begin
        clksccdivcnt <= ( clksccdivcnt == s_scif_div ) ? '0 : clksccdivcnt + clksccen;
        clkscc <= ( clksccdivcnt == r_scif_div/2 ) & clksccen ? 1'b1 : ( clksccdivcnt == r_scif_div ) ? 1'b0 : clkscc;
    end

rtl/modules/ifsub/rtl/udma_scif.sv:239
    assign scif_sck_o = clksccen & clkscc;

rtl/modules/ifsub/rtl/udma_scif.sv:217
    assign clkscif_undft = clkscc | clkscd;

rtl/modules/ifsub/rtl/udma_scif.sv:255-262 (r_scif_div is stale: reset to 0, loaded only on an enable edge)
        if(~per_rstn_i) begin
            ...
            r_scif_div <= '0;
        end else begin
            ...
            if(s_scif_tx_sample2 || s_scif_rx_sample2)
            begin
                r_scif_div        <= s_scif_div;
            end
        end
```

**Attack scenario.** Any code that can reach the uDMA APB window (the SCIF register file has no lock - udma_scif_reg.sv:250 `r_scif_clksel <= cfg_data_i[15:14];` is a plain always_ff decoder, and no coreuser/pprot check exists on the ifsub path) writes divider=0, or lowers the divider while the SCIF channel is enabled. clkscc latches high, clkscif stops toggling, and the SCIF is dead until the peripheral reset is asserted - a lower-privileged task can therefore permanently disable a smart-card/secure-element link that a higher-trust context depends on, and can freeze SCK high on the card mid-session. The same latch also defeats a later switch to SCD (external-clock) mode, because the stuck clkscc holds the OR gate at 1 and masks clkscd entirely.

**Verification.** No independent verdict recorded for this entry.

---

<a id="bao-086"></a>

### BAO-086 — SCE ownership can never be granted to the VexRiscv: sce_sec compares against AMBAID4_VEXD (0x4) but the only Vex port that reaches the SCE drives AMBAID4_VEXP (0xD), so a Vex-initiated secure session is owned by the Cortex-M7

**Severity: Low** | CWE-1294 Insecure Security Identifier Mechanism | Threat actor: T1 (unprivileged software on the CM7); the victim is the Vex's secure session | Confidence: High

**Location:** `rtl/modules/crypto_top/rtl/sce_sec.sv:62`

**Description.** `sce_sec` identifies the requesting master by the AHB user tag and uses that to (a) capture which CPU's coreuser bundle becomes the SCE owner and (b) gate every subsequent access. Both the capture (lines 61-62) and the gate (lines 72-74) test `ahbs.hauser == daric_cfg::AMBAID4_VEXD`, which is 4'h4 (daric_cfg_pkg.sv:74). But AMBAID4_VEXD is the tag of the Vex *data AXI* master, which is routed to the nic400 and only reaches ReRAM/SRAM/QFC - it never reaches the SCE's AHB slave. The only Vex port that reaches 0x4002_0000 is its peripheral port, and that port drives AMBAID4_VEXP = 4'hD (daric_cfg_pkg.sv:81; vexsys.sv:166,178 `assign paxim.aruser = AHBPID4 | '0;` with `.AHBPID4 (daric_cfg::AMBAID4_VEXP)` at soc_coresub.sv:402). I verified the tag survives the path: `ahb_thru _ahbp1( .ahbslave( vex_ahbp ), .ahbmaster( core_ahbp3[1] ) );` (soc_coresub.sv:613) then `ahb_mux3` explicitly muxes it through (amba_components.sv:276 `assign ahbmaster.hauser = (msel == 2) ? ahbslave[2].hauser : (msel == 1) ? ahbslave[1].hauser : ahbslave[0].hauser ;`) and `ahb_demux_map` forwards it unchanged (ahb_demux.sv:113). Consequences: (1) the Vex branch of the capture mux at line 62 is unreachable, so `coreuserselreg` can only ever be 0 and `coreuserreg` can only ever hold the CM7's identity; (2) when the Vex writes `scemode` to a non-zero value, `sceuserlock` fires and `sceuser`/`sceusersel` are loaded with the *Cortex-M7's* identity (or with the reset value 8'h00 if the CM7 has not touched the SCE since the last SCE reset); (3) `ahben` then evaluates `( ahbs.hauser == AMBAID4_CM7P ) & ( coreuser_cm7 == sceuser )`, so the CM7 - a different CPU, on the other side of the SoC's inter-core isolation boundary - is the one granted access to the session the Vex opened, while the Vex is permanently locked out of the SCE it just configured.

**Evidence.**
```systemverilog
rtl/modules/crypto_top/rtl/sce_sec.sv:61-64
    `theregrn( {coreuserselreg, coreuserreg} ) <=   ahbscpvld & ( ahbs.hauser == daric_cfg::AMBAID4_CM7P ) ? { 1'b0, coreuser_cm7 } :
                                                    ahbscpvld & ( ahbs.hauser == daric_cfg::AMBAID4_VEXD ) ? { 1'b1, coreuser_vex } : {coreuserselreg, coreuserreg};

    `theregrn( {sceusersel, sceuser} ) <= sceuserlock ? {coreuserselreg, coreuserreg} : {sceusersel, sceuser};

rtl/modules/crypto_top/rtl/sce_sec.sv:72-74
    assign ahben =  mode_non ? 1'b1 :
                            ((sceusersel == 0 ) ? ( ahbs.hauser == daric_cfg::AMBAID4_CM7P ) : ( ahbs.hauser == daric_cfg::AMBAID4_VEXD )) &
                            ((sceusersel == 0 ) ? ( coreuser_cm7 == sceuser ) : ( coreuser_vex == sceuser ));

rtl/asic_top/rtl/daric_cfg_pkg.sv:74,81
    localparam bit [3:0] AMBAID4_VEXD = 4'h4;
    localparam bit [3:0] AMBAID4_VEXP = 4'hD;

rtl/modules/core/rtl/vexsys.sv:166,178
    assign paxim.aruser = AHBPID4 | '0;
    assign paxim.awuser = AHBPID4 | '0;

rtl/modules/soc_coresub/rtl/soc_coresub.sv:400-403
        .AXIIID4       (daric_cfg::AMBAID4_VEXI),
        .AXIDID4       (daric_cfg::AMBAID4_VEXD),
        .AHBPID4       (daric_cfg::AMBAID4_VEXP)

rtl/modules/amba/rtl/amba_components.sv:276
 assign ahbmaster.hauser = (msel == 2) ? ahbslave[2].hauser : (msel == 1) ? ahbslave[1].hauser : ahbslave[0].hauser ;
```

**Preconditions.** The Vex must be an enabled core (`coreselvex` magic word present in ReRAM, soc_coresub.sv:273) and must be the agent that opens the SCE secure session. The CM7 needs only unprivileged code execution and the ability to issue one load to 0x4002_0000 while the SCE is in mode_non - which is the state after every reset. If the CM7 never touches the SCE, `coreuserreg` stays at its reset value 8'h00 and the SCE becomes unusable by anyone (`coreuser_cm7` is never 8'h00 once cm7sys has run, because cm7sys.sv:761 forces the fw1 bit for any PC outside boot0/boot1/fw0), which is a hard denial of service rather than a leak.

**Attack scenario.** Deployment where the Vex is the security core (the ReRAM `coreselvex` magic word is programmed, soc_coresub.sv:273) and the CM7 runs the untrusted application:
1. The CM7 - which needs no privilege at all, because `mode_non` leaves `ahben` unconditionally 1 - issues a single dummy load from 0x4002_0000 while executing in whatever code region it wants to impersonate. That access has `hauser == AMBAID4_CM7P`, so `ahbscpvld` is true and `coreuserreg` is loaded with the CM7's current coreuser and `coreuserselreg` with 0.
2. The Vex secure firmware now brings the SCE up: it writes 0x4002_8000 with scemode = 2 (secure). Because the Vex's tag is 0xD, that write does NOT update `coreuserreg`. `sceuserlock` fires on the 0->non-zero transition of `scemodereg` and latches `{sceusersel, sceuser} = {1'b0, <CM7 coreuser from step 1>}`.
3. The Vex loads keys into SKEY/AKEY/PKB and programs the engines - it can still do this, because it does so through the SCE DMA... no: every one of those accesses also goes through the same AHB slave, and `ahben` is now 0 for hauser 0xD. The Vex is locked out of the SCE entirely (denial of service, and the Vex's own driver silently reads zeros and silently drops writes - see the ahb_gate behaviour in finding 5).
4. The CM7, whose identity was latched, now satisfies `ahben` whenever it executes from the region it primed in step 1. It has full owner-level access to the SCE control plane in secure mode: it can program the SCE DMA at 0x4002_9000 (which asserts `sce_sec_op` in the ReRAM controller and unlocks ReRAM key-slot reads), drive the AES/PKE/hash engines as a signing and decryption oracle with keys it cannot read, and read the bus-readable output segments SOB (0x4002_0700), PSOB (0x4002_1800) and AOB (0x4002_1E00).
Even in the symmetric configuration where both cores are enabled, the effect is the same: SCE ownership is structurally unassignable to the Vex, and any Vex attempt to open a secure session hands the session to whichever CM7 context last touched the SCE.

**Mitigation.** RTL fix: change both occurrences of `daric_cfg::AMBAID4_VEXD` in sce_sec.sv (lines 62 and 73) to `daric_cfg::AMBAID4_VEXP`, since 0xD is the only Vex identity that can ever appear on this AHB slave. Better still, replace the hard-coded pair of magic IDs with a parameterised table so a future ID reassignment cannot silently break the comparison, and add a default arm that forces `ahben = 0` and raises an error for any hauser that matches neither entry - today an unrecognised hauser simply fails the comparison, which is safe, but the capture register silently retains a stale identity, which is not. Software workaround on fabricated silicon: the Vex must never be relied upon to own an SCE session - all SCE use must be funnelled through the CM7 peripheral port. If the product's threat model requires the Vex to hold secrets the CM7 cannot reach, that isolation does not exist in this silicon and the design must fall back to keeping the CM7 in a fully trusted role, or to not using the SCE at all from the Vex.

**Verification.** Independently confirmed by a second reviewer. I independently traced the whole path and reproduced this. The constants are as quoted: daric_cfg_pkg.sv:74 `AMBAID4_VEXD = 4'h4`, :81 `AMBAID4_VEXP = 4'hD`. sce_sec.sv:61-62 and :73 are verbatim as quoted and both test AMBAID4_VEXD. The SCE slave is coreahbmux[2] (soc_coresub.sv:544 `.ahbs ( coreahbmux[2] )`), fed by coreahb_mux from core_ahb32 (soc_coresub.sv:628-637), which bmxcore drives from ahb_bmx33 (bmxcore.sv:272 `ahb_thru bmx33m1 ( .ahbslave(bmx33m[1]), .ahbmaster(core_ahb32) );`). The three ahb_bmx33 slave ports are sce_ahb (SCE's own AXI, id SCEA=0x5), the mdma/bdma mux, and cm7_ahbp (bmxcore.sv:268-270). vex_daxi is NOT among them - bmxcore.sv:287-299 routes vex_daxi only to nic1_intf .s4 whose masters are rrc/sram0/sram1/qfc. So hauser==4'h4 can never appear at the SCE AHB slave. The Vex's only route is vex_ahbp -> core_ahbp3[1] (soc_coresub.sv:613) -> ahb_mux3 (which explicitly forwards hauser, amba_components.sv:275) -> cm7_ahbp -> bmx33s[2]. And that port carries 0xD: vexsys.sv:166/178 drive paxim.aruser/awuser = AHBPID4, parameterised AHBPID4=AMBAID4_VEXP at soc_coresub.sv:402, and axi_ahb_bdg propagates it to the AHB tag at aab_intf.sv:116 `assign ahbmaster.hauser = uaab.HAUSER;`. For contrast the CM7 path is cm7sys.sv:695 `assign ahbp0.hauser = AHBPID4;` with AHBPID4=AMBAID4_CM7P (soc_coresub.sv:331). Consequences follow mechanically: coreuserselreg can only ever be 0, so sceusersel is always 0, so ahben in any non-mode_non state requires hauser==CM7P; the Vex is structurally locked out and any Vex-opened session is owned by whatever CM7 coreuser was last captured (or by the reset value 8'h00 if none). I searched for a compensating control (an alternative capture path, a second comparator, a parameter override) and found none - the sce_sec devmode[0] bit that the comment at sce.sv:132 calls 'ahben bypass' only drives ahbs_lock (sce_sec.sv:77), and ahbs_lock is declared at sce.sv:109 and used nowhere, so it is dead.

**Corrections applied by the verifier.** The RTL defect is unconditional and confirmed. The specific 'CM7 hijacks the Vex's secure session' attack is deployment-dependent: it needs both cores enabled (soc_coresub.sv:272-273, vexcfg_enreg/cm7cfg_enreg from the ReRAM magic words) and the Vex opening the session. In a Vex-only build (cm7cfg_en = ~vexcfg_enreg | cm7cfg_enreg = 0) the CM7 never issues a transfer, coreuserreg stays at its reset 8'h00, and the result is a hard denial of service rather than a hijack - the SCE becomes unusable in mode_xls/mode_sec by anyone. Also, the finder's step 3 correctly self-corrects mid-sentence; the Vex is locked out for its own key loads too, so the CM7 inherits an empty session unless the CM7 itself loads the keys.

---

<a id="bao-087"></a>

### BAO-087 — QFC XIP AES key and AES enable are unlocked APB control registers writable by any bus master, so software can disable or re-key external-flash decryption

**Severity: Low** | CWE-1231 Improper Prevention of Lock Bit Modification (security-critical key/enable register lacks any write protection) | Threat actor: T1 for the register writes; combined with T3 (attacker owns the external QSPI/XIP flash device) for arbitrary code/data injection into the XIP window | Confidence: High

**Location:** `rtl/modules/core/rtl/qfc.sv:202`

**Description.** `qfc` hardwires its SFR lock to zero with a flop that is permanently reset to '0, and then instantiates the 128-bit XIP AES key and the AES enable bit as ordinary `apb_cr` registers under that lock. `apb_cr` derives its write strobe as `assign apbwr = ~sfrlock & apbslave.psel & apbslave.penable & apbslave.pwrite;` (apb_sfr.sv:333), so with `sfrlock` tied to 0 the key and the enable are freely writable for the life of the chip by anything that can reach the APB. The key is not read-back-able - `cr_aeskey.prdata32` is deliberately omitted from the `apbx.prdata` OR-list at qfc.sv:183-189 - but write-only is not a protection here: the security property that matters for an execute-in-place path is that the key and the enable cannot be CHANGED, and neither is protected. `aesena` and `aeskeyin` are the only two security inputs the wrapper passes to the closed decryption core (qfc.sv:360-361); the in-repo module named `qfc_aes` that sits in the AXI path is a verified pure pass-through with no cipher, no key and no integrity check whatsoever (qfc_aes.sv:24-74), so there is no second, independent integrity gate on data returned from external flash. There is also no lifecycle gate: `qfc_en` comes from a ReRAM config word and resets to the PERMISSIVE value (`theregfull( pclk, resetn, qfc_en, '1 )`, soc_coresub.sv:287), so the XIP path is live before the boot read can disable it.

**Evidence.**
```systemverilog
rtl/modules/core/rtl/qfc.sv:156, 176
    logic sfrlock;
...
    `theregrn( sfrlock ) <= '0;

rtl/modules/core/rtl/qfc.sv:202-203
    apb_cr #(.A('h40), .DW(32), .SFRCNT(4)) cr_aeskey      (.cr(aeskeyin), .prdata32(),.*);
    apb_cr #(.A('h50), .DW(1))              cr_aesena      (.cr(aesena), .prdata32(),.*);

rtl/modules/core/rtl/qfc.sv:360-361 (these two are the only security inputs to the closed core)
    .aesena,
    .aeskeyin,

rtl/modules/amba/rtl/apb_sfr.sv:332-333 (what sfrlock=0 means)
    assign apbrd = apbslave.psel & apbslave.penable & ~apbslave.pwrite;
    assign apbwr = ~sfrlock & apbslave.psel & apbslave.penable & apbslave.pwrite;

rtl/modules/core/rtl/qfc_aes.sv:24-26 (the in-path 'aes' module is a wire-through)
    assign axim.arvalid =   axis.arvalid ;
    assign axim.araddr =    axis.araddr ;
    assign axim.arid =      axis.arid ;

rtl/modules/soc_coresub/rtl/soc_coresub.sv:287 (XIP enabled by default out of reset)
    `theregfull( pclk, resetn, qfc_en, '1 ) <= ( nvrcfgdata.cfgcore.qfc_disable == 'h0 );
```

**Preconditions.** Attacker can write 0x4001_0040-0x4001_004C and 0x4001_0050. The QFC APB is `coresubapbs[0]` (soc_coresub.sv:882-883) inside the 0x4001_0000 window that `coreahb_demux_map` idx 1 maps to the coresub APB bridge - reachable from the CM7 AHB-P, the Vex AHB-P, the MDMA and the BDMA AHB master, with no privilege or coreuser filter on that path. The XIP window itself (0x8000_0000-0x9FFF_FFFF via nic400 m3) is likewise unfiltered.

**Attack scenario.** 1. The product ships with an encrypted XIP image in external QSPI flash; boot code installs the provisioned key at 0x4001_0040-0x4001_004C and sets `aesena`=1 at 0x4001_0050. Nothing locks either register afterwards, because `qfc.sv:176` ties `sfrlock` to 0.
2. Attacker with T3 desolders/reflashes the external SPI device (or interposes on the bus) and places his own payload there. He also gains any code execution that can reach the coresub APB - unprivileged CM7 code, Vex code, or an MDMA transfer (finding 2).
3. He writes 0 to 0x4001_0050, clearing `aesena`. The closed SPI core now returns the flash contents to the AXI fabric verbatim, and `qfc_aes` (qfc_aes.sv) passes them through untouched. The attacker's plaintext payload is now readable and executable at 0x8000_0000.
4. Alternatively he writes his own 128-bit key at 0x4001_0040 and supplies ciphertext encrypted under it, achieving the same result while keeping `aesena` set - which defeats any firmware self-check that merely verifies `aesena` is still 1.
5. He redirects the CM7 (or Vex) to fetch from 0x8000_0000. Per finding 1, code fetched from the XIP window makes `coreuserreg0pre[6:4]` all-zero, so `coreuser[7]` - the bit rrc.sv treats as the 'fw1' identity - is asserted. The attacker's off-chip code therefore executes with a ReRAM key/code-region identity that no legitimate on-chip firmware can even present.
6. Because the CFG-region check is also broken (finding 1) and the attacker's code now runs, he can proceed to rewrite the ACRAM and read ReRAM key slots.

**Mitigation.** RTL fix: drive `qfc.sfrlock` from a set-only lock bit (or from a dedicated one-way `aeskey_lock` register) instead of `'0`, so that boot code can install the key and enable and then latch them until reset; make `cr_aesena` a sticky set-to-1 bit that cannot be cleared by software; and gate the whole QFC SFR block on privilege plus a coreuser identity, since 'anything on the APB' is far too wide for a key register. Provide a genuine integrity check (MAC/authenticated mode) on XIP fetches rather than confidentiality alone - the current design has no in-repo integrity path at all. Also make `qfc_en` reset to the RESTRICTIVE value (0) and only open after the ReRAM boot read completes, rather than resetting to '1.
Silicon workaround: (a) set `qfc_disable` in the ReRAM core config so `qfc_en` goes to 0 immediately after the boot read, which holds the entire QFC in reset (`resetnqfc = qfc_en & resetn`, soc_coresub.sv:868) and gates its clocks - this is the only durable mitigation, and it means giving up XIP; (b) if XIP is required, never treat XIP contents as trusted: boot code must copy the image into ReRAM or SRAM and verify a signature over it with the SCE before executing, and must never branch directly into 0x8000_0000; (c) restrict which masters can reach 0x4001_0000 (see the MDMA mitigation) and have firmware periodically re-verify `aesena` - though note that re-keying keeps `aesena` set, so polling that bit alone is insufficient.

**Verification.** Independently confirmed by a second reviewer. Verified verbatim: qfc.sv:176 sfrlock tied to a permanently-'0 flop; qfc.sv:202-203 `apb_cr #(.A('h40), .DW(32), .SFRCNT(4)) cr_aeskey` and `apb_cr #(.A('h50), .DW(1)) cr_aesena` under that lock; qfc.sv:183-189 confirms cr_aeskey.prdata32 is omitted from the read OR-list so the key is write-only while aesena is readable; qfc.sv:360-361 confirms these two are the only security inputs to the closed core. apb_sfr.sv:333 `assign apbwr = ~sfrlock & apbslave.psel & apbslave.penable & apbslave.pwrite;` confirms sfrlock=0 means always-writable — note the cited module is apb_sfr2, reached via apb_cr -> apb_sfr2 (apb_sfr.sv:102-119), which I checked. QFC is coresubapbs[0] = 0x4001_0000 (soc_coresub.sv:882-883). soc_coresub.sv:287 `\`theregfull( pclk, resetn, qfc_en, '1 ) <= ( nvrcfgdata.cfgcore.qfc_disable == 'h0 );` quoted correctly — reset value is permissive. I also checked qfc.sv:321 (`i_apb_slv_sel(apbx.psel & apbx.paddr[9])`, a looser decode than apbx_psel1) and confirmed it lies inside a /* */ comment block, so there is no aliased shadow window — worth stating because it is the kind of thing that would otherwise look like a second bug.

**Corrections applied by the verifier.** The RTL defect is real; the impact analysis is inflated. (a) Cited line is off: `sfrlock` is declared at qfc.sv:156 and driven at qfc.sv:176 `\`theregrn( sfrlock ) <= '0;` — line 202-203 is the register instantiation, which is correctly quoted. (b) Attack step 3 gains the attacker nothing on confidentiality: with aesena=1 the XIP window at 0x8000_0000 already returns DECRYPTED plaintext to any master, so clearing aesena does not reveal anything an on-chip attacker could not already read. The real impact is narrower and should be reported as: no lock bit exists to bind the key+enable after boot, so (i) an attacker with T3 who also has any APB write can supply chosen ciphertext and read back its decryption under the provisioned key — a decryption oracle against the flash key — and (ii) firmware cannot make 'XIP is encrypted' a durable post-boot invariant. (c) Attack steps 5-6 are void: they depend on finding 1, which is refuted. Code fetched from 0x8000_0000 asserts only coreuser[7], which rrc.sv:815 treats as NOT boot0/boot1, so cfg_prev_dis=1 and the ACRAM rewrite is denied. (d) The qfc_aes.sv pass-through observation is correct (verified: qfc.sv:244-249 instantiates it live on axis->axix and qfc_aes.sv:24-74 is pure wire-through), but the cipher is inside the closed sdvt_spi_master_core taking aesena/aeskeyin (qfc.sv:360-361); concluding 'no integrity check whatsoever' is an inference about a black box, not RTL evidence. (e) The finder missed a partial compensating control: soc_coresub.sv:866-867 gates both QFC clocks with ICGs on qfc_en and `assign resetnqfc = cmsatpg ? resetn : qfc_en & resetn;`, so provisioning qfc_disable holds the whole block, including its SFRs, in reset.

---

<a id="bao-088"></a>

### BAO-088 — HF_INIT loads the entire hash constant table (SHA-2 IVs and round constants, SHA-3 rho offsets and round constants) from bus-writable crypto RAM, and that region is deliberately excluded from the SCE RAM wipe

**Severity: Low** | CWE-1233 Security-Sensitive Hardware Controls with Missing Lock Protection (attacker-writable algorithm constants, no lock, no zeroization) | Threat actor: T1 (any software able to reach the SCE window before or while it is unlocked) | Confidence: High

**Location:** `rtl/modules/crypto_top/rtl/combohasha.sv:580`

**Description.** The hash engine holds no hard-coded constants. Every initialisation vector and round-constant table lives in the first INITSIZE = hash_pkg::RAMSEG_CHACHA20_H = 428 words of the private hash RAM (HRAM), and the only way to populate them is HF_INIT, which DMAs SCERAM words 0..427 verbatim into HRAM words 0..427 (combohasha.sv:78-87, SEG_INIT has segaddr:'0, segsize:INITSIZE; combohasha.sv:580-588, MFSM_LD_INIT). Per hash_pkg.sv:90-104 that region is exactly the SHA-256 IV (HRAM 0..7), SHA-256 K (8..71), SHA-512 IV (72..87), SHA-512 K (88..247), the BLAKE2/3 IVs and tables (248..313), the RIPEMD tables (314..369), the SHA-3 rho-offset table (370..379) and the 24 Keccak round constants (380..403). SCERAM words 0..427 span SEG_LKEY, SEG_KEY, SEG_SKEY, SEG_SCRT, SEG_MSG and part of SEG_HOUT, every one of which permits AHB writes (scedma_pkg.sv:250-255). So any master that can write the SCE crypto RAM chooses the arithmetic constants of every hash algorithm in the chip. Worse, the poisoning persists across the security boundary: the HRAM cryptoram is instantiated with .clrstart(INITSIZE) (combohasha.sv:857), so the sceramclr wipe FSM (cryptoram.sv:61-68) starts at word 428 and runs to WCNT-1=767 - HRAM words 0..427 are never cleared by sfr_arclr, sfr_arrst, mode-quit or any SCE reset. There is no integrity check, no lock bit, and no way for later, more-privileged code to detect tampering short of running its own known-answer test.

**Evidence.**
```systemverilog
combohasha.sv:59
    localparam INITSIZE = hash_pkg::RAMSEG_CHACHA20_H;

combohasha.sv:78-87 (source segment is SCERAM address 0, length 428)
    localparam segcfg_t SEG_INIT =
        '{  segid:      '0 ,
            segtype:    ST_BI,
            ramsel:     'd0,
            segaddr:    '0 ,
            segsize:    INITSIZE ,

combohasha.sv:580-588
            MFSM_LD_INIT     :
                begin
                    chnli_cfg.rpsegcfg = SEG_INIT;
                    chnli_cfg.wpsegcfg = HASHSEG_INIT;
                    chnli_cfg.opt_ltx     = cr_segltx[0] | '0;
                    chnli_cfg.rpptr_start = '0;
                    chnli_cfg.transsize = INITSIZE;
                    chnli_en = '1;
                end

combohasha.sv:854-858 (the wipe deliberately skips the constants)
    cryptoram #(
        .ramname    ("HRAM"), // HRAM, PRAM, ARAM, SCERAM
        .thecfg     (thecfg),
        .clrstart   (INITSIZE)
    )m(

cryptoram.sv:24-25 and 61-63 (clear runs clrstart..clrend only)
    parameter clrstart = '0,
    parameter clrend = thecfg.WCNT-1
...
    assign ramclrdone = ( ramclrfsm == clrend );
    `theregrn( ramclrfsm ) <= ramclr ? clrstart :
                              ramclrdone ? '0 : ramclrfsm + ramclren;

hashcore.sv:45-58 (what lives in those 428 words)
    localparam RAMSEG_SHA256_H   = 0 ;
    localparam RAMSEG_SHA256_K   = RAMSEG_SHA256_H   + 8    ;
    localparam RAMSEG_SHA512_H   = RAMSEG_SHA256_K   + 64   ;
    localparam RAMSEG_SHA512_K   = RAMSEG_SHA512_H   + 8*2  ;
...
    localparam RAMSEG_SHA3_P0    = RAMSEG_RIPMD_X    + 40   ;
    localparam RAMSEG_SHA3_P1    = RAMSEG_SHA3_P0    + 10   ; //48

hashcore.sv:577 and 585 (constants read straight out of that table every round)
    assign ramseg_k =   ( thecfg.hashtype == HT_SHA256 ) ? RAMSEG_SHA256_K : RAMSEG_SHA512_K;
    assign rambase = hashrndcyc == 4 ? ramseg_k : ramseg_msg;
```

**Preconditions.** Write access to 0x4002_0000..0x4002_06AF and to the COMBOHASH SFR page. Both are open to any AHB master while scemode==0 (the reset state), so the attacker only needs to run once, before whoever claims the SCE. If the attacker instead owns the SCE in mode_sec, all six of those segments still permit AHB writes under ACRULEs, so the same attack works.

**Attack scenario.** Attacker = unprivileged software (T1) able to reach the SCE window at 0x4002_xxxx - which, per sce_sec.sv:72 ('assign ahben = mode_non ? 1'b1 : ...'), is every AHB master while scemode==0, i.e. from reset until some code claims the SCE.
1. Attacker writes a doctored 428-word constant image over 0x4002_0000..0x4002_06AF (SEG_LKEY/KEY/SKEY/SCRT/MSG/HOUT - all AHB-writable). For example it leaves the SHA-256 IV alone but replaces the 64-entry K table with one for which it has precomputed a collision pair, or simply zeroes K so the compression function becomes trivially collidable.
2. Attacker writes COMBOHASH_SFR_CRFUNC = 0xff (HF_INIT) and 0x5a to SFR_AR. MFSM_LD_INIT copies all 428 words into HRAM 0..427.
3. Attacker restores the SCERAM contents so nothing looks amiss, then yields to the next boot stage.
4. The next stage claims the SCE (writes scemode) and may issue sfr_arclr / sfr_arrst to 'wipe' the crypto RAM before use. Because the HRAM clear FSM starts at word 428, the poisoned constants survive intact.
5. Every subsequent SHA-256/SHA-512/SHA-3/BLAKE hash in the chip - including secure-boot image measurement and the HMAC that drives truststate - is computed with the attacker's constants. The attacker supplies a rogue image whose doctored-SHA-256 digest equals the reference digest, and secure boot accepts it.
Because these are the only constants the engine has, there is no known-good copy in silicon to fall back on.

**Mitigation.** RTL: hold the IVs and round constants in ROM or hardwired constants rather than a bus-loadable RAM region; or at minimum make HF_INIT one-shot per SCE reset (latch a constants_loaded flag cleared only by sceresetn) and make sceramclr cover HRAM word 0 (.clrstart('0)) so entering or leaving a secure mode forces the new owner to reload the constants. Sourcing SEG_INIT from SCERAM address 0 - which aliases the key segments - should also be changed to a dedicated non-key segment.
Already-fabricated silicon: the boot ROM must (a) claim the SCE (write scemode) and load the constant table via HF_INIT itself, before any third-party code executes, and (b) re-run HF_INIT plus a known-answer test (e.g. SHA-256 of the empty string compared against a hardcoded digest) immediately before every security-critical hash, since nothing else can detect a poisoned table. Note re-running HF_INIT requires writing 428 words into the key segments, so the KAT must be done where clobbering SEG_LKEY/KEY/SKEY/SCRT/MSG is acceptable.

**Verification.** Independently confirmed by a second reviewer. Verified end to end.

- INITSIZE arithmetic: hash_pkg.sv:90-104 gives RAMSEG_SHA3_P1 = 380 and hash_pkg.sv:104 `RAMSEG_CHACHA20_H = RAMSEG_SHA3_P1 + 48` = 428. combohasha.sv:59 `localparam INITSIZE = hash_pkg::RAMSEG_CHACHA20_H;` So INITSIZE = 428, exactly as claimed.
- combohasha.sv:78-87 SEG_INIT with `segaddr: '0, segsize: INITSIZE` — verbatim correct.
- combohasha.sv:580-588 MFSM_LD_INIT with `rpsegcfg = SEG_INIT`, `rpptr_start = '0`, `transsize = INITSIZE` — verbatim correct. Source is SCERAM word 0.
- combohasha.sv:854-858 `.clrstart(INITSIZE)` — verbatim correct, and cryptoram.sv:24-25 shows `clrend` defaults to `thecfg.WCNT-1` = 767 (combohasha.sv:836 WCNT: 256*3). cryptoram.sv:61-63 confirms the clear FSM runs clrstart..clrend, so HRAM words 0..427 are never wiped by any sceramclr.
- The wipe is otherwise real: sce_sec.sv `sceramclr = ( initregs == 4'h7 ) | ar_clrram` pulses after every sceresetn deassertion, so this genuinely survives mode-quit and sfr_arrst.
- SCERAM 0..427 aliasing is correct: SEGADDR_LKEY=0/64, KEY=64/64, SKEY=128/64, SCRT=192/64, MSG=256/128, HOUT=384/64 (scedma_pkg.sv:211-216), all with AHB write permitted (accessrule index 1 = 1 for LKEY/KEY/SKEY/SCRT/MSG at scedma_pkg.sv:292-296, and HOUT 8'b01_00_00_10 at :297 also has index 1 = 1).
- Consumption is real and broader than the finder stated: hashcore.sv:577/585 read the SHA-2 K table every round; hashcore_sha3.sv:195/302-303 read the rho/pi table from RAMBASE_P0=RAMSEG_SHA3_P0 and the 24 round constants from RAMBASE_P1=RAMSEG_SHA3_P1 (hashcore.sv:418-419), both inside the un-wiped region; hashcore_blk.sv:61-63/78 reads the BLAKE sigma message-permutation table from ramseg_x = RAMSEG_BLK2_X / RAMSEG_BLK3_X, also inside it. There is no ROM copy of any constant anywhere in the design (grep for the SHA-256 K values returns nothing in rtl/).
- No lock bit, no one-shot flag, no integrity check on HF_INIT exists.

**Corrections applied by the verifier.** One numeric correction: the Keccak round-constant table is 48 words (HRAM 380..427, 24 lanes x 64 bits), not 380..403; the 0..427 total is right. Also worth adding to the report: the BLAKE sigma permutation table (hashcore_blk.sv:61-63, ramseg_x) and the SHA-3 rho/pi offsets (hashcore_sha3.sv:195, RAMBASE_P0) are in the same un-wiped region, so poisoning is not limited to IVs and round constants. Severity high is appropriate: the escalation is specifically that the poison survives the SCE reset + RAM wipe that a new owner would reasonably rely on.

---

<a id="bao-089"></a>

### BAO-089 — SCE ownership is latched from the last AHB transfer to touch the SCE region rather than from the agent that wrote scemode, and transfers that the access-control gate just denied still update the ownership capture register

**Severity: Low** | CWE-367 Time-of-check Time-of-use (TOCTOU) Race Condition | Threat actor: T1 (unprivileged software on the CM7, or any master able to place a transfer on the SCE slave during the window) | Confidence: Medium

**Location:** `rtl/modules/crypto_top/rtl/sce_sec.sv:64`

**Description.** The ownership handoff is a two-stage affair with no atomicity between the stages. `coreuserreg` is a free-running capture register: it is reloaded on EVERY qualifying AHB address phase into the SCE's 64 KB slave region (line 61-62). `sceuser` - the value that `ahben` actually compares against for the rest of the session - is then loaded from whatever `coreuserreg` happens to hold at the single cycle when `sceuserlock` fires (line 64), which is the cycle after `scemode` transitions from 0 to non-zero. The agent that writes `scemode` is therefore NOT necessarily the agent that becomes the owner: the write travels AHB -> `apb_bdg` -> APB -> `sfr_scemode` and takes several clock cycles to land, and AHB is pipelined, so at least one subsequent address phase is presented and captured before `cr_scemode` changes. Two further defects compound this. First, `ahbscpvld` (line 70) is computed from `ahbs`, which is the UNGATED slave side of `ahb_gate` (`ahb_gate ahbsgate(.ahben,.ahbslave(ahbs),.ahbmaster(ahbm));`, line 76, with `ahbs`/`ahbm` bound to `ahbs0_sync`/`ahbs0` at sce.sv:285-286). `ahb_gate` clears only `hsel` and `htrans` on the master side (amba_components.sv:1037-1039) and passes `hready` straight back (amba_components.sv:1049), so a transfer that the access control has just denied still satisfies `ahbscpvld` and still overwrites `coreuserreg` - the register that decides who owns the engine is updated by exactly the accesses the design refused. Second, `coreuserreg`/`coreuserselreg` reset to 8'h00/1'b0 (`theregrn` -> `'0`, template.sv:90-91), so if no CM7-tagged transfer occurs between the SCE reset and the mode change, the owner is latched as the impossible identity 8'h00 and the SCE is bricked for everyone.

**Evidence.**
```systemverilog
rtl/modules/crypto_top/rtl/sce_sec.sv:58-64
    assign sceuserlock = ( scemodereg == 0 ) && ~( scemode == scemodereg ) ;
    `theregrn( scemodereg ) <= scemode;

    `theregrn( {coreuserselreg, coreuserreg} ) <=   ahbscpvld & ( ahbs.hauser == daric_cfg::AMBAID4_CM7P ) ? { 1'b0, coreuser_cm7 } :
                                                    ahbscpvld & ( ahbs.hauser == daric_cfg::AMBAID4_VEXD ) ? { 1'b1, coreuser_vex } : {coreuserselreg, coreuserreg};

    `theregrn( {sceusersel, sceuser} ) <= sceuserlock ? {coreuserselreg, coreuserreg} : {sceusersel, sceuser};

rtl/modules/crypto_top/rtl/sce_sec.sv:70,76
    assign ahbscpvld = ahbs.hsel & ahbs.htrans[1] & ahbs.hreadym & ahbs.hready ;

    ahb_gate #(.AW(32),.DW(32)) ahbsgate(.ahben,.ahbslave(ahbs),.ahbmaster(ahbm));

rtl/modules/amba/rtl/amba_components.sv:1037-1039,1048-1050 (ahb_gate: only hsel/htrans are gated; hready/hrdata/hresp pass through)
        assign ahbmaster.hsel        = ahben & ahbslave.hsel        ;
        assign ahbmaster.haddr       = ahbslave.haddr       ;
        assign ahbmaster.htrans      = ahben ? ahbslave.htrans : '0      ;
...
        assign ahbslave.hrdata       = ahbmaster.hrdata     ;
        assign ahbslave.hready       = ahbmaster.hready     ;
        assign ahbslave.hresp        = ahbmaster.hresp      ;

rtl/modules/common/rtl/template.sv:90-91 (reset value of the capture register is all-zero)
`define theregrn(theregname) \
    `theregfull( clk, resetn, theregname, '0 )
```

**Preconditions.** The attacker must control code that executes on the CM7 with a different coreuser than the agent opening the session, and must be able to place an SCE-region access in the window between the scemode store's address phase and the APB write landing. The exact width of that window depends on `cmsdk_ahb_to_apb`, which is a black box not present in this repository - this is why I rate confidence medium rather than high. The variant of this finding that requires no timing at all is finding 2 (the Vex ID mismatch), where the priming access can be issued at leisure because the Vex's own scemode write never updates the capture register.

**Attack scenario.** Same-CPU privilege downgrade of the SCE owner:
1. Trusted CM7 code (say boot0-classified) prepares to open a secure SCE session. It issues the store of scemode = 2 to 0x4002_8000. That store's AHB address phase captures boot0's coreuser into `coreuserreg`, and then the `apb_bdg`/`cmsdk_ahb_to_apb` bridge holds the AHB in wait states for several cycles while the APB access completes.
2. AHB pipelines the next transfer's address phase against the current data phase. The attacker arranges for the very next SCE-region access to come from a lower-privilege coreuser: either a return/branch into an attacker-controlled region immediately after the store (the CM7's coreuser is PC-derived and lags the PC by only `coreuser_filtercyc + 2` cycles, and `coreuser_filtercyc` resets to 0), or - in a design where the store is posted - simply the next queued access in the attacker's own code. That address phase reloads `coreuserreg` with the attacker's identity.
3. `cr_scemode` finally updates. `scemodereg` is still 0, so `sceuserlock` fires and `sceuser` is loaded with the ATTACKER's coreuser, not boot0's.
4. From that point `ahben` grants the attacker full owner access to the secure session - the SCE control plane, the DMA (and therefore ReRAM key-slot reads with `sce_sec_op` asserted), and every engine as a signing/decryption oracle - while the legitimate owner is silently denied. The denial is silent in both directions: `ahb_gate` does not raise HRESP, the downstream demux returns HREADY=1/HRESP=0/HRDATA=0 for an unselected slave (ahb_demux.sv:119,122,124-131), and the SCE reports no access-control error for gate denials (`fr_acerr` at sce_glbsfra.sv:89 only reports `scedma_ac` rule denials). Legitimate firmware that loses the race therefore believes its key loads succeeded and proceeds to run the engines on stale or zero key material.

**Mitigation.** RTL fix: make the ownership capture atomic with the mode change instead of racing it. The cleanest form is to capture the identity from the transfer that actually writes the mode register - route the requester's hauser/coreuser alongside the APB write into `sce_glbsfr` and have `sfr_scemode` export it, so `sceuser` is loaded from the writer by construction. Failing that, freeze `coreuserreg` as soon as a write to the mode register is accepted on the AHB side and hold it frozen until `sceuserlock` has fired. Independently: qualify `ahbscpvld` with `ahben` so that denied transfers cannot update the ownership register (`assign ahbscpvld = ahben & ahbs.hsel & ...`); make `ahb_gate` return an AHB ERROR response rather than silently completing with zeros, so that both a probing attacker and a losing legitimate owner are visible; and add a status/interrupt bit for gate denials next to the existing `fr_acerr`. Software workaround on fabricated silicon: after writing `scemode`, the owning code must read back `sceuser` (exported to the SoC and to the RRC) or otherwise self-test by performing an owner-only SCE access and verifying the returned data is not zero, and must abort the session if the check fails. It must also ensure that no other SCE-region access - from any master, including the BIO/BDMA and MDMA - can be in flight across the mode change, e.g. by quiescing those masters first.

**Verification.** Verified as written; exploitability not fully established. The code reads exactly as described. sce_sec.sv:58-64, :70 and :76 are verbatim correct; coreuserreg is a free-running capture updated on every qualifying address phase and sceuser is loaded from it in the single cycle sceuserlock is high. ahbscpvld is indeed computed from the ungated slave side (ahbs is bound to ahbs0_sync at sce.sv:285, ahbm to ahbs0 at :286), and I confirmed ahb_gate at amba_components.sv:1028-1050 gates only hsel and htrans while passing hready/hrdata/hresp straight back, so a denied transfer still satisfies ahbscpvld. The reset value is '0 per template.sv:90-91. Where the finding is weaker than stated: (a) the 'denied transfers update the ownership register' sub-claim has no reachable consequence I could construct - sceuserlock can only fire on the 0->non-zero scemode transition, and while scemode==0 ahben is unconditionally 1, so no transfer that updates coreuserreg at the decisive moment was ever denied; after the latch, scemode is write-locked (sce_glbsfra.sv:78) and any further change asserts modequit, which resets sce_sec and clears coreuserreg. (b) The race itself is at most a one-cycle window: ahbscpvld requires ahbs.hready, and apb_bdg holds HREADY low through the APB access, so no new address phase is captured during the wait states; only the address phase presented in the final HREADY-high cycle can displace the writer's identity. (c) Only CM7P transfers update coreuserreg at all (the VEXD arm is unreachable, per finding 2), so the attacker and the victim must both be CM7 contexts with different coreuser values, and the attacker must land an SCE-region address phase in that single cycle. CM7 coreuser is PC-derived with a filter (cm7sys.sv:763-776), so this needs an interrupt or branch landing with cycle accuracy - many cycles of entry latency against a one-cycle window. I could not construct a practical exploit, and the finder's own note that cmsdk_ahb_to_apb is not in the repository is correct - I could not find it either, so the exact window cannot be pinned down from this source.

**Corrections applied by the verifier.** Downgrade from medium to low. The architectural criticism is valid and worth reporting - ownership is latched from a free-running capture register rather than atomically from the transfer that writes scemode, and denied transfers are not excluded from that capture - but the concrete privilege-downgrade attack is not substantiated: the exploitable window is a single cycle, it requires a same-core context switch with cycle accuracy, and the 'denied transfer' sub-claim is unreachable because ahben is always 1 in the only state where sceuserlock can fire. The genuinely load-bearing part of this finding is the reset-value case ('if no CM7-tagged transfer occurs, the owner is latched as 8'h00'), and that is a real DoS - but it is a consequence of finding 2, not an independent race. Also note the silent-failure observation is correct and useful on its own: ahb_gate raises no HRESP (amba_components.sv:1046-1048) and fr_acerr (sce_glbsfra.sv:89) only reports scedma_ac rule denials, so gate denials are invisible to both attacker and victim.

---

<a id="bao-090"></a>

### BAO-090 — sfrlock is declared but never driven in the SCE global register file, leaving the mode, RAM-clear/reset and engine clock-enable registers permanently writable; the intended operational lock is commented out

**Severity: Low** | CWE-1233 Security-Sensitive Hardware Controls with Missing Lock Bit Protection | Threat actor: T1 (software holding SCE ownership, which is unrestricted in mode_non) | Confidence: High

**Location:** `rtl/modules/crypto_top/rtl/sce_glbsfra.sv:65`

**Description.** `sce_glbsfr` declares `logic sfrlock;` and never assigns it. The line that would drive it is present but commented out (line 68), and it is exactly the pattern that the sibling engine register files DO implement - `aes.sv:135` and the analogous line in `combohasha.sv` both contain `` `theregrn( sfrlock ) <= optlock ? 1'b1 : mfsm_done ? '0 : sfrlock; `` to hold their configuration stable for the duration of an operation. Because `sfrlock` is pulled into every SFR instance in the block through `` `apbs_common `` and `.*`, and because `apb_sfr`/`apb_ar` gate writes with `assign apbwr = ~sfrlock & ...` (apb_sfr.sv:333, and apb_ar via `.sfrlock(sfrlock|'0)` at apb_sfr.sv:253), an undriven net here fails OPEN: in simulation it is X and in synthesis it is tied low, so every register in the block is unconditionally writable at all times. The affected registers are `sfr_suben` (0x4002_8004, the per-engine ICG enables at sce.sv:256), `sfr_ahbs` (0x4002_8008, the AHB channel XOR/LTX options), `sfr_arrst`/`sfr_arclr` (0x4002_801C, SCE reset and crypto-RAM wipe), `sfr_ffen`/`sfr_ffclr` (0x4002_8030/34, the segment FIFO enables and clears) and `sfr_tickcyc`. The one register that is protected - `sfr_scemode` - is protected only because its instantiation overrides the port explicitly with `.sfrlock(~devmode & (|cr_scemode))`, which masks the fact that the block-level lock does not exist. Note this is not a privilege-boundary break on its own (all of these registers sit behind the `ahben` ownership gate), but it removes the operational interlock that the rest of the SCE implements, so the owner - or an attacker who has won ownership by findings 2/5 - can stop an engine's clock, clear a segment FIFO, or reset the SCE mid-operation, and can do so at a chosen point in a key-dependent computation.

**Evidence.**
```systemverilog
rtl/modules/crypto_top/rtl/sce_glbsfra.sv:63-70
    logic apbrd, apbwr;
    logic pclk;
    logic sfrlock;
    assign pclk = clk;

//    `theregrn( sfrlock ) <= optlock ? 1'b1 : mfsm_done ? '0 : sfrlock;

    `apbs_common;

rtl/modules/crypto_top/rtl/sce_glbsfra.sv:78-87 (all bound by .* to the undriven net; only scemode overrides it)
    apb_cr #(.A('h00), .DW(2))      sfr_scemode     (.cr(cr_scemode), .prdata32(), .sfrlock(~devmode & (|cr_scemode)), .*);
    apb_cr #(.A('h04), .DW(SUBCNT),.IV('h1f)) sfr_suben       (.cr(cr_suben),   .prdata32(),.*);
    apb_cr #(.A('h08), .DW(5))      sfr_ahbs        (.cr(cr_ahbsopt), .prdata32(),.*);
...
    apb_ar #(.A('h1c), .AR(32'h5a)) sfr_arrst       (.ar(ar_reset), .*);
    apb_ar #(.A('h1c), .AR(32'ha5)) sfr_arclr       (.ar(ar_clrram), .*);

rtl/modules/crypto_top/rtl/aes.sv:132-135 (the same three lines in a sibling module, with the driver present)
    logic sfrlock;
    assign pclk = clk;

    `theregrn( sfrlock ) <= optlock ? 1'b1 : mfsm_done ? '0 : sfrlock;

rtl/modules/amba/rtl/apb_sfr.sv:253 (apb_ar consumes the same net)
            .sfrlock     (sfrlock|'0     ),
```

**Preconditions.** SCE ownership (free in mode_non after any reset; otherwise obtainable via findings 2 or 5). No physical access required. This is an integrity/fault-injection and denial-of-service primitive rather than a direct confidentiality break by itself.

**Attack scenario.** An attacker who holds SCE ownership - which after any reset is anyone at all, since `ahben` is unconditionally 1 in `mode_non` (sce_sec.sv:72), and which can be obtained against a legitimate owner via findings 2 and 5 - writes 0x4002_8004 in the middle of a running operation to clear the `cr_suben` bit for a chosen engine. The `ICG uclksub ( .CK ( clk ), .EN ( cr_suben[gvi] ), ... )` at sce.sv:256 stops that engine's clock while its RAM continues to run on the ungated `clk` (sce.sv:420 `.clkram(clk)`), freezing the datapath at a chosen cycle of a key-dependent computation and giving a controlled fault-injection and single-stepping primitive with no physical access. The same write can be used to gate `clksub[4]`, the SCE DMA clock, stalling a descriptor mid-transfer while the RAM ports stay live. Writing 0xa5 to 0x4002_801C at a chosen cycle aborts an operation and clears the crypto RAM mid-computation, and writing to `sfr_ffclr` at 0x4002_8034 resets a segment FIFO's pointers under a running channel. None of these are possible in the AES or hash register files, which lock themselves for the duration of an operation - the interlock exists in the design and is simply missing here.

**Mitigation.** RTL fix: uncomment and complete the driver at sce_glbsfra.sv:68 so `sfrlock` is asserted while any SCE engine or DMA channel is busy (the `sr_busy` vector is already an input to this module at line 37) and released when the operation completes - matching aes.sv:135. In addition, an undriven net feeding a write-enable is a latent fail-open: the design should never leave a security-relevant control signal unassigned, and the build should treat 'undriven net' as an error rather than a warning for signals named `sfrlock`. Software workaround on fabricated silicon: none that closes the hole, since the registers are genuinely unlocked; firmware can only reduce exposure by ensuring the SCE never sits in `mode_non` with secrets resident (which finding 1 shows is not fully achievable for RNGA/RNGB) and by not granting SCE ownership to any context it does not fully trust for the entire duration of an operation.

**Verification.** Verified as written; exploitability not fully established. The code fact is confirmed exactly: sce_glbsfra.sv:65 `logic sfrlock;` with no assignment anywhere in the module, line 68 the commented-out driver, and every apb_cr/apb_ar in the block picking it up through `.*` (lines 79-99). The consumption path is real: apb_cr passes `.sfrlock(sfrlock | '0)` to apb_sfr2 (apb_sfr.sv:114) whose write enable is apb_sfr.sv:333 `assign apbwr = ~sfrlock & apbslave.psel & apbslave.penable & apbslave.pwrite;`, and apb_ar does the same via apb_sfr.sv:253 into apb_sfrop2 (apb_sfr.sv:378). The sibling contrast is also exactly as quoted - aes.sv:132-135 has the identical three declarations plus `\`theregrn( sfrlock ) <= optlock ? 1'b1 : mfsm_done ? '0 : sfrlock;`. Only sfr_scemode overrides the port. Where the finding overreaches: the affected registers all sit behind the ahben ownership gate, so the missing lock crosses no privilege boundary. The attack narrative ('an attacker who holds SCE ownership stops an engine clock mid-computation') describes a capability the legitimate owner already has by design - ar_reset, ar_clrram and cr_suben are owner-facing controls. The one genuinely attacker-reachable case is mode_non, where ahben is unconditionally 1 and any master can pulse ar_clrram or gate clksub - but that is a consequence of sce_sec.sv:72, not of the missing sfrlock, which was never ownership-qualified in the first place. I also checked the commented line's own premise: sce_glbsfra.sv contains no `optlock` and no `mfsm_done` signal, so line 68 is template residue copied from an engine register file, not a control that was deliberately removed.

**Corrections applied by the verifier.** Keep as a latent fail-open / coding-standard defect, not as an exploitable weakness. The claim that this 'gives a controlled fault-injection and single-stepping primitive with no physical access' should be dropped or heavily qualified: the primitive is available to the SCE owner regardless of sfrlock, and to a non-owner only in mode_non where the ownership gate is open anyway. The correct framing for the vendor is: an undriven net feeding a write-enable is X in simulation and tied low in synthesis, and the build flow should treat an undriven signal named sfrlock as an error. Also correct one detail - the commented-out line references optlock and mfsm_done, neither of which exists in this module, so describing it as 'the intended operational lock' is not supported; it is copy-paste residue.

---

<a id="bao-091"></a>

### BAO-091 — A single non-redundant ReRAM byte compare replaces the entire hard-coded crypto-DMA access-control table with ReRAM-supplied rules

**Severity: Low** | CWE-1233 Security-Sensitive Hardware Controls with Missing Lock Bit Protection | Threat actor: T2 (fault injection on the single 8-bit compare or on the ReRAM boot read) / T1 with boot0-or-boot1 coreuser classification able to rewrite the ReRAM SCE config word | Confidence: Medium

**Location:** `rtl/modules/crypto_top/rtl/scedma_ac.sv:40`

**Description.** `scedma_ac` chooses between the compile-time, immutable access-control table `ACRULEs` (scedma_pkg.sv:290-310) and 18 bytes taken verbatim from the ReRAM SCE config word, based on a single equality test against one byte. When `nvracrules[29] == 8'h5a`, every one of the 18 per-segment, 8-bit access rules is replaced by ReRAM content. Setting those bytes to 0xFF grants every channel read and write access to every segment - including SKEY, SCRT, PKB and AKEY - which turns the crypto RAM into an ordinary readable memory while `mode_sec` is still nominally enforcing. The decision is a single 8-bit comparison in a single flop-free combinational path, with no duplication and no error-detection code over the table, so it is a textbook single-point glitch target; and the whole mechanism sits in the same ReRAM config word (`nvrcfg = nvrcfgdata.cfgsce`) as `devmode_sce` (sce.sv:131), meaning one corrupted word disables both the SCE interlocks and the DMA ACL. There is no anti-rollback and no lock: the table can be re-supplied on every boot.

**Evidence.**
```systemverilog
scedma_ac.sv:27 and 39-40
    input   logic [31:0][0:7]       nvracrules   ,
...
    logic nvrrule_enable;
    assign nvrrule_enable = (nvracrules[29] == 8'h5a);

scedma_ac.sv:65-67
    for (genvar j = 0; j < scedma_pkg::SEGCNT; j++) begin: gacrule
        assign chnlacrules[j] = nvrrule_enable ? nvracrules[j] : ACRULEs[j].accessrule;
    end

sce.sv:372-376 (the ReRAM word is wired straight in)
    scedma_ac dmaac(
        .clk,
        .resetn             (sceresetn),
        .acenable           ( acenable      ),
        .nvracrules         ( nvrcfg ),

sce.sv:131 (the SAME ReRAM word also carries the five SCE interlock bypasses)
assign devmode_sce = devmode ? '1 : nvrcfg[28];// != 8'h00) || devmode;

scedma_pkg.sv:292-295 (the table being overridden is the one protecting the key segments)
        '{ segid:SEGID_LKEY , accessrule: 8'b01_01_01_01 },
        '{ segid:SEGID_KEY  , accessrule: 8'b01_01_01_01 },
        '{ segid:SEGID_SKEY , accessrule: 8'b01_01_01_01 },
        '{ segid:SEGID_SCRT , accessrule: 8'b01_01_01_01 },
```

**Preconditions.** Either (a) code classified as boot0/boot1 by the coreuser PC comparator can write the ReRAM CFG region at 0x603D_C000 (the SCE config word `cfgsce`), or (b) a glitch/laser fault flips the 8-bit compare `nvracrules[29] == 8'h5a` or corrupts the boot-read shadow of the config word. There is no lock bit, no redundancy, no second compare, and no signature over the table.

**Attack scenario.** Path A (software): code that the CM7 coreuser comparator classifies as boot0 or boot1 - which the RRC's `cfg_prev_dis` term (rrc.sv:815) permits to write the ReRAM CFG region - writes byte 29 of the SCE config word to 0x5a and bytes 0..17 to 0xFF. On the next boot, `nvrrule_enable` is 1 and `chnlacrules[j] = 8'hFF` for every segment, so `chnlac[i]` is 1 for every channel and every segment even with `acenable = mode_sec = 1`. A plain AHB read of 0x4002_0200 now returns SKEY, and an AXI DMA can stream LKEY/KEY/SKEY/SCRT/PKB/AKEY to external memory. Nothing in the design detects or locks this, and `acerr` cannot report it (finding 3).
Path B (fault injection): with the device in normal secure operation, a voltage or laser glitch aimed at the 8-bit comparator `nvracrules[29] == 8'h5a` - a single unreplicated combinational term feeding a pure mux - forces `nvrrule_enable` high. `chnlacrules` then takes whatever the ReRAM SCE config bytes 0..17 happen to contain; if any of them has bit 0 or bit 2 set for a key segment, that segment becomes readable over the AHB or AXI channel for as long as the fault holds. Because the mux is combinational the effect is immediate and needs no reset, and because the compare is not sampled into a protected flop there is no reference value to compare against afterwards.

**Mitigation.** RTL fix: this override should not exist in a production part, or should be gated by an irreversible lifecycle signal (CMS user mode / a one-way counter) rather than by a byte value. If it must remain, (a) replicate the enable compare at least twice in separate logic cones and require both to agree, with a mismatch forcing `nvrrule_enable = 0` and raising a tamper event; (b) protect the 18 rule bytes with a CRC/ECC stored in the same word and fall back to the compile-time `ACRULEs` on any mismatch; (c) sample `nvrrule_enable` and `chnlacrules` into flops at boot and add a lock bit so they cannot change after `brdone`; (d) restrict the override so it can only ever REMOVE permissions relative to `ACRULEs` (`chnlacrules[j] = ACRULEs[j].accessrule & (nvrrule_enable ? nvracrules[j] : 8'hFF)`), which makes the whole mechanism fail-safe. Silicon workaround: firmware/provisioning must ensure the ReRAM SCE config word never contains 0x5a in byte 29, and the ReRAM CFG region (0x603D_C000) must be locked via the ACRAM `cfg_wr_dis` bit before any non-boot code runs, so Path A is closed; Path B cannot be mitigated in firmware.

**Verification.** Verified as written; exploitability not fully established. Verbatim correct. scedma_ac.sv:39-40 `assign nvrrule_enable = (nvracrules[29] == 8'h5a);` and scedma_ac.sv:65-67 replace all 18 per-segment rule bytes with ReRAM content when it matches. sce.sv:376 `.nvracrules ( nvrcfg )` and soc_coresub.sv:545 `.nvrcfg ( nvrcfgdata.cfgsce )` confirm the source is the ReRAM SCE config word, and brc.sv:131 `assign nvrcfgdata = syscfgdata;` confirms that in the ASIC build (non-FPGA) it comes from the boot ReRAM read, not a constant. sce.sv:131 confirms the same word also carries devmode_sce. I also checked the bit-ordering hazard (sce.sv:47 declares nvrcfg as [31:0][7:0] while scedma_ac.sv:27 declares nvracrules as [31:0][0:7], so each byte is bit-reversed across the port) - 0x5a is a bit-reversal palindrome, so the compare works either way, and the rule bytes map correctly onto the [0:7] accessrule ordering. What I cannot substantiate is that either exploit path is an escalation. Path A requires writing the ReRAM CFG region, and rrc.sv:815 `cfg_prev_dis` denies that to anything except coreuser_in[4]/[5] (boot0/boot1) - i.e. the secure-boot stages that already own the whole trust chain, so re-provisioning the ACL is not a privilege they lack. Path B is a real single-point-of-failure observation (one unreplicated 8-bit compare feeding a pure combinational mux, no ECC over the 18 rule bytes, no lock after brdone) but is unverifiable fault-injection speculation and would also need the ReRAM bytes 0..17 to happen to contain permissive values.

**Corrections applied by the verifier.** The claim that nothing is sampled into flops is partly wrong: the config word itself IS captured into boot flops (brc.sv:106-111 syscfgdata registers, path present in the non-FPGA branch at line 131); what is unregistered is the comparator and the rule mux. Severity lowered from medium to low: this is an intentional configurability feature whose only software path requires boot0/boot1 authority. The defensible part of the finding is the fail-open direction - the override can only ADD permissions, and a fail-safe form (`ACRULEs[j].accessrule & nvracrules[j]`) costs nothing.

---

<a id="bao-092"></a>

### BAO-092 — SCE AES CTR mode increments only one 32-bit word of the counter block, with no carry propagation and no wrap detection

**Severity: Low** | CWE-323 Reusing a Nonce, Key Pair in Encryption | Threat actor: T1 (software that drives the SCE AES engine in CTR mode over a long-lived key/counter) | Confidence: Medium

**Location:** `rtl/modules/crypto_top/rtl/aes.sv:463`

**Description.** In CTR mode the counter update is performed by adding 1 to exactly one 32-bit word of the 128-bit counter block on its way out to the AKEY writeback - word 0 or word 3, selected by the software bit cr_optltx[5]. The addition is a plain 32-bit add whose carry-out is discarded, and the other three words of the counter block are never touched. The counter block is therefore effectively a 32-bit counter over a fixed 96-bit nonce, and when the selected word rolls over from 0xFFFFFFFF to 0x00000000 the entire counter block repeats exactly, silently. Nothing in the engine detects or reports this: there is no wrap flag, no block-count limit enforced in hardware (opt_aescnt bounds only a single invocation to 65536 blocks, and the counter state persists in the AKEY segment between invocations so a stream can be resumed indefinitely), and err[0:1] carries only ARAM parity. Because CTR mode keystream reuse reveals the XOR of two plaintexts, this is a confidentiality break rather than a mere robustness issue - but it requires 2^32 blocks (64 GiB) under one key, hence low severity in practice.

**Evidence.**
```systemverilog
rtl/modules/crypto_top/rtl/aes.sv:456-465:
    assign { opt_crtopt1, opt_crtopt0 } = cr_optltx[5:4];
    assign aramres_segrdatx = ~opt_crtopt0 ?
                                      aramres.segrdat :
                                    { aramres.segrdat[7:0], aramres.segrdat[15:8], aramres.segrdat[23:16], aramres.segrdat[31:24]};
    assign segrdat_ctr = ~opt_crtopt0 ?
                                      segrdat_ctrx :
                                    { segrdat_ctrx[7:0], segrdat_ctrx[15:8], segrdat_ctrx[23:16], segrdat_ctrx[31:24]};
    assign segrdat_ctrx = aramres_segrdatx + 'h1;
    assign segrdat_ctren = ( opt_mode == MODE_CTR ) && ( mfsm == MFSM_WB_IV )
                        && ( opt_crtopt1 ? ( chnlo_rpreq.segptr == 'h3 ) : ( chnlo_rpreq.segptr == 'h0 ));

rtl/modules/crypto_top/rtl/aes.sv:489  (only the selected word is replaced; the other three pass through unchanged):
    assign chnlo_rpres.segrdat = segrdat_ctren ? segrdat_ctr : aramres.segrdat ;

rtl/modules/crypto_top/rtl/aes.sv:534  (no wrap or overflow indication anywhere in the error surface):
    `theregrn( err[0:1] ) <= ramerror;
```

**Preconditions.** The SCE AES engine is used in CTR mode (opt_mode == MODE_CTR) with a long-lived key and a counter block whose selected 32-bit word is allowed to advance through its full range, either within one very long stream or across many invocations that resume from the counter value written back into the AKEY segment.

**Attack scenario.** 1. Firmware sets up an AES-CTR stream: key in the SCE AKEY segment, a 128-bit counter block at AKEY[cr_segptrstart[PTRID_IV]], opt_mode = MODE_CTR, and encrypts data in repeated invocations, each of which resumes from the counter value that MFSM_WB_IV wrote back into AKEY.
2. Every block advances only the single 32-bit word selected by cr_optltx[5] (aes.sv:465). The remaining 96 bits of the counter block are constant for the life of the stream.
3. After 2^32 blocks the selected word wraps from 0xFFFFFFFF to 0x00000000 with the carry discarded (aes.sv:463 is a bare 32-bit add). The counter block is now bit-for-bit identical to the block used 2^32 blocks earlier, so the keystream repeats.
4. An attacker who has collected ciphertext spanning the wrap XORs the two ciphertext blocks encrypted under the repeated counter and obtains P1 XOR P2, recovering plaintext by standard crib-dragging. No hardware indication of the wrap is produced: err[0:1] carries only ARAM parity and the operation reports a normal MFSM_DONE.
5. The same failure occurs much sooner if firmware, misled by the byte-swap option cr_optltx[4], selects the wrong 32-bit word as the counter field (opt_crtopt1 chooses word 3 vs word 0) and that word is not actually the least-significant field of the intended counter - in which case the effective period can be far shorter than 2^32.

**Mitigation.** RTL fix: propagate the carry across the full 128-bit counter block - increment the block as a single 128-bit value in MFSM_WB_IV rather than patching one 32-bit word - and add a sticky overflow/wrap status bit that is raised when the counter block returns to its initial value, wired into the engine's err[] outputs (err[2:7] are currently undriven) so that a wrap cannot go unnoticed.
Software workaround on fabricated silicon: fully mitigable in firmware. Treat the SCE CTR counter as a 32-bit counter over a 96-bit nonce and enforce the NIST limit in software: never encrypt more than 2^32 blocks (and preferably far fewer) under one (key, nonce) pair, and rekey or re-nonce well before the selected word can wrap. Firmware must also read back the counter word from AKEY between invocations and refuse to continue a stream whose counter has decreased or returned to its starting value, and must set cr_optltx[5] consistently with the endianness in which it constructed the counter block.

**Verification.** Verified as written; exploitability not fully established. The code reads exactly as described. aes.sv:456-465 reproduces verbatim, including `assign segrdat_ctrx = aramres_segrdatx + 'h1;` where aramres_segrdatx is a 32-bit `dat_t`, so the carry-out is discarded, and `segrdat_ctren` is asserted only for `chnlo_rpreq.segptr == 'h3` or `'h0` depending on cr_optltx[5]. aes.sv:489 `assign chnlo_rpres.segrdat = segrdat_ctren ? segrdat_ctr : aramres.segrdat ;` confirms the other three words pass through untouched. aes.sv:534 confirms err carries only ramerror, so there is no wrap indication. I could not find any carry chain or wrap flag elsewhere in the module. However I am downgrading confidence in this being a *defect*: a 32-bit block counter over a 96-bit fixed nonce is exactly the SP800-38D/GCM construction and is a legitimate, widely-used design point, not an implementation error. The real gap is the absence of any hardware wrap/overflow status bit, and the exploit requires 2^32 blocks (64 GiB) under one (key, nonce) pair, which the finder correctly acknowledges. The secondary claim about cr_optltx[5] selecting the 'wrong' word producing a much shorter period is speculative — selecting word 3 vs word 0 is the byte-order option, and there is no evidence of a shorter effective period.

**Corrections applied by the verifier.** Reframe: this is not a carry-propagation bug so much as an undocumented 32-bit-counter/96-bit-nonce design point with no wrap detection. Drop or heavily qualify attack step 5 (the 'misled by cr_optltx[4]' variant) — cr_optltx[4] is the byte-swap option applied symmetrically at aes.sv:457-462 and cr_optltx[5] selects word 3 vs word 0; nothing in the RTL supports a period shorter than 2^32. The actionable request to the vendor is a sticky wrap flag in the unused err[2:7] bits plus documentation of the 2^32-block limit.

---

<a id="bao-093"></a>

### BAO-093 — Writing an undefined cr_func and then starting the AES engine latches its SFR write-protect permanently, silently dropping all further AES register writes until an SCE reset

**Severity: Low**

**Location:** `rtl/modules/crypto_top/rtl/aes.sv:135`

*Surfaced by the independent verifier, not the original domain reviewer.*

**Description.** aes.sv gates every APB write to the AES block on a locally generated `sfrlock` that is set when an operation starts and cleared only when the main FSM reaches MFSM_DONE: `\`theregrn( sfrlock ) <= optlock ? 1'b1 : mfsm_done ? '0 : sfrlock;` (aes.sv:135), with `assign optlock = ( start & ( mfsm == MFSM_IDLE));` (aes.sv:159) and `assign mfsm_done = ( mfsm == MFSM_DONE );` (aes.sv:175). cr_func is an 8-bit register (`bit [7:0] cr_func;` aes.sv:84, `apb_cr #(.A('h00), .DW(8)) sfr_crfunc` aes.sv:144) but the FSM case only decodes the three 2-bit encodings AF_KS=0, AF_ENC=1, AF_DEC=2 (aes.sv:54-56, 184-232). For any cr_func value of 3..255 the default arm executes `mfsmnext = mfsm; mfsmdone = '1;` (aes.sv:227-231), and the FSM register `\`theregfull(clk, resetn, mfsm, MFSM_IDLE ) <= ( start & ( mfsm == MFSM_IDLE)) | mfsmdone ? mfsmnext : mfsm;` (aes.sv:173) therefore reloads MFSM_IDLE forever. MFSM_DONE is never reached, mfsm_done never pulses, and sfrlock stays high until sceresetn. Because apb_cr and apb_ar both gate writes on sfrlock (`assign apbwr = ~sfrlock & apbs.psel & apbs.penable & apbs.pwrite;` apb_sfr.sv:402, and apb_ar routes sfrlock into apb_sfrop2 at apb_sfr.sv:253), software can no longer rewrite cr_func, the segment pointers, the key length, or even pulse sfr_ar to retry. Worse, the failure is silent: APB writes to a locked SFR complete normally with no pslverr, and `assign busy = |mfsm | ramclrbusy;` (aes.sv:167) reads 0, so software sees an idle, apparently healthy engine whose configuration writes are being discarded. Any subsequent security-relevant AES operation attempted by privileged code after an attacker triggers this will simply never run, with no error signalled.

**Evidence.**
```systemverilog
rtl/modules/crypto_top/rtl/aes.sv:135 (lock set on start, cleared only on MFSM_DONE):
    `theregrn( sfrlock ) <= optlock ? 1'b1 : mfsm_done ? '0 : sfrlock;

rtl/modules/crypto_top/rtl/aes.sv:159,175:
    assign optlock = ( start & ( mfsm == MFSM_IDLE));
    assign mfsm_done = ( mfsm == MFSM_DONE );

rtl/modules/crypto_top/rtl/aes.sv:227-231 (undecoded cr_func: FSM pinned in place, done asserted every cycle):
            default :
                begin
                    mfsmnext = mfsm;
                    mfsmdone = '1;
                end

rtl/modules/crypto_top/rtl/aes.sv:84,144 (cr_func is 8 bits, only 0/1/2 decoded):
    bit [7:0]   cr_func;
    apb_cr #(.A('h00), .DW(8))      sfr_crfunc      (.cr(cr_func), .prdata32(),.*);

rtl/modules/amba/rtl/apb_sfr.sv:402 and 253 (both cr and ar writes are gated by sfrlock):
    assign apbwr = ~sfrlock & apbs.psel & apbs.penable & apbs.pwrite;
            .sfrlock     (sfrlock|'0     ),
```

**Attack scenario.** 1. Unprivileged software with access to the SCE APB window writes cr_func = 0x03 (or any value >= 3) to 0x4002_D000.
2. It writes 0x5a to sfr_ar at 0x4002_D004. `optlock` asserts for one cycle because mfsm is MFSM_IDLE, so sfrlock latches high.
3. The FSM's default arm keeps mfsm at MFSM_IDLE with mfsmdone tied high, so MFSM_DONE is never entered and sfrlock is never cleared.
4. From this point every write to the AES SFR block — cr_func, sfr_opt, sfr_optltx, sfr_segptr, sfr_maskseed and sfr_ar itself — is silently discarded with no bus error, and `busy` reads 0 so the engine looks idle and healthy.
5. Privileged code that subsequently tries to perform an AES operation (for example during a secure-boot or key-unwrap step) will configure the engine, write the go register, and wait for a completion interrupt that can never arrive; recovery requires asserting sceresetn. This is availability-only — no secret is disclosed — but it is a one-write, unprivileged, silent denial of the AES engine and should be fixed by clearing sfrlock on the default FSM arm (or by rejecting undecoded cr_func values at optlock time).

**Verification.** No independent verdict recorded for this entry.

---

<a id="bao-094"></a>

### BAO-094 — PKE exposes an exact per-operation cycle counter (sfr_tickcnt) that converts every data-dependent PKE datapath into a noise-free, software-readable timing oracle

**Severity: Low** | CWE-385 Covert Timing Channel | Threat actor: T1 (any software that can read the SCE APB space) | Confidence: High

**Location:** `rtl/modules/crypto_top/rtl/pke.sv:313`

**Description.** pke.sv instantiates a free-running counter that is cleared when the PKE core starts, incremented once every `tickcyc+1` cycles while the core is busy, and LATCHED into a read-only status register the moment the operation completes. `tickcyc` is a software-writable 8-bit CR; setting it to 0 makes `tickhit = (tickcnt0 == 0)` true every cycle, so `tickcntsr` becomes the exact cycle count of the just-finished PkeCore operation.

This is a debug/performance feature, but its effect is to hand an attacker a perfect, jitter-free measurement of exactly the quantity that the two preceding findings leak: the duration of an RSA exponentiation, an ECC scalar multiply, or a modular inversion. Timing attacks that would normally need thousands of noisy external measurements become deterministic single-shot reads. The register is a plain `apb_sr` with no lock, no privilege check, and no gating on `mode_sec` or `devmode`.

**Evidence.**
```systemverilog
pke.sv:313-314
    apb_cr #(.A('h50), .DW(8))   sfr_tickcyc    (.cr(tickcyc),    .prdata32(),.*);
    apb_sr #(.A('h54), .DW(32))  sfr_tickcnt    (.sr(tickcntsr),  .prdata32(),.*);

pke.sv:818-824
        assign tickclr = ~pcore_busy;
        assign ticklock = pcore_done_sync;
        assign tickhit = ( tickcnt0 == tickcyc );
        `theregfull(clkpke, resetn, pcore_busy, '0) <= pcore_start_sync ? 1'b1 : pcore_done_sync ? 1'b0 : pcore_busy;
        `theregfull(clkpke, resetn, tickcnt0, '0 ) <= tickclr | tickhit ? '0 : tickcnt0 + 1;
        `theregfull(clkpke, resetn, tickcnt, '0 ) <= tickclr ? '0 : tickcnt + tickhit ;
        `theregfull(clkpke, resetn, tickcntsr, '0 ) <= ticklock ? tickcnt : tickcntsr;

rtl/modules/crypto_top/rtl/sce_sec.sv:72 (no access control in the reset mode)
    assign ahben =  mode_non ? 1'b1 :
```

**Preconditions.** Read access to the PKE control APB at 0x4002_C000. Per sce_sec.sv:72, `ahben` is unconditionally 1 while `scemode == 0` (the reset state), so in that state ANY AHB master reaching 0x4002_xxxx can read this register with no coreuser or privilege check. Writing `sfr_tickcyc` (0x4002_C050) to 0 makes the counter increment every clock, giving 1-cycle resolution.

**Attack scenario.** 1. Attacker software writes 0 to `sfr_tickcyc` (0x4002_C050) so the counter runs at full clock resolution. The write is not blocked: `sfrlock` in pke.sv is only asserted while an operation is in flight (`optlock = ( start & ( mfsm == MFSM_IDLE))`, pke.sv:287,319).
2. Victim firmware runs an RSA-CRT exponentiation or an ECDSA nonce inversion on the PKE.
3. Attacker polls `sfr_fr` (0x4002_C00C) for `mfsm_done`, then reads `sfr_tickcnt` (0x4002_C054) and obtains the exact cycle count of the victim's private-key operation.
4. Feeding those exact counts into the extra-reduction analysis (finding 1) or the binary-EEA iteration analysis (finding 2) recovers the RSA factor / ECDSA nonce with orders of magnitude fewer queries than a noisy channel would require, and without any physical access.

**Mitigation.** RTL fix: gate the tick counter's visibility on `devmode_sce` (or on `~mode_sec`) so that no cycle count is latched or readable for operations performed in secure mode — e.g. force `tickcntsr <= '0` when `mode_sec` is asserted, mirroring how `pkeahbslock` already gates the PKE RAM window (pke.sv:1408-1410). At minimum, make `sfr_tickcyc` write-once and enforce a large minimum divisor so the counter cannot resolve individual extra reductions.

Firmware workaround on fabricated silicon: enter `scemode != 0` before any private-key operation so the SCE AHB owner gate (sce_sec.sv:72-77) restricts the APB to the owning core, and ensure the owning core's own code never leaves the tick registers readable to lower-privilege code. Note this only restricts which core may read, not which privilege level — so additionally, private-key operations should be performed only from code that is not concurrent with untrusted software on the same core.

**Verification.** Independently confirmed by a second reviewer. pke.sv:313-314 are exactly the two quoted apb_cr/apb_sr declarations, and pke.sv:818-824 are the tick logic verbatim (I counted line-by-line from 780). The mechanism works as described: tickclr=~pcore_busy clears at start, tickcnt advances on tickhit, and tickcntsr latches on pcore_done_sync. sce_sec.sv:72 is verbatim `assign ahben =  mode_non ? 1'b1 :` and there is no privilege/coreuser check in that branch. No lock covers it beyond sfrlock, which is only asserted while an operation is in flight (pke.sv:287, 319).

**Corrections applied by the verifier.** The severity is overstated and one detail should be tightened. (a) tickcyc is an apb_cr with IV=32'h0 (apb_sfr.sv:81), so it already resets to 0 and `tickhit = (tickcnt0 == tickcyc)` is true every cycle without any attacker write — the write step in the attack scenario is unnecessary, which strengthens the mechanism but removes the 'attacker must configure it' framing. (b) This is an amplifier, not an independent vulnerability. `sfr_srmfsm` (0x4002_C008) and `sfr_fr` (0x4002_C00C) are equally unlocked and unprivileged in mode_non, and any attacker with software execution already has a CPU cycle counter, so the incremental benefit is removing jitter from the clk-to-clkpke domain crossing rather than creating a new channel. It should be reported as a hardening item attached to findings 1/2/5, not as a standalone high.

---

<a id="bao-095"></a>

### BAO-095 — The Montgomery intermediate dual-port RAM inside PkeCore is excluded from every RAM-clear mechanism and retains secret intermediates across SCE mode changes and resets

**Severity: Low**

**Location:** `rtl/modules/crypto_pke/rtl/PkeCore.sv:403`

*Surfaced by the independent verifier, not the original domain reviewer.*

**Description.** The SCE has two zeroization paths for PKE storage: the global `sceramclr` pulse (sce_sec.sv:85, asserted after any modequit-triggered SCE reset and on the ar_clrram command) and the per-block software command `sfr_ar2` at offset 0x04 (pke.sv:300). Both converge on `ramclr0` (pke.sv:1509), which is routed only to the two `cryptoram` PRAM instances (pke.sv:1517 and 1536). The third PKE memory — the 212 x 64-bit `mimm_dpram` instantiated inside PkeCore at PkeCore.sv:403 — has no clear port at all: the module's port list (mimm_dpram.sv:22-33) contains only cmsatpg, cmsbist, rbs, clk, waddr, wr, wdata, raddr, rd, rdata, parityerr. This RAM holds the Montgomery working state — the UI accumulator, the UU partial product and, in the BA_RAM2_DQ region, the per-round quotient digits q = u0 * n0' (mimm.sv:30-32, 198-208), all of which are functions of the secret operand. So a PKE operation aborted by a mode downgrade leaves those intermediates resident: sceresetn drops, the PRAMs are wiped when initregs recounts to 4'h7, and the mimm dpram keeps its contents into the new (possibly non-secure) mode. This is a zeroization gap rather than a demonstrated read primitive — I traced the only external port on this RAM, the `rbs` redundancy/BIST interface (PkeCore.sv:404 -> pke.sv rbsmimm -> soc_coresub.sv:540 -> soc_top.sv:276 rbif_sce_mimmdpram), and in this tapeout that rbif is declared at the top level without a driving master, so I could not substantiate a read path. Reported as defence-in-depth: a memory holding secret-derived state should not be the one memory the chip's zeroize command cannot reach.

**Evidence.**
```systemverilog
rtl/modules/crypto_pke/rtl/PkeCore.sv:403-413 (no clear input)
    mimm_dpram  #(.DW(64),.AW(8),.DCNT(212))ram2 (
        .cmsatpg, .cmsbist,.rbs,
        .clk        ( Clk ),
        .waddr      ( ram2waddr[7:0]),
        .wr         ( ram2wr ),
        .wdata      ( ram2wdat ),
        .raddr      ( ram2raddr[7:0]),
        .rd         ( ram2rd ),
        .rdata      ( ram2rdat ),
        .parityerr  ( parityerr )
    );

rtl/modules/crypto_pke/rtl/mimm_dpram.sv:22-33 (module has no clear port)
)(
	input  bit cmsatpg, cmsbist,
	rbif.slavedp rbs,
	input  bit clk,
	input  bit [AW-1:0] waddr,
	input  bit wr,
	input  bit [DW-1:0] wdata,
	input  bit [AW-1:0] raddr,
	input  bit rd,
	output bit [DW-1:0] rdata,
	output bit parityerr
);

rtl/modules/crypto_top/rtl/pke.sv:1508-1509, 1517, 1536 (clear reaches only the two PRAMs)
    logic ramclr0;
    assign ramclr0 = ramclr | ramclrar;
        ...
        .ramclr(ramclr0),   // cryptoram m0
        ...
        .ramclr(ramclr0),   // cryptoram m1

rtl/modules/crypto_pke/rtl/mimm.sv:30-32 (what lives in that RAM)
    parameter adr_t BA_RAM2_UI  = 12'h000,
    parameter adr_t BA_RAM2_UU  = BA_RAM2_UI + MAX/DW+PL+2,
    parameter adr_t BA_RAM2_DQ  = BA_RAM2_UU + MAX/DW+PL+2
```

**Attack scenario.** Firmware runs an RSA-CRT exponentiation in scemode=2/3. Mid-operation the attacker (or a glitch, T4) writes scemode back to 0. sce_sec.sv:82 asserts modequit, sceresetnin drops, and on release initregs recounts to 4'h7 and pulses sceramclr (sce_sec.sv:85), wiping both PRAMs. The mimm dual-port RAM is not in that path, so the Montgomery accumulator and the DQ quotient-digit region survive the mode downgrade into mode_non — a mode in which sce_sec.sv:72 grants any AHB master unrestricted access to the SCE. An attacker who can reach that RAM (via DFT/scan or the rbif redundancy port if it is bonded out in a later respin, or via any future firmware path that reads it) recovers secret-derived state that the chip's own zeroize command was believed to have destroyed. The fix is to add a clear input to mimm_dpram and drive it from ramclr0 alongside the two cryptoram instances.

**Verification.** No independent verdict recorded for this entry.

---

<a id="bao-096"></a>

### BAO-096 — A single write of an unrecognised cr_func permanently latches the COMBOHASH sfrlock, wedging the hash engine until an SCE reset

**Severity: Low** | CWE-1245 Improper Finite State Machines in Hardware Logic (unhandled encoding leaves a lock permanently asserted) | Threat actor: T1 (any software able to write two words in the SCE APB window) | Confidence: High

**Location:** `rtl/modules/crypto_top/rtl/combohasha.sv:203`

**Description.** sfrlock is set by optlock (a start write while mfsm==MFSM_IDLE) and is only ever cleared by mfsm_done, i.e. mfsm reaching MFSM_DONE (combohasha.sv:203, 225, 245). The main FSM's cr_func case statement (combohasha.sv:256-449) has a default branch that keeps the FSM in MFSM_IDLE and never asserts mfsmdone (combohasha.sv:443-448), so for any cr_func outside the enumerated hashfunc_e values the FSM cannot advance and mfsm_done can never become true. sfrlock therefore latches high forever. Because sfrlock gates apbwr for the whole block (apb_sfr.sv:333 'assign apbwr = ~sfrlock & apbslave.psel & apbslave.penable & apbslave.pwrite;'), software cannot even rewrite sfr_crfunc to a legal value to recover - the only exit is asserting sceresetn via the separate sce_glbsfr action register at 0x4002_801C. Note also that busy (combohasha.sv:237 'assign busy = |mfsm | ramclrbusy;') reads 0 in this state, so the wedge is invisible to a caller polling busy or SFR_FR.

**Evidence.**
```systemverilog
combohasha.sv:203
    `theregrn( sfrlock ) <= optlock ? 1'b1 : mfsm_done ? '0 : sfrlock;

combohasha.sv:225
    assign optlock = ( start & ( mfsm == MFSM_IDLE));

combohasha.sv:242 and 245
    `theregfull(clk, resetn, mfsm, MFSM_IDLE ) <= ( start & ( mfsm == MFSM_IDLE)) | mfsmdone ? mfsmnext : mfsm;
...
    assign mfsm_done = ( mfsm == MFSM_DONE );

combohasha.sv:443-449 (unrecognised cr_func: FSM parks in IDLE, mfsmdone never asserts)
            default : /* default */
                begin
                    mfsmnext = MFSM_IDLE;
                    mfsmdone = '0;
                    hashcntnext = hashcnt;
                end
        endcase

combohasha.sv:237 (busy does not report the wedge)
    assign busy = |mfsm | ramclrbusy;

hash_pkg.sv:112-127 (only these encodings are handled; every other value hits default)
    typedef enum hashfunc_t {
        HF_SHA256          = 'h00,
        HF_SHA512          = 'h01,
        HF_RIPMD           = 'h02,
        HF_BLK2s           = 'h03,
        HF_BLK2b           = 'h04,
        HF_BLK3            = 'h05,
        HF_SHA3            = 'h06,
        HF_HMAC256_KEYHASH = 'h40,
        HF_HMAC256_PASS1   = 'h50,
        HF_HMAC256_PASS2   = 'h60,
        HF_HMAC512_KEYHASH = 'h41,
        HF_HMAC512_PASS1   = 'h51,
        HF_HMAC512_PASS2   = 'h61,
        HF_INIT            = 'hff
    } hashfunc_e;
```

**Preconditions.** Two APB writes, to 0x4002_B000 and 0x4002_B004. No physical access, no privilege beyond reaching the SCE APB window (unrestricted while scemode==0 per sce_sec.sv:72).

**Attack scenario.** Attacker = unprivileged software (T1) with access to the COMBOHASH APB page, i.e. any AHB master while scemode==0, or the SCE owner in mode_sec.
1. Write COMBOHASH_SFR_CRFUNC (0x4002_B000) = 0x07, or any of the ~230 unassigned encodings (0x08-0x3F, 0x42-0x4F, 0x52-0x5F, 0x62-0xFE).
2. Write 0x5a to COMBOHASH_SFR_AR (0x4002_B004). optlock pulses, sfrlock latches to 1, and mfsm stays in MFSM_IDLE.
3. Every subsequent write to any COMBOHASH register is discarded by apb_sfr's 'apbwr = ~sfrlock & ...', including writes to SFR_CRFUNC and SFR_AR. SFR_SRMFSM still reads MFSM_IDLE and busy reads 0, so a victim driver sees a healthy, idle engine that silently ignores every command.
4. All hash-dependent services stall: secure-boot measurement, the HMAC path that drives truststate, and any software using the sha2-bao1x driver, which spins forever in 'while csr.rf(utra::combohash::SFR_FR_MFSM_DONE) == 0' (deps/sha2-bao1x/src/sha256.rs:78).
5. Recovery requires writing 0x5a to sce_glbsfr's sfr_arrst at 0x4002_801C, which asserts sceresetn for the whole SCE and triggers the crypto-RAM wipe, destroying any in-flight secure-session state.

**Mitigation.** RTL: make the default branch of the cr_func case set 'mfsmnext = MFSM_DONE; mfsmdone = '1;' so an illegal opcode completes with an error instead of parking, and/or gate optlock on cr_func being a recognised encoding. Add an unlock path (e.g. clear sfrlock when mfsm==MFSM_IDLE for N cycles with no start) and report the illegal opcode on the err bus (combohasha.sv:894 currently reports only RAM errors).
Already-fabricated silicon: firmware must validate cr_func against the hashfunc_e whitelist {0x00-0x06, 0x40, 0x41, 0x50, 0x51, 0x60, 0x61, 0xff} before writing SFR_CRFUNC, and must not expose the COMBOHASH page to code that has not been so validated. Hash drivers should add a timeout around the SFR_FR_MFSM_DONE poll and, on timeout, recover by issuing sfr_arrst (0x5a to 0x4002_801C), accepting the SCERAM wipe.

**Verification.** Independently confirmed by a second reviewer. Reproduced from the code. combohasha.sv:203 `theregrn( sfrlock ) <= optlock ? 1'b1 : mfsm_done ? '0 : sfrlock;`, combohasha.sv:225 `assign optlock = ( start & ( mfsm == MFSM_IDLE));`, combohasha.sv:242 and 245 are all verbatim. The default branch at combohasha.sv:443-448 sets `mfsmnext = MFSM_IDLE; mfsmdone = '0;`, so with an unenumerated cr_func the state register at line 242 reloads MFSM_IDLE and `mfsm_done = (mfsm == MFSM_DONE)` can never assert. sfrlock therefore latches high with no clear path except reset.

The lock really does block recovery: all COMBOHASH SFRs are instantiated with `.*`, which binds the module-local `sfrlock` (combohasha.sv:200) into apb_cr/apb_ar/apb_fr, and apb_sfr.sv:333 `assign apbwr = ~sfrlock & apbslave.psel & apbslave.penable & apbslave.pwrite;` (also :378 for the single-register variant). Critically apb_ar routes through the same gate (apb_sfr.sv:248-259: `sfrapbwr` comes from the sfrlock-gated apbwr, and `ar <= sfrapbwr & (pwdata == AR)`), so even SFR_AR is dead. combohasha.sv:237 `assign busy = |mfsm | ramclrbusy;` reads 0 with mfsm==MFSM_IDLE==8'h00, so the wedge is invisible, and SFR_SRMFSM reads IDLE. hash_pkg.sv:112-127 confirms ~240 unassigned encodings hit the default. Recovery is only via sceresetn: combohash's resetn is sceresetn (sce.sv:447) and sce_glbsfra.sv:86 `apb_ar #(.A('h1c), .AR(32'h5a)) sfr_arrst (.ar(ar_reset), .*)` drives it through sce_sec `sceresetnin = ~( modequit | ar_reset )`.

The stickiness is even acknowledged in the vendor's own driver: deps/sha2-bao1x/src/sha256.rs:76 writes SFR_CRFUNC=0 immediately after SFR_AR with the comment "test to see if this flag is 'sticky' - yes it is, sfrlock works" — and deps/sha2-bao1x/src/sha256.rs:78 does spin unbounded on SFR_FR_MFSM_DONE, so the DoS does hang the shipped driver.

**Corrections applied by the verifier.** No factual corrections; every quote and line number checks out. Severity low is right: it is a denial of service only, it is recoverable by sfr_arrst, and it is reachable only by code that already has access to the COMBOHASH APB page (unrestricted only while scemode==0 per sce_sec.sv:72, otherwise limited to the SCE owner). I would recommend the vendor merge this into the finding-1 write-up as part of the same "COMBOHASH SFR page must be treated as privileged" recommendation rather than shipping it standalone.

---

<a id="bao-097"></a>

### BAO-097 — vdresetn is driven by a flop with no reset and the entire voltage-tamper response path is synchronous to clksys, so there is no asynchronous escape if the clock is stopped

**Severity: Low** | CWE-1271 Uninitialized Value on Reset for Registers Holding Security Settings | Threat actor: T4 (clock manipulation) combined with T2 (voltage glitching) | Confidence: Medium

**Location:** `rtl/modules/sec/rtl/sensorc.sv:94`

**Description.** The module output `vdresetn` - which is the chip's only hardware tamper-reset request (soc_top.sv:712 -> sysctrl.sv:794 sysresetgen) - is driven by a bare always block with no reset term:

    always@(posedge clksys) vdresetn <= vdresetnreg;

Compare with every other sequential element in the same module, all of which use `` `theregfull(clksys, resetn, ...) `` with an explicit initial value (sensorc.sv:84,85,90,93,99,100,104,110,111). This one output flop was written by hand and omits the reset. Two consequences:

1. It powers up indeterminate. It drives `secresetn`, which is an input to `sysresetgen.resetnin` in sysctrl.sv:794. A security-relevant reset-request signal that comes out of power-up in an unknown state is exactly the class the CWE describes; whether it settles benignly depends on which clksys edges arrive relative to socresetn release, which is not analysable from this RTL.

2. More importantly for an attacker, it makes the whole voltage-tamper response strictly synchronous and clock-dependent. `vds` (sensorc.sv:90), `vdcnt`/`vdreg` (sensorc.sv:99-100), `vdresetnreg` (sensorc.sv:93) and this final flop are all on `clksys`. There is no asynchronous or self-timed path from the analog detector pins (VD09L/H, VD25L/H, VD33L/H) to any reset or key-clear. If clksys stops or is slowed, `vdresetn` freezes at its last value and the reset request is never issued. clksys is itself software-selected between two sources in cgucore.sv:75-99 via `clksyssel`.

The same module also implements a debounce that suppresses short events entirely: `` `theregfull(clksys, resetn, vdcnt[i], '0 ) <= vds[i] ? '0 : ( vdcnt[i] == cr_vdcfg[i] ) ? vdcnt[i] : vdcnt[i] + 1; `` (sensorc.sv:100). The counter is reset to 0 on *any* cycle where the detector reads OK, so it never accumulates across a train of short glitches; with a firmware-chosen `cr_vdcfg[i]` of up to 15 (sensorc.sv:76, unlocked CR at 0x4005_3020), any glitch shorter than cr_vdcfg+1 clksys periods is invisible and repeated glitches never sum.

**Evidence.**
```systemverilog
sensorc.sv:88-94
    logic vdresetnreg;

	`theregfull(clksys, resetn, vds, '1 ) <= vd;
	assign sr_vdsr = vdflag & ~cr_vdmask0;
//	assign vdresetn = & ( cr_vdmask1 ? '1 : ~vdflag );
    `theregfull(clksys, resetn, vdresetnreg, '1 ) <= & ( cr_vdmask1 ? '1 : ~vdflag );
    always@(posedge clksys) vdresetn <= vdresetnreg;

sensorc.sv:96-102 (the debounce that resets on every clean cycle)
	generate
		for (genvar i = 0; i < VDC; i++) begin: gvd
			assign vdflag[i] = ( cr_vdcfg[i] == 0 ) ? ~vd[i] : vdreg[i];
			`theregfull(clksys, resetn, vdreg[i], '0 ) <= ( vdcnt[i] == cr_vdcfg[i] );
			`theregfull(clksys, resetn, vdcnt[i], '0 ) <= vds[i] ? '0 : ( vdcnt[i] == cr_vdcfg[i] ) ? vdcnt[i] : vdcnt[i] + 1;
		end
	endgenerate

sensorc.sv:39 (module output, only driver is the unreset flop above)
    output logic vdresetn,

rtl/modules/common/rtl/template.sv:82-85 (the macro every other flop in this module uses)
`define theregfull( theclk, theresetn, theregname, theinitvalue ) \
    always@( posedge theclk or negedge theresetn ) \
    if( ~theresetn) \
        theregname <= theinitvalue; \
```

**Preconditions.** For the clock-stop bypass: ability to stop or slow clksys (T4 - external clock/oscillator manipulation, or one write to the CGU select). For the debounce bypass: firmware has programmed a nonzero cr_vdcfg, plus T2 glitch capability. Both additionally require that cr_vdmask1 has been cleared - otherwise the separate cr_vdmask1 finding already defeats the reset outright.

**Attack scenario.** Clock-stop bypass (T4, and the primary practical impact). The attacker's goal is a voltage glitch that faults a secure-boot signature check or an SCE key comparison without triggering the tamper reset. Assume for the sake of argument that firmware has correctly cleared cr_vdmask1 (0x4005_3004) so the reset is armed. The attacker halts or severely slows clksys - by attacking the external crystal/oscillator, by driving the clock pad, or by getting one write to the sysctrl CGU source-select - immediately before applying the glitch. `vdresetnreg` (sensorc.sv:93) and the output flop (sensorc.sv:94) are both clocked on clksys, so neither samples the tamper condition; `vdresetn` remains stuck at 1 for the entire duration of the glitch. `sysresetgen` (sysctrl.sv:794) never sees a deassertion, so the SoC is not reset, the SCE is not reset, and the crypto-RAM wipe that SCE reset release would have triggered (sce_sec.sv:85-87) never runs. When the attacker restores the clock, the glitch is over, `vdflag` has returned to clean, and `vdresetnreg` samples 1. The tamper is never recorded. There is no asynchronous path from the detector pin to any reset in this design to catch it.

Debounce bypass (T2, no clock manipulation). If firmware programs a nonzero debounce in cr_vdcfg (0x4005_3020) - the obvious choice to suppress false positives on a noisy rail - the attacker applies a train of glitches each shorter than (cr_vdcfg+1) clksys periods. sensorc.sv:100 resets vdcnt[i] to 0 on every cycle in which vds[i] reads clean, so the counter never accumulates across the train and `vdreg[i]` never sets. The glitches reach the logic; the detector never reports.

Power-up indeterminacy (T4): `vdresetn` has no reset, so its value between power-up and the first clksys edge after socresetn release is not defined by this RTL, while it is already feeding sysresetgen.

**Mitigation.** RTL fix: (1) give the output flop a reset - use `` `theregfull(clksys, resetn, vdresetn, '1) `` like every other flop in the module, or drop the extra pipeline stage and drive vdresetn from vdresetnreg directly; (2) add an asynchronous or always-on-domain path from the voltage-detector pins to the reset/zeroize logic (e.g. clocked from clk32k in the AO domain, or a purely combinational asynchronous reset assert with synchronous release) so that stopping the main clock cannot suppress the response; (3) change the debounce so vdcnt saturates or leaks rather than being cleared on every clean cycle, so a glitch train accumulates; (4) add a clock-liveness/frequency monitor on clksys that itself raises tamper (the freqmeter at sysctrl.sv:645 exists but its output is only a status register).
Silicon workaround (partial): firmware should leave cr_vdcfg at 0 (0x4005_3020) so the detector path is undebounced and reacts on the first clksys edge, accepting more false positives; and should cross-check the CGU frequency meter (sysctrl.sv:645-652, results at 0x4004_0040) each time it handles a secret, treating an unexpected clksys frequency as a tamper event. Neither addresses the unreset flop nor the fundamental clock dependency on already-fabricated silicon.

**Verification.** Verified as written; exploitability not fully established. The code reads exactly as quoted. sensorc.sv:94 is `always@(posedge clksys) vdresetn <= vdresetnreg;` with no reset term, and it is the sole driver of the module output declared at sensorc.sv:39, while every other sequential element in the file (lines 84, 85, 90, 93, 99, 100, 104, 110, 111) uses `` `theregfull `` with an explicit init value per template.sv:82-85. The debounce claim is also literally correct: sensorc.sv:100 `<= vds[i] ? '0 : ( vdcnt[i] == cr_vdcfg[i] ) ? vdcnt[i] : vdcnt[i] + 1;` clears the counter on any cycle the rail reads healthy, so a train of sub-threshold glitches never accumulates.

But the security impact is much weaker than stated, so I am dropping medium to low.
(1) The unreset flop is fail-safe in both directions. Its data input vdresetnreg resets to '1 (line 93), so one clksys edge after reset release the output is 1; if it powers up 0 the only effect is that sysresetgen holds the SoC in reset (sysctrl.sv:908 `resetninx = &resetnin & resetn`) — a spurious reset, not a suppressed one. There is no state in which the missing reset makes the part *less* likely to react to tamper than the intended value.
(2) The clock-stop argument is a true observation but is generic to the whole design rather than a defect of this flop, and I verified the downstream side is in fact asynchronous: resetgen uses resetninx as the async reset of resetext (sysctrl.sv:910-911), so once vdresetn falls the reset asserts without needing an edge. The clock dependency is confined to sensorc's sampling.
(3) The debounce behaviour is the textbook definition of a debounce filter, not a defect; and the precondition the finder states is decisive — this whole scenario only matters if cr_vdmask1 has been cleared, otherwise the separate mask finding already defeats the reset.

---

<a id="bao-098"></a>

### BAO-098 — Light-detector debounce comparison is done in 32-bit arithmetic, so writing cr_ldcfg=0xF makes the trip condition unreachable and permanently blinds both light/decap detectors

**Severity: Low**

**Location:** `rtl/modules/sec/rtl/sensorc.sv:110`

*Surfaced by the independent verifier, not the original domain reviewer.*

**Description.** The light-detector debounce compares a 4-bit counter against `cr_ldcfg+1`. cr_ldcfg is declared `logic [3:0]` (sensorc.sv:45, apb_cr DW(4) at sensorc.sv:74) and ldcnt[i] is 4 bits (sensorc.sv:51). Because the literal `1` is a 32-bit integer, `cr_ldcfg+1` is evaluated in 32 bits and does NOT wrap: with cr_ldcfg = 4'hF the right-hand side is 32'd16 while ldcnt[i], zero-extended, can only reach 15. The equality at sensorc.sv:110 is therefore never true, ldreg[i] never sets, ldflag/sr_ldsr stay 0 and the light detectors can never report. sensorc.sv:111 makes it permanent rather than transient: the counter's saturation term uses the same unreachable comparison, so ldcnt free-runs and wraps 15->0 forever. The sibling voltage path has no such bug - sensorc.sv:99-100 compares `vdcnt[i] == cr_vdcfg[i]` with no +1 and both operands 4 bits - which shows the +1 is an unreviewed copy-paste divergence. sfr_ldcfg is a plain apb_cr at 0x4005_3018 with sfrlock hardwired to 0 (sensorc.sv:57), on an APB path with no privilege check, so any bus master can set the maximum debounce; a well-intentioned firmware author picking the maximum debounce value to suppress false positives would silently disable the detector with no indication.

**Evidence.**
```systemverilog
rtl/modules/sec/rtl/sensorc.sv:45,51
	logic [3:0] cr_ldcfg;
    logic [LDC-1:0][3:0] ldcnt;

rtl/modules/sec/rtl/sensorc.sv:74
    apb_cr #(.A('h18), .DW(4)   )  		sfr_ldcfg     (.cr(cr_ldcfg),   .prdata32(),.*);

rtl/modules/sec/rtl/sensorc.sv:108-113
	generate
		for (genvar i = 0; i < LDC; i++) begin: gld
			`theregfull(clksys, resetn, ldreg[i], '0 ) <= ( ldcnt[i] == cr_ldcfg+1 );
			`theregfull(clksys, resetn, ldcnt[i], '0 ) <= ~lds[i] ? '0 : ( ldcnt[i] == cr_ldcfg+1 ) ? ldcnt[i] : ldcnt[i] + 1;
		end
	endgenerate

(compare, no +1 and both operands 4 bits) rtl/modules/sec/rtl/sensorc.sv:99-100
			`theregfull(clksys, resetn, vdreg[i], '0 ) <= ( vdcnt[i] == cr_vdcfg[i] );
			`theregfull(clksys, resetn, vdcnt[i], '0 ) <= vds[i] ? '0 : ( vdcnt[i] == cr_vdcfg[i] ) ? vdcnt[i] : vdcnt[i] + 1;
```

**Attack scenario.** Unprivileged software (T1) writes 0x0000_000F to 0x4005_3018. From that instant both ip_lightdet instances (soc_top.sv:717-724) are inert: no value of ldcnt can equal 32'd16, so ldreg never sets, sr_ldsr (sensorc.sv:105) stays 0 and the sensorc irq (sensorc.sv:115) never fires on light. The attacker then decapsulates the package and uses optical probing or laser fault injection - the exact event the light detectors exist to catch - with no interrupt and no status bit. Unlike setting cr_ldmask, this leaves no masked-but-set indication anywhere: the status register itself reads clean, so firmware polling 0x4005_3014 sees nothing. The same defect also fires without an attacker: firmware that programs the maximum debounce for noise immunity silently disables the detector.

**Verification.** No independent verdict recorded for this entry.

---

<a id="bao-099"></a>

### BAO-099 — AO backup registers — the documented cross-power-down secret store — have sfrlock hard-tied to zero, no privilege check, and no tamper-triggered erase

**Severity: Low** | CWE-1233 Security-Sensitive Hardware Controls with Missing Lock Bit Protection / CWE-1272 Sensitive Information Uncleared Before Debug/Power State Transition | Threat actor: T1 (unprivileged software or a BIO/BDMA program); T2 for the no-tamper-erase aspect | Confidence: Medium

**Location:** `rtl/modules/ao/rtl/aobureg.sv:30`

**Description.** aobureg is 8 x 32 bits (256 bits) of always-on, battery-backed storage at 0x4006_5000-0x4006_501F. The vendor documentation explicitly designates it as the place to keep secrets across power-down: docs/src/pmu.md:184 says 'Store any important data to AO backup registers or AORAM before entry' and docs/src/system-control.md:16 says 'BUREG — Backup registers in AO domain. Contents are retained during SoC power-down.' The module implements no access control whatsoever: `sfrlock` is hard-tied to zero, the register file is a plain read/write `apb_cr`, and the AO APB path it hangs off (soc_top.sv:830-838 -> ao_top.sv:127) carries no coreuser tag, no hauser check and no pprot consumer. This is a notable asymmetry with the rest of the SoC, which does implement a coreuser/ACRAM ownership scheme for the ReRAM key slots and an owner-lock for the SCE. In addition, nothing clears these registers on a tamper event: grepping the tamper/mesh/sensor subsystem shows no path from any tamper detector into the AO domain, so a detected intrusion leaves the retained secret in place.

**Evidence.**
```systemverilog
rtl/modules/ao/rtl/aobureg.sv:26-35 (entire access-control surface of the module)
	bit [REGCNT-1:0][31:0] cr_buregs;
    logic apbrd, apbwr;
    logic sfrlock;

    assign sfrlock = '0;

    `apbs_common;
    assign apbx.prdata = sfr_bureg.prdata32;

    apb_cr #(.A('h0), .DW(32), .SFRCNT(REGCNT))   sfr_bureg      (.cr( cr_buregs           ), .prdata32(),.*);

rtl/modules/ao/rtl/ao_top.sv:234-238 (instantiated on the open AO APB, reset only by porresetn)
    aobureg aobureg(
        .pclk(pclk),
        .resetn(porresetn),
        .apbs(apbaos[5]),.apbx(apbaos[5])
        );

rtl/asic_top/rtl/soc_top.sv:830-838 (the bridge that reaches it applies no identity filter)
    ahbasync uahbaolf(.clks(hclk), .clkm(clkao), .resetn(coreresetn), .ahbs (coreahb_ao), .ahbm(coreahb_aolf));
        apb_bdg uapbaobdg(
    /*        input        */   .hclk     ( clkao           ),
    /*        input        */   .resetn   ( coreresetn      ),
    /*        input        */   .pclken   ( 1'b1 ),
    /*        ahbif.slave  */   .ahbslave ( coreahb_aolf    ),
    /*        apbif.master */   .apbmaster( apbaobdg        )
        );
    apb_thru uapbao(.apbslave (apbaobdg), .apbmaster(apbao));

docs/src/system-control.md:16
"BUREG — Backup registers in AO domain. Contents are retained during SoC power-down. Size: 32 bytes. Located at `0x4006_5000`-`0x4006_501F`."
```

**Preconditions.** Firmware uses BUREG for anything security-relevant, which the vendor documentation directs it to do. Attacker needs only the ability to issue bus reads/writes to 0x4006_5000 — no privilege escalation, since neither the AO bridge nor the module performs any check.

**Attack scenario.** Secure firmware follows docs/src/pmu.md:184 and stores a wrapped-key handle, a resume authentication token, or a PIN-attempt counter in BUREG before entering power-down. On resume, before or concurrently with the secure resume path, unprivileged application code (T1) — or the BIO/BDMA AHB master, whose hauser='0' matches no identity check anywhere in the design — simply reads 0x4006_5000..0x4006_501C and recovers all 256 bits, because there is no ownership tag, no lock bit, and no privilege gate on the path. The same access is a write: an attacker who cannot read a value can still overwrite it, so a PIN-attempt or anti-rollback counter kept in BUREG can be rewound to zero by any code that can issue a bus write, defeating lockout/throttling. Because there is no tamper input to this block, a physical attacker (T2) who trips the mesh or a sensor also does not cause the secret to be erased; combined with the fact that only PAD_XRSTn/POR clears these flops, the retained value survives every reset an attacker might trigger short of pulling the reset pin.

**Mitigation.** RTL: give aobureg a real `sfrlock` driven by a write-once lock bit (following the pattern in aes.sv:135 / combohasha.sv:159 rather than the `assign sfrlock = '0;` used here), and add an owner tag so that only the coreuser identity that wrote a slot can read it back — the mechanism already exists for the ReRAM key slots in rrc.sv and should be extended to the AO domain. Add a coreuser/hauser filter in front of the AO APB bridge at soc_top.sv:830-838. Route the tamper/mesh/sensor event into the AO domain and clear `cr_buregs` (and the AO SRAM) on it. Silicon workaround: firmware must not store plaintext secrets in BUREG. Store only a ciphertext blob whose key never leaves the SCE, and derive that key from something not resident in the AO domain, so that a BUREG read yields nothing usable; and store any monotonic counter in the ReRAM one-way counters at 0x603D_A000/B000 rather than in BUREG, since BUREG offers no rollback protection.

**Verification.** Verified as written; exploitability not fully established. aobureg.sv:26-35 is verbatim as quoted; `assign sfrlock = '0;` is at line 30 exactly, and the entire module is one `apb_cr #(.A('h0), .DW(32), .SFRCNT(REGCNT))` with no other logic. ao_top.sv:234-238 verbatim (resetn = porresetn, apbaos[5] -> 0x4006_5000). soc_top.sv:830-838 verbatim; I confirmed the ahbasync+apb_bdg pair carries no hauser/pprot/coreuser filtering and that coreuser is never used as a bus filter anywhere. The no-tamper-erase claim is correct and I verified it independently: `grep -rl 'tamper|mesh|sensorc'` hits only sec_inc.sv, soc_top.sv, soc_top_no_cm7_rv.sv, mesh.sv, secsub.sv and sensorc.sv - there is no tamper signal in rtl/modules/ao/ at all, and ao_top3's port list (ao_top.sv:32-104) has no tamper input. I mark this plausible rather than confirmed because everything hinges on firmware placing an asset in BUREG, which neither the RTL nor the documentation establishes.

**Corrections applied by the verifier.** The finder truncated the documentation quote in a way that flatters the finding. docs/src/system-control.md:16 in full reads: 'BUREG - Backup registers in AO domain. Contents are retained during SoC power-down. Size: 32 bytes. Located at `0x4006_5000`-`0x4006_501F`. Wake-up via interrupt will preserve the contents; wake-up by system reset will clear the contents.' The docs never designate BUREG as a secret store or claim any confidentiality/rollback property - 'the documented cross-power-down secret store' overstates them, and docs/src/pmu.md:184 says 'Store any important data', not 'secrets'. Restate as: 256 bits of always-on retained storage with no lock bit, no ownership tag and no privilege gate, in a design that does implement ownership for the ReRAM key slots and the SCE - an inconsistency worth fixing, but with no evidence any asset is actually placed there. Severity low, not medium.

---

<a id="bao-100"></a>

### BAO-100 — Security-error escalation to NMI is disabled at reset and can be silently re-masked: evc's `erren` resets to 0 with sfrlock hardwired to 0

**Severity: Low** | CWE-1233 Security-Sensitive Hardware Controls with Missing Lock Bit Protection | Threat actor: T1 (software on either CPU or control of the BIO/BDMA peripheral master) | Confidence: High

**Location:** `rtl/modules/sysctrl/rtl/evc.sv:158`

**Description.** The event controller aggregates the SoC's hard error sources into a single non-maskable interrupt to the CM7: `assign cm7nmi = |(errin&erren);`. In soc_top.sv the `errin` bundle is the set of security-relevant fault indications — `err[0] = |coresuberr`, `err[1] = |sceerr`, `err[2] = |ifsuberr`, `err[3] = |secirq` (the OR of the mesh, voltage/light sensor and glue-chain tamper interrupts from secsub), `err[4] = |aoramerr`. The enable mask `erren` is a plain APB control register instantiated with `.IV(0)`, and evc drives its own write-protect to a constant: `assign sfrlock = '0;`. Consequently (a) out of reset, and after every coreresetn — including the software core reset via RCURST1 at 0x4004_0084 — no error source, including tamper, raises an NMI; and (b) any bus master able to write 0x4004_4084 can clear the mask again at any time with no lock and no privilege check. There is no redundant or non-maskable path: the tamper indications reach the CPU only through this register (and through the ordinary maskable IRQ vector at ev[239:224]). Combined with the previous finding — that the mesh's clock itself can be stopped from the same unprotected APB block — an attacker can render the tamper subsystem both clock-dead and interrupt-silent with two 32-bit stores.

**Evidence.**
```systemverilog
rtl/modules/sysctrl/rtl/evc.sv:71
    assign cm7nmi = |(errin&erren);

rtl/modules/sysctrl/rtl/evc.sv:139-140
    logic sfrlock;
    assign sfrlock = '0;

rtl/modules/sysctrl/rtl/evc.sv:157-158
apb_fr #(.A('h80), .DW(ERRCNT)                   )  sfr_cm7errfr  (.fr(errin),      .prdata32(),.*);
apb_cr #(.A('h84), .DW(ERRCNT), .IV(0)           )  sfr_cm7errcr  (.cr(erren),      .prdata32(),.*);

rtl/asic_top/rtl/soc_top.sv:479-483
    assign err[0] = |coresuberr;
    assign err[1] = |sceerr;
    assign err[2] = |ifsuberr;
    assign err[3] = |secirq;
    assign err[4] = |aoramerr;

rtl/asic_top/rtl/soc_top.sv:494-499
        .evin       (ev|256'h0),
        .errin      (err|16'h0),
        // m7
        .cm7irq,
        .cm7ev,
        .cm7nmi,
```

**Preconditions.** For the reset-state exposure: none — this is the power-on and post-core-reset condition. For the active-masking case: one APB write to 0x4004_4084 (evc is apbsys[4], base 0x4004_4000), reachable from the CM7 AHB-P, Vex AHB-P, MDMA or BDMA peripheral AHB master, with no coreuser/pprot check.

**Attack scenario.** 1. Attacker with code execution writes 0 to EVC_ERRCR at 0x4004_4084 (or simply relies on the reset value if he can force a core reset first — RCURST1 at 0x4004_0084 accepts 0x55AA from any master and, per sysctrl.sv:803, drives coreresetgen, which is evc's reset). 2. `erren` is now 0, so `cm7nmi` is stuck low regardless of what `errin` reports. 3. Any subsequent tamper event (mesh aperture break, voltage/light sensor trip, glue-chain break — all funnelled through `err[3] = |secirq`), SCE error, or AO RAM ECC error is no longer escalated. The flag register EVC_ERRFR at 0x4004_4080 still shows the event, but nothing forces the CPU to look. 4. Combined with the mesh clock-gate kill described above, the attacker has both removed the detector and removed the alarm. The window is also relevant on its own: between reset release and the first firmware write to EVC_ERRCR, any hard error — including a tamper trip during early boot, which is exactly when secrets are being loaded — is silently ignored.

**Mitigation.** RTL fix: make the security-critical error bits (at minimum err[3], the tamper OR) non-maskable — route them to cm7nmi unconditionally, or give `sfr_cm7errcr` a sticky set-only semantic (bits can be enabled but never disabled without a system reset) plus a real sfrlock driven from a write-once lock register, and set `.IV` so tamper escalation is ON out of reset rather than OFF. Route the tamper OR to `secresetn` as well so it does not depend on the CPU responding at all. Firmware workaround on fabricated silicon: have the boot ROM write EVC_ERRCR = 0x1F as one of its very first actions, before any secret is loaded; and because the register cannot be locked, add a periodic integrity check that re-reads 0x4004_4084 and treats any cleared bit as a tamper event. Also enable the redundant maskable IRQ path (ev[239:224] via EVC_CM7EVSEL/EVC_CM7EVEN) so there are two independent notifications.

**Verification.** Independently confirmed by a second reviewer. Code verified verbatim: evc.sv:71 `assign cm7nmi = |(errin&erren);`, evc.sv:139-140 `logic sfrlock; assign sfrlock = '0;`, evc.sv:157-158 the apb_fr/apb_cr pair with `.IV(0)` on sfr_cm7errcr at offset 0x84. soc_top.sv:479-483 matches exactly, including `assign err[3] = |secirq;`, and evc is apbsys[4] (soc_top.sv:492) so the register really is at 0x4004_4084. The reset domain claim also holds: soc_top.sv:491 `.resetn (coreresetn)` and sysctrl.sv:871 `apb_ar #(.A('h84), .AR('h55aa)) sfr_rcurst1 (.ar(corereset_sw), .*);` feeding coreresetgen at sysctrl.sv:802-807, so a software core reset does clear erren. What I could not substantiate is the impact framing, given the unmasked cm7irq broadcast above.

**Corrections applied by the verifier.** The claim 'there is no redundant or non-maskable path' is wrong in two ways. (1) evc.sv:63 `theregrn( cm7irq ) <= evin;` is unmasked inside evc, and cm7irq is broadcast to both CPU subsystems (soc_top.sv:497 `.cm7irq,`, :599 `.cm7_irq ( cm7irq[IRQCNT-1-16:0] )` into soc_coresub, :781 the same into soc_ifsub); since soc_top.sv:472-473 puts `err` at ev[223:192] and `secirq` at ev[239:224], both the raw tamper bits and the error bundle reach the CPU interrupt vector regardless of `erren`. Masking then happens in the CPU's own controller, not here. (2) There is a CPU-independent hardware tamper path for the sensor branch: secsub drives `vdresetn` -> soc_top.sv:712 `.vdresetn ( secresetn )` -> sysctrl.sv:795 sysresetgen `.resetnin ( { socresetn, vdresetn, secresetn, ~sysreset_sw } )`. Only the mesh and gluechain lack such a path. Also, an interrupt-enable register with IV=0 is the normal idiom throughout this SoC, so 'disabled at reset' is not itself the defect; the actionable part is the missing lock and the missing mesh-to-reset path. Severity dropped to low.

---

<a id="bao-101"></a>

### BAO-101 — cgucore's `porresetn` and `resetn` are both wired to `sysresetn` in sysctrl, defeating the stated guarantee that the CLKSYS source selection survives a user-mode reset

**Severity: Low**

**Location:** `rtl/modules/sysctrl/rtl/sysctrl.sv:415`

*Surfaced by the independent verifier, not the original domain reviewer.*

**Description.** cgucore deliberately separates two reset domains for the CLKSYS root mux. Its header comment (cgucore.sv:67-69) states the intent explicitly: 'clksys is basic clk should be guaranteed without PLL / it starts from clkosc, and can be redirected to xtal by software. / ****usermode reset(resetn here) will not change the selection.****' — and the implementation honours that by clocking the select chain and the glitchless mux off `porresetn` (cgucore.sv:72-73, 78) while everything else uses `resetn`. The integration in sysctrl throws the distinction away: both ports are connected to the same net, `sysresetn`. The commented-out `//coreresetn` on line 416 shows `resetn` was originally meant to be the core reset, which is what made `porresetn` meaningful. As wired, every system reset — including the software-writable RCURST0 action register (sysctrl.sv:870, magic 0x55AA at 0x4004_0080), the voltage-detector tamper reset `vdresetn`, and `secresetn` — resets the CLKSYS select chain. Compounding this, the CGUSEL1 SFR that feeds it is itself reset by sysresetn (sysctrl.sv:846 `.resetn(sysresetn)`) and cgucore.sv:72 follows `clksyssel` unconditionally with no update-enable, so the mux really does revert. The effect is that the SoC's root timebase silently falls back from the external crystal to the internal RC oscillator on any system reset — and that RC oscillator's trim is the software-writable `sfr_ipcosc` (sysctrl.sv:880, 257), i.e. the fallback source is the one an attacker can retune.

**Evidence.**
```systemverilog
rtl/modules/sysctrl/rtl/sysctrl.sv:415-416
       /*input   logic               */.porresetn          (sysresetn),
        /*input   logic               */.resetn             (sysresetn),//coreresetn),

rtl/modules/sysctrl/rtl/cgucore.sv:67-69
// clksys is basic clk should be guaranteed without PLL
// it starts from clkosc, and can be redirected to xtal by software.
// ****usermode reset(resetn here) will not change the selection.****

rtl/modules/sysctrl/rtl/cgucore.sv:72-82
    `theregfull(clksys, porresetn, clksysselreg0, 1'b0) <= clksyssel;
    `theregfull(clksys, porresetn, clksysselreg , 1'b0) <= clksysselreg0 ;

    cgudyncswt uclksyssel(
        .clk0   (clksrc[0]),
        .clk1   (clksrc[1]),
        .resetn (porresetn),
        .clksel (clksysselreg),
        .clk0en (clksysselen_tmp[0]),
        .clk1en (clksysselen_tmp[1])
    );

rtl/modules/sysctrl/rtl/sysctrl.sv:846
    apb_cr #(.A('h30), .DW(1))      sfr_cgusel1 (.cr(cfgsel1),  .prdata32(),  .resetn(sysresetn),.*);

rtl/modules/sysctrl/rtl/sysctrl.sv:870
    apb_ar #(.A('h80), .AR('h55aa))        sfr_rcurst0    (.ar(sysreset_sw),   .*);
```

**Attack scenario.** Firmware that requires an accurate, attacker-independent timebase — for example a boot stage that measures an operation's duration, or code relying on the crystal for a tamper-response timeout — redirects CLKSYS to the external crystal by writing CGUSEL1 = 1 at 0x4004_0030, relying on the module's stated guarantee that a user-mode reset will not change the selection. An attacker with peripheral-bus access writes 0x55AA to RCURST0 at 0x4004_0080. sysresetn asserts; because sysctrl.sv:415 ties cgucore's porresetn to that same net, clksysselreg0/clksysselreg clear and cgudyncswt's sync flops clear, and because sfr_cgusel1 also resets on sysresetn, cfgsel1 returns to 0 — the mux switches back to clksrc[0], the internal RC oscillator, whose frequency the attacker can then move with sfr_ipcosc (0x4004_009C) plus the ipflow action write. The same silent fallback happens on any tamper-driven secresetn/vdresetn, i.e. exactly when the timebase matters most, and nothing reports the source change (the freqmeter measures clkosc and clkxtl separately but drives nothing).

**Verification.** No independent verdict recorded for this entry.

---

<a id="bao-102"></a>

### BAO-102 — CGUOWR, the CGU's only write-once primitive, is inert: `apb_owr`'s `owr` output port is never driven and the net is never consumed

**Severity: Low**

**Location:** `rtl/modules/sysctrl/rtl/sysctrl.sv:977`

*Surfaced by the independent verifier, not the original domain reviewer.*

**Description.** The CGU exposes a register documented as the 'CGU one-way register' at 0x4004_00C0 (docs/src/clock-generation.md, register table). Internally `apb_owr` builds exactly the primitive a lock bit needs: a per-bit action register, a sticky set-only flop (`wronereg[i] <= wronereg[i] | wrone[i]`, clearable only by reset), and a status register to read it back. But the module's `output logic [DW-1:0] owr` port is never assigned anywhere in the module body (sysctrl.sv:979-993 — the generate block drives `wrone` and `wronereg`, and only `wronereg` reaches the readback SFR). On the outside, sysctrl.sv:816 declares `bit [31:0] owr;` and sysctrl.sv:887 connects it to that dead port; grep shows no other reference in the file. So the register is a software-visible sticky scratchpad with zero hardware effect. Taken together with the undriven `sfrlock` port confirmed above, the CGU/RCU/IPC register bank at 0x4004_0000 — which holds the clock source selects, all frequency dividers, the PLL ratio, the OSC trim, the clock sub-gates and both software reset action registers — has no functioning write-protection mechanism of any kind, despite containing two separate half-built ones. This is corroborating evidence for the vendor that the omission is an oversight rather than a design decision, and it identifies the exact hook to attach a lock to in a future stepping.

**Evidence.**
```systemverilog
rtl/modules/sysctrl/rtl/sysctrl.sv:962-995
module apb_owr
#(
      parameter A=0,
      parameter AW=12,
      parameter DW=16
)(
        input  logic                          pclk        ,
        input  logic                          resetn      ,
        apbif.slavein                         apbs        ,
        input  bit                          sfrlock     ,
        output logic [31:0]                 prdata32    ,
        output logic [DW-1:0]   owr
);

    bit [DW-1:0] wrone, wronereg;
    logic clk;
    assign clk = pclk;

genvar i;
generate
    for (i = 0; i < DW; i++) begin: gar
    apb_ar #(.A(A), .AW(AW), .AR(i)         )  sfr_ar    (.ar(wrone[i]),              .*);
    `theregrn( wronereg[i] ) <= wronereg[i] |wrone[i];
    end
endgenerate

    apb_sr #(.A(A),  .AW(AW),  .DW(DW)           )  sfr_sr    (.sr(wronereg),  .prdata32(prdata32),.*);


endmodule

rtl/modules/sysctrl/rtl/sysctrl.sv:816
    bit [31:0] owr;

rtl/modules/sysctrl/rtl/sysctrl.sv:887
    apb_owr #(.A('hc0), .DW(32) )    sfr_owr   (.owr(owr),     .prdata32(),.*);
```

**Attack scenario.** There is no direct exploit for the dead register itself; the exposure is the absence it demonstrates. Firmware hardening guidance for this part might reasonably assume CGUOWR is the CGU's lock and set its bits during boot to freeze the clock tree before dropping privilege. Because `owr` is an unconnected output port, every one of those bits reads back as set while gating nothing: an attacker who subsequently reaches the peripheral APB writes CGUFD_HCLK/CGUSET, CGUPCLKGR or RCURST0 exactly as if the lock had never been written, and a firmware integrity check that re-reads CGUOWR to confirm the lock is still engaged sees the correct sticky value and reports the system as protected.

**Verification.** No independent verdict recorded for this entry.

---

<a id="bao-103"></a>

### BAO-103 — Host APB reads of a running BIO machine's instruction-RAM page return the last word that machine read from its private RAM, defeating the chip-enable gating that is supposed to make the RAM inaccessible to the host while the machine runs

**Severity: Low**

**Location:** `rtl/modules/bio_bdma/rtl/bio_bdma.sv:1735`

*Surfaced by the independent verifier, not the original domain reviewer.*

**Description.** The design deliberately partitions access to each machine's 4 KiB private RAM: bio_bdma.sv:1738 `assign imem_wr_mode[j] = en_sync[j]; // when machine j is disabled, the host can use its port to read/write`, and the RAM chip-enable at :1796-1797 only honours a host PSEL when the machine is stopped — `.ce_n(~( mem_la_write[j] || mem_la_read[j] || (psel_sync[j][1] & ~imem_wr_mode[j])))`, with the in-line comment "during host mode, access whenever PSEL active". The intent is clearly that while machine j runs, the host's APB window onto page j is dead. It is not. The capture register at :1735 samples the RAM output every aclk unconditionally, with no qualification on imem_wr_mode, host_mem_rd or PSEL, and the APB read data is that capture register: :1708 `assign apbx_imem[j].prdata = host_mem_rdata;` fed by the priority mux at :1691-1699. So an APB read of the imem page while the machine is running does not read the RAM (the chip-enable is correctly withheld) but does return `ram_rd_data[j]` frozen at whatever word the running machine last fetched or loaded. Repeated polling of 0x5012_5000+ therefore samples the private instruction/data stream of a running BIO core. This is a leak of state the RTL's own gating was written to protect, through a register that bypasses that gating.

**Evidence.**
```systemverilog
bio_bdma.sv:1735 (unconditional capture — no imem_wr_mode / PSEL qualification)
                host_mem_rdata_capture[j] <= ram_rd_data[j];

bio_bdma.sv:1708 (APB read data is that capture register)
            assign apbx_imem[j].prdata = host_mem_rdata;

bio_bdma.sv:1691-1699 (priority mux, aclk)
        if (host_mem_rd[0]) begin
            host_mem_rdata <= host_mem_rdata_capture[0];
        end else if (host_mem_rd[1]) begin
        ...

bio_bdma.sv:1738 (the intent)
            assign imem_wr_mode[j] = en_sync[j]; // when machine j is disabled, the host can use its port to read/write

bio_bdma.sv:1790-1797 (the gating that this bypasses)
                .ce_n(~(
                    mem_la_write[j] || mem_la_read[j] // during run mode, make sure data does not move
                    || (psel_sync[j][1] & ~imem_wr_mode[j]))), // during host mode, access whenever PSEL active
```

**Attack scenario.** Firmware runs a trusted BIO program on machine 0 that stages sensitive material through machine 0's private RAM (a key being moved between the SCE and a peripheral, for example) and relies on the run-mode chip-enable gating plus the machine-enable bit to keep that RAM opaque to anything holding only the imem APB window at 0x5012_5000-0x5012_5FFF. A concurrently running agent that holds that window polls it and recovers a stream of the words machine 0 most recently read from its own RAM, without ever stopping the machine (stopping it would be observable via SFR_CTRL and SFR_DBG0). The leak rate is bounded by the APB read rate versus the aclk overwrite rate, so it is a sampling channel rather than a full dump, and the attacker and the BIO are in the same trust domain in the default architecture — hence low rather than medium. The defect is nonetheless a concrete failure of an access control the RTL explicitly implements.

**Verification.** No independent verdict recorded for this entry.

---

<a id="bao-104"></a>

### BAO-104 — Mailbox status register reports rx_err and tx_err swapped, so the receiver's stale-data indicator is wrong

**Severity: Low** | CWE-1245 Improper Finite State Machines in Hardware Logic (status signal cross-wired) | Threat actor: T1 (unprivileged software on either CPU); also triggers spontaneously as a reliability bug | Confidence: High

**Location:** `rtl/modules/mbox/rtl/mbox.sv:96`

**Description.** `mbox_apb` connects the mailbox client's two error outputs to local wires of the OPPOSITE name (lines 96-97), and then packs those local wires into the status register in their nominal order (line 113). The net effect is a single, uncancelled swap: `sfr_status` bit [5], which the field ordering names `rx_err`, actually carries `mbox_client.sfr_sr_tx_err`, and bit [4], named `tx_err`, carries `mbox_client.sfr_sr_rx_err`.

This matters because `rx_err` is the only signal that tells the receiver its last read was invalid. `mbox_client.v:269` exposes the read data as `assign sfr_sr_rdata = mbox_r_dat;` - a direct combinational tap of the peer's FIFO output, with NO qualification by `mbox_r_valid`. Reading 0x4001_3004 when the peer's FIFO is empty therefore returns whatever `mailbox_syncfifobufferedmacro0_fifo_dout` happens to be holding (cram_axi.sv:12743), i.e. the previous message's last word, and the only indication is `sfr_sr_rx_err`, set at mbox_client.v:534-535 by `(mbox_r_ready & (~mbox_r_valid))`. That indication lands in the wrong bit.

Because bits [4] and [5] are cleared together by the same status read (`sr_read_aclk & ~sr_read_r`, mbox_client.v:521 and :531), software that tests only its own direction's bit will silently accept stale data whenever the other direction's error is clear.

**Evidence.**
```systemverilog
rtl/modules/mbox/rtl/mbox.sv:96-97 (client outputs bound to the opposite-named local wires)
```
        .sfr_sr_rx_err(tx_err),
        .sfr_sr_tx_err(rx_err),
```
rtl/modules/mbox/rtl/mbox.sv:113 (local wires packed in nominal order - the swap is not undone)
```
    apb_asr #(.A('h8), .DW(6) )      sfr_status            (.sr({rx_err, tx_err, abort_ack, abort_in_progress, tx_free, rx_avail}), .ar(status_read), .prdata32(),.*);
```
What rx_err actually means inside the client - rtl/modules/mbox/rtl/mbox_client.v:531-539
```
    if ((sr_read_aclk & (~sr_read_r))) begin
        sfr_sr_rx_err <= 1'd0;
    end else begin
        if ((mbox_r_ready & (~mbox_r_valid))) begin
            sfr_sr_rx_err <= 1'd1;
        end else begin
            sfr_sr_rx_err <= sfr_sr_rx_err;
        end
    end
```
and the unqualified read data it is meant to guard - rtl/modules/mbox/rtl/mbox_client.v:269
```
assign sfr_sr_rdata = mbox_r_dat;
```
The same swap is present in the second copy of this wrapper, rtl/modules/vexriscv/lib/mbox_v0.1.sv:96-97 and :113.
```

**Preconditions.** Software on either side relies on the mailbox status register's rx_err/tx_err bits, which is the only error signalling the hardware provides. Exploitation of the replay variant requires the attacker to be able to read 0x4001_3004, which per the access-control finding is unrestricted.

**Attack scenario.** 1. The Vex's secure task sends an N-word response to the CM7. The CM7's firmware drains it; the last word W_last remains latched on `mailbox_syncfifobufferedmacro0_fifo_dout` because the FIFO output register is not cleared when the FIFO empties.\n2. Attacker code (or the CM7's own driver, under a race with the abort path, which flushes the peer FIFO at cram_axi.sv:12727/12750 without clearing this output register) reads 0x4001_3004 once more. `mbox_r_valid` is 0, so nothing is popped, but `sfr_sr_rdata` still returns W_last verbatim.\n3. The client sets `sfr_sr_rx_err`. The reader checks status bit [5], the bit named rx_err - and gets `tx_err` instead, which is 0 because its own transmit side is idle. The reader concludes the word is valid and consumes a replayed word of the previous message.\n4. Symmetrically, a genuine transmit-side error (mbox_client.v:524-525, set when a word is written while the previous one is still stalled) is reported in bit [4] but read out of bit [5], so a sender that checks tx_err never sees its own dropped word and believes the message was delivered intact.\nThe practical consequence is a message-boundary desync: if the protocol is positional (word 0 = opcode, words 1..n = payload), a replayed or silently dropped word shifts every subsequent word by one, and the receiver interprets payload as an opcode.

**Mitigation.** RTL: correct the port bindings so the names match end to end - `.sfr_sr_rx_err(rx_err), .sfr_sr_tx_err(tx_err)` at mbox.sv:96-97 (and identically in rtl/modules/vexriscv/lib/mbox_v0.1.sv). Independently, qualify the read data so an empty read cannot return stale bytes: `assign sfr_sr_rdata = mbox_r_valid ? mbox_r_dat : 32'h0;` at mbox_client.v:269, and clear the peer FIFO output register on abort/flush. Give rx_err and tx_err separate write-1-to-clear bits rather than clearing both on any status read.\nFirmware workaround on fabricated silicon: treat status bit [5] as tx_err and bit [4] as rx_err - i.e. swap the two masks in both drivers, and document it. Do not rely on either bit for message integrity: check `rx_avail` (bit [0]) BEFORE every read of 0x4001_3004 rather than checking an error bit after, and carry an explicit length and sequence number inside the message so a shifted or replayed word is detectable at the application layer.

**Verification.** Independently confirmed by a second reviewer. Verified mbox.sv:96-97 verbatim: `.sfr_sr_rx_err(tx_err),` / `.sfr_sr_tx_err(rx_err),` - the client's outputs are bound to the opposite-named local wires (declared at mbox.sv:61-62). Verified mbox.sv:113 verbatim: `.sr({rx_err, tx_err, abort_ack, abort_in_progress, tx_free, rx_avail})`, MSB-first, so bit[5]=local rx_err=client sfr_sr_tx_err and bit[4]=local tx_err=client sfr_sr_rx_err. The swap is single and uncancelled - confirmed.
Verified the semantics inside the client: mbox_client.v:531-539 sets sfr_sr_rx_err on `(mbox_r_ready & (~mbox_r_valid))`, i.e. a receive underflow, and mbox_client.v:521-529 sets sfr_sr_tx_err on `((mbox_w_valid & (~mbox_w_ready)) & w_pending)`, i.e. a transmit stall. So the port names are semantically correct at the client and it is the wrapper binding that is wrong.
Verified the duplicate: rtl/modules/vexriscv/lib/mbox_v0.1.sv:96-97 and :113 are identical, so the same swap exists on both endpoints.
Verified mbox_client.v:269 `assign sfr_sr_rdata = mbox_r_dat;` is unqualified by mbox_r_valid, so the stale-read premise is correct.
Cross-checked against the software contract: rtl/scripts/headergen/output/bao1x_peri.svd MBOX_APB SFR_STATUS declares rx_avail[0], tx_free[1], abort_in_progress[2], abort_ack[3], tx_err[4], rx_err[5]. Since the SVD is machine-generated from the wrapper's field-name order and not from the client's function, the header will tell firmware bit[5] is rx_err while it actually carries tx_err. Documented-vs-implemented mismatch confirmed.

**Corrections applied by the verifier.** The swap is real and I additionally confirmed it is a documented-behaviour-vs-RTL mismatch, which the finder did not cite: the generated SVD that produces the software headers declares bit[4]=tx_err and bit[5]=rx_err (rtl/scripts/headergen/output/bao1x_peri.svd, MBOX_APB SFR_STATUS), while the RTL puts the client's tx_err in bit[5] and the client's rx_err in bit[4]. Severity should be low rather than medium: both bits feed the same interrupt (mbox_client.v:264 `sfr_int_error = (sfr_sr_tx_err | sfr_sr_rx_err)`) so an error is still signalled, both are cleared by the same status read so no error is lost, and a correctly written driver checks rx_avail (bit[0]) before reading rather than checking an error bit afterwards. The consequence is misattribution of an already-signalled error, not silent acceptance in the general case.

---

<a id="bao-105"></a>

### BAO-105 — Mailbox transmit word is a live tap of the APB register, and a second write during the CDC "blind" window is silently swallowed - word substitution with no error flag

**Severity: Low** | CWE-367 Time-of-check Time-of-use (TOCTOU) Race Condition | Threat actor: T1 (unprivileged software on either CPU, or any DMA master under its control) | Confidence: Medium

**Location:** `rtl/modules/mbox/rtl/mbox_client.v:265`

**Description.** The CM7-side mailbox has no transmit FIFO and does not latch the word at handshake time. `mbox_w_dat` is assigned directly and combinationally from the APB control register `sfr_cr_wdata` (line 265), which is the plain, unlocked register at 0x4001_3000 (mbox.sv:111, with `sfrlock` tied to 0 at mbox.sv:104). The value seen by the peer is therefore whatever is in that register at the instant the peer captures it, not the value that was in it when the "written" event was raised.

The "written" event itself is rate-limited by a blind flag: `wdata_sync_ps_i = wdata_sync_i & ~wdata_sync_blind` (line 275), where `wdata_sync_blind` is set on the first write pulse and only cleared when the far-side acknowledgement returns (lines 412-417). A second write to 0x4001_3000 that arrives before that round trip completes therefore generates NO second toggle - the event is discarded - but it DOES overwrite `sfr_cr_wdata`, and hence changes `mbox_w_dat` under the still-asserted `mbox_w_valid`.

The result is that the first word is destroyed and the second is transmitted in its place, exactly once. No status bit reports it: `sfr_sr_tx_err` is set only by `(mbox_w_valid & ~mbox_w_ready) & w_pending` (lines 524-525), which does not fire in this sequence, and `sfr_sr_tx_free` (line 268) reports the channel as having accepted a word. This violates the basic valid/ready stability rule - once VALID is asserted the payload must not change until READY - and, because the register is writable by any master, it turns into a substitution primitive against the other CPU's outgoing message.

**Evidence.**
```systemverilog
rtl/modules/mbox/rtl/mbox_client.v:265-268 (payload is the register itself, not a captured copy)
```
assign mbox_w_dat = sfr_cr_wdata;
assign mbox_w_valid = ((cr_wdata_written_aclk & (~w_valid_r)) | w_pending);
assign mbox_w_done = (ar_done_aclk & (~ar_done_r));
assign sfr_sr_tx_free = (~(mbox_w_valid | w_pending));
```
rtl/modules/mbox/rtl/mbox_client.v:275 and :411-421 (the second write's event is swallowed while blind is set)
```
assign wdata_sync_ps_i = (wdata_sync_i & (~wdata_sync_blind));
...
always @(posedge pclk_clk) begin
    if (wdata_sync_i) begin
        wdata_sync_blind <= 1'd1;
    end
    if (wdata_sync_ps_ack_o) begin
        wdata_sync_blind <= 1'd0;
    end
    if (wdata_sync_ps_i) begin
        wdata_sync_ps_toggle_i <= (~wdata_sync_ps_toggle_i);
    end
```
rtl/modules/mbox/rtl/mbox_client.v:521-529 (the error flag that does NOT cover this case)
```
    if ((sr_read_aclk & (~sr_read_r))) begin
        sfr_sr_tx_err <= 1'd0;
    end else begin
        if (((mbox_w_valid & (~mbox_w_ready)) & w_pending)) begin
            sfr_sr_tx_err <= 1'd1;
        end else begin
            sfr_sr_tx_err <= sfr_sr_tx_err;
        end
    end
```
The unlocked, unqualified register being tapped - rtl/modules/mbox/rtl/mbox.sv:104 and :111
```
    assign sfrlock = '0;
...
    apb_acr #(.A('h0), .DW(32))      sfr_wdata             (.cr(wdata), .ar(wdata_written), .prdata32(),.*);
```

**Preconditions.** Write access to 0x4001_3000, which is unrestricted (no sfrlock, no coreuser/hauser check on the APB path - see the mailbox access-control finding). The substitution window is the pclk->aclk->pclk pulse-synchronizer round trip, roughly 4-6 clocks, and is entered on every legitimate transmit.

**Attack scenario.** 1. The CM7's secure firmware writes word W1 of a command to 0x4001_3000. `sfr_cr_wdata`=W1, the write pulse enters the pclk->aclk pulse synchronizer, and `wdata_sync_blind` is set for the several-cycle round trip (pclk toggle -> 2 aclk flops -> ack toggle -> 2 pclk flops).\n2. Within that window, attacker code running on either CPU (or an SCE-DMA / BDMA descriptor pointed at 0x4001_3000) writes W2 to the same address. There is no lock and no identity check, so the write lands.\n3. `sfr_cr_wdata` becomes W2 immediately. Because `mbox_w_dat` is a live tap, the value presented to the Vex changes to W2 while `mbox_w_valid` is asserted. The attacker's write generates no second valid, because `wdata_sync_blind` is still 1.\n4. The Vex's RX FIFO captures W2. The CM7 sees `tx_free` return, `tx_err` clear, and no interrupt - it believes W1 was delivered.\n5. If W1 was an opcode or a length field, the Vex now acts on the attacker's substitute; if W1 was a payload word, the message is corrupted at a position the sender cannot detect. Repeating the trick lets the attacker rewrite selected words of a secure command stream while the sender's own error reporting stays clean.\nA weaker, non-adversarial form of the same defect: two back-to-back store instructions to 0x4001_3000 (2-3 hclk apart, far shorter than the CDC round trip) always lose the first word silently, so any driver that does not poll tx_free between every single word drops data with no indication.

**Mitigation.** RTL: capture the payload into a dedicated shadow register at the moment the write event is accepted, and drive `mbox_w_dat` from that shadow rather than from the live CR - e.g. `theregfull(pclk, resetn, wdat_latched, '0) <= (sfr_cr_wdata_written & ~wdata_sync_blind) ? sfr_cr_wdata : wdat_latched;` with `assign mbox_w_dat = wdat_latched;`. Additionally, raise a sticky error when a write arrives while `wdata_sync_blind` is set, instead of discarding it silently, and make `sfr_wdata` reject writes while `~sfr_sr_tx_free`. Combine with a real `sfrlock` and an identity check on the APB path so a second writer cannot exist in the first place.\nFirmware workaround on fabricated silicon: never write 0x4001_3000 without first reading 0x4001_3008 and confirming `tx_free`; after each word, re-read 0x4001_3000 and confirm it still holds the value just written before proceeding (this detects, though does not prevent, substitution). Most importantly, authenticate the message at the application layer - a MAC over the whole message computed by the sender and checked by the receiver makes any substituted word detectable regardless of the hardware race.

**Verification.** Verified as written; exploitability not fully established. Verified mbox_client.v:265-268 verbatim, including `assign mbox_w_dat = sfr_cr_wdata;` at line 265 - the payload is the live APB control register, never latched at handshake time. Verified mbox_client.v:275 `assign wdata_sync_ps_i = (wdata_sync_i & (~wdata_sync_blind));` and the blind-flag logic at mbox_client.v:411-421, which matches the quote exactly: blind is set on any wdata_sync_i and cleared only on wdata_sync_ps_ack_o, and the toggle is generated only from the blinded signal. So a second write pulse inside the round trip is genuinely discarded.
Verified that the second write still lands in the register: mbox.sv:111 `apb_acr #(.A('h0), .DW(32)) sfr_wdata (.cr(wdata), .ar(wdata_written), ...)` with sfrlock hard-zero at mbox.sv:104, and apb_sfr2 (apb_sfr.sv:339) `sfrdatarr[i] <= ( sfrsel[i] & apbwr ) ? apbslave.pwdata : sfrdatarr[i]` - unconditional on any addressed write. So mbox_w_dat does change under an asserted mbox_w_valid. The stability violation is real.
Verified the valid/pending logic at mbox_client.v:508-519: `w_pending <= 1'd1` only when the write arrives with `~mbox_w_ready`, and mbox_w_valid = pulse | w_pending (line 266). So in the finder's exact sequence (peer ready) w_pending is 0 and tx_err indeed does not fire - the finder is right about that specific case. But the wide-window variant they describe as the practical one goes through w_pending, where tx_err does fire.
I found no compensating control - there is no back-pressure on the CR write, no reject-while-busy, and sfr_sr_tx_free (line 268) is derived from aclk-domain state that has not yet updated when the second write arrives, so polling tx_free immediately after a write does not close the hole either. The defect is real; only the exploit value is uncertain.

**Corrections applied by the verifier.** The RTL reads exactly as described and the valid/ready payload-stability violation is real. Two corrections to the impact. (1) The adversarial substitution window is only the pclk->aclk->pclk pulse-synchronizer round trip - roughly 2 pclk + 2 aclk cycles - and the peer captures the word after only ~2 aclk cycles, so a second bus master must land an APB write inside a ~2-3 clock window. Given an AHB-to-APB transfer takes at least 2 pclk cycles plus bridge and arbitration latency, an attacker cannot hit this deterministically; an attacker who can write 0x4001_3000 at all can corrupt the channel far more simply (finding 2), so this adds little. (2) The finder's claim that no status bit reports the loss is only true when the peer was ready. In the more reachable variant - a second write while w_pending is set because the peer FIFO is full - mbox_client.v:524-525 `((mbox_w_valid & (~mbox_w_ready)) & w_pending)` DOES set sfr_sr_tx_err, so that case is flagged. Downgrading to low.

---

<a id="bao-106"></a>

### BAO-106 — APB and AHB SFR banks ignore write byte strobes, so any sub-word write clobbers all 32 bits of the register

**Severity: Low**

**Location:** `rtl/modules/amba/rtl/apb_sfr.sv:339`

*Surfaced by the independent verifier, not the original domain reviewer.*

**Description.** `apb_sfr2` and `ahb_sfr2` are the register-bank primitives behind every apb_cr/apb_acr/apb_fr and ahb_cr/ahb_fr instance in the SoC. Neither consumes the write strobes. In `apb_sfr2` the register update at apb_sfr.sv:339 writes the full `apbslave.pwdata` whenever the address matches and `apbwr` is asserted; `pstrb` is never referenced anywhere in apb_sfr.sv (I grepped the whole file - the only pstrb hit is `assign apbmaster.pstrb = 0` in the null-master stub at line 269). `ahb_sfr2` is the same: ahbs_trans is instantiated with `.byte_strobe(reg_byte_strobe)` and the resulting net is never read, while the update at ahb_sfr.sv:262 stores the whole `reg_wdata`. On AHB and APB, the byte lanes not selected by the transfer size / strobe carry undefined data, so a byte or halfword store to any control register in this SoC overwrites the other lanes with whatever the master happened to leave on the bus. Security-relevant control registers routinely pack a lock/enable bit next to a data field in the same 32-bit word (e.g. sysctrl CGUSEC, the SCE global control registers, the RRC control register at rrc.sv:274), so a driver performing a byte-granular field update silently rewrites the neighbouring security bits to an attacker-irrelevant but unpredictable value - and a compiler is entitled to narrow a volatile field access to a byte store.

**Evidence.**
```systemverilog
rtl/modules/amba/rtl/apb_sfr.sv:335-341 (pwdata written whole; pstrb never referenced)
```
    logic apbrd, apbwr;
    assign apbrd = apbslave.psel & apbslave.penable & ~apbslave.pwrite;
    assign apbwr = ~sfrlock & apbslave.psel & apbslave.penable & apbslave.pwrite;
...
        `theregfull( pclk, resetn, sfrdatarr[i], IV ) <= ( sfrsel[i] & apbwr ) ? apbslave.pwdata : sfrdatarr[i];
```
rtl/modules/amba/rtl/ahb_sfr.sv:216-262 (byte_strobe is captured from ahbs_trans and then never used)
```
  wire  [3:0]            reg_byte_strobe;
...
      .byte_strobe  (reg_byte_strobe),
...
        `theregfull( hclk, resetn, sfrdatarr[i], IV ) <= ( sfrsel[i] & reg_write_en ) ? reg_wdata : sfrdatarr[i];
```
The interfaces do carry the strobe, so the information is available and is being discarded - rtl/modules/common/rtl/amba_interface_def.sv:373
```
    wire   [3:0]       pstrb;
```

**Attack scenario.** This is a latent-corruption defect rather than a direct attacker primitive - an attacker who can write the register at all can already write the whole word. The realistic failure is a confused-deputy one: privileged firmware updates one byte-wide field of a packed security register (for example a trim or mode byte) with a byte store; the hardware writes all four bytes, and the adjacent lock/enable bits in the same word are set to the undefined content of the unselected byte lanes. If those bits control a write-protect or a mode gate, the register silently ends up in a permissive state that the firmware believes it never touched, with no bus error and no way to detect it other than reading the register back. The same mechanism means any sub-word write anywhere in the SoC's SFR space is a latent corruption of three neighbouring bytes.

**Verification.** No independent verdict recorded for this entry.

---

<a id="bao-107"></a>

### BAO-107 — Mailbox APB slave returns PREADY=1 unconditionally, so gating the mailbox clock silently discards inter-CPU messages with an OKAY response

**Severity: Low**

**Location:** `rtl/modules/mbox/rtl/mbox.sv:105`

*Surfaced by the independent verifier, not the original domain reviewer.*

**Description.** `mbox_apb` expands the `apbs_common` macro (apb_sfr.sv:19-23), which hard-ties `apbx.pready = 1'b1` and `apbx.pslverr = 1'b0` as pure constants - they do not depend on pclk and are not qualified by the peripheral's clock gate. Meanwhile both of the mailbox's clocks are software-gateable: soc_coresub.sv:438-439 gates aclk and hclk into the mailbox with `clkmboxgate`, which is soc_top.sv:576 `aclksubgate[5]`, which is a plain read/write control register in the CGU (sysctrl.sv:864, `apb_cr #(.A('h60), .DW(ACKCNT), .IV('hff)) sfr_aclkgr (.cr(aclksubgate),...)`, documented as CGUACLKGR at 0x4004_0060), whose sfrlock is the undriven net at soc_top.sv:217. Clearing bit 5 stops both mailbox clocks. Because PREADY is a constant, every subsequent AHB/APB access to 0x4001_3000-0x4001_301C still completes with an OKAY response and no bus fault, but nothing is clocked: apb_sfr2's register update (apb_sfr.sv:339) is a pclk flop and never fires, and the apb_acr/apb_asr action pulses (mbox.sv:177, :237) are pclk flops and never fire, so no word is pushed and no word is popped. The status register read path is combinational, so it keeps returning the frozen pre-gate values - typically tx_free=1, rx_avail=0, tx_err=0, rx_err=0. The sender therefore polls a status register that permanently says 'ready, no error' while every message it writes is discarded.

**Evidence.**
```systemverilog
rtl/modules/amba/rtl/apb_sfr.sv:19-23 (the macro used by mbox.sv:105)
```
    `define apbs_common \
    assign apbx.pready = 1'b1; \
    assign apbx.pslverr = 1'b0; \
    assign apbrd = apbs.psel & apbs.penable & ~apbs.pwrite; \
    assign apbwr = apbs.psel & apbs.penable & apbs.pwrite
```
rtl/modules/soc_coresub/rtl/soc_coresub.sv:438-439 (both mailbox clocks gated by one software bit)
```
    logic aclkmbox; ICG icg_mbox_aclk ( .CK (aclk), .EN ( clkmboxgate ), .SE(cmsatpg), .CKG ( aclkmbox ));
    logic hclkmbox; ICG icg_mbox_hclk ( .CK (hclk), .EN ( clkmboxgate ), .SE(cmsatpg), .CKG ( hclkmbox ));
```
rtl/asic_top/rtl/soc_top.sv:576 (the gate source)
```
                               .clkmboxgate ( aclksubgate[5] ),
```
rtl/modules/sysctrl/rtl/sysctrl.sv:864 (a plain software control register)
```
    apb_cr #(.A('h60), .DW(ACKCNT),   .IV('hff)) sfr_aclkgr     (.cr(aclksubgate),.prdata32(),.*);
```
and the write-protect that would have covered it is an undriven net - rtl/asic_top/rtl/soc_top.sv:217 and :361
```
    logic               sfrlock;
...
    /*        input logic      */   .sfrlock     (sfrlock|'0     ),
```

**Attack scenario.** 1. Attacker code writes 0x4004_0060 clearing bit 5. There is no lock bit protecting this register (sysctrl's sfrlock is never driven), and the CGU clock-gate register is not covered by any coreuser or hauser check. 2. Both mailbox clocks stop. 3. The CM7's secure firmware continues its normal send loop: it reads 0x4001_3008, sees the frozen tx_free=1 and tx_err=0, writes a word to 0x4001_3000, and gets an OKAY response - the AHB-to-APB bridge completes because PREADY is a constant 1. The word is never registered and never reaches the Vex. 4. The Vex's secure task never receives the command; the CM7 never receives a reply and never sees an error bit, because the status register is frozen at 'idle, no error'. The result is a stealthy, unattributable cut of the inter-CPU trust channel: neither endpoint can distinguish it from a peer that is simply slow, and any firmware protocol that relies on the mailbox status register for liveness or error detection is defeated. Restoring the gate bit does not recover the lost words, so an attacker can also use it to delete a specific message from a sequence and desynchronise a positional protocol.

**Verification.** No independent verdict recorded for this entry.

---

<a id="bao-108"></a>

### BAO-108 — ReRAM ECC and controller error outputs are wired only to a status register — the boot read of all security configuration is consumed with no integrity check and no error path

**Severity: Low** | CWE-1261 Improper Handling of Single Event Upsets (uncorrectable NV error not acted upon) | Threat actor: T2 (physical access: laser/EM/glitch fault injection, or exploitation of retention loss). | Confidence: Medium

**Location:** `rtl/modules/rrc/rtl/rrc.sv:289`

**Description.** Both ReRAM macro wrappers export `ecc_err_o[2:0]` and `trc_err_o` (rrc.sv:999,1002,1085,1088). In the RRC these are OR-combined (rrc.sv:937,939) and then routed to exactly one place: bits of the read-only status register `rrcsr` (rrc.sv:289, `ahb_sr #(.A('h08), .DW(10)) sfr_rrcsr`). They are not sticky, they do not participate in `rrcint` (rrc.sv:291 `assign rrcint = |rrcfr;`, and `rrcfr` at rrc.sv:290 contains only the five access-error flags), they do not reach `rrcnmi` (rrc.sv:292), they do not gate `trc_dout_ready_done` (rrc.sv:491) and therefore do not prevent the faulted 256-bit word from being latched into `ahb_rd_buf` (rrc.sv:561) or into the boot-read image `brdatreg` (rrc.sv:156), and they do not stall or abort the boot FSM `brfsm` (rrc.sv:136-144), which advances purely on `trc_dout_ready_sdone`. Since the AHB response is hardwired OKAY (rrc.sv:583 `assign ahbarray.hresp = 2'h0;`), a faulted word is indistinguishable from a good one to the requesting master. This matters because `brdatreg` is not ordinary data — it is the entire security configuration, loaded once at boot and then used combinationally by the access-control logic for the rest of the power cycle: `brdatreg[20..23]` supply `user_code_cfg_boot0/boot1/fw0/fw1`, the code-region cross-stage read/write-disable matrix (rrc.sv:232-235, consumed at rrc.sv:731-757); `brdatreg[24..31]` supply the 256-bit `data_cfg_rd_dis`/`data_cfg_wr_dis`/`key_cfg_rd_dis`/`key_cfg_wr_dis` bitmaps (rrc.sv:616-619, consumed at rrc.sv:809-813); `brdatreg[axi_yadr][255:240]` supply the IFR write/read-disable bytes (rrc.sv:781-782). Every one of these is permissive-when-cleared. `brdatreg` is on `sysresetn`, so a corrupted image persists across every warm reset.

**Evidence.**
```systemverilog
rrc.sv:937  assign trc_err = trc_err_s0 | trc_err_s1;
rrc.sv:939  assign ecc_err = ecc_err_s0 | ecc_err_s1;
rrc.sv:289  assign rrcsr[9:0] = {ecc_err, trc_err, trc_info_lock_err, ip_user_cmd_i, trc_busy};
rrc.sv:290  assign rrcfr = {info_access_error_athclk, cfg_access_error_athclk, code_access_error_athclk, data_access_error_athclk, key_access_error_athclk};
rrc.sv:291  assign rrcint = |rrcfr;
rrc.sv:292  assign rrcnmi = rrcint & rrccr[15];
--- the faulted word is latched regardless ---
rrc.sv:156  `theregfull(clksys, sysresetn, brdatreg[bridx_org], '0) <= trc_dout_ready_sdone ? {trc_dout_s1[127:0],trc_dout_s0[127:0]} : brdatreg[bridx_org];
rrc.sv:561  `theregfull(clktop, coreresetn, ahb_rd_buf, '0) <= trc_dout_ready_done ? {trc_dout_s1[127:0],trc_dout_s0[127:0]} : ahb_rd_buf;
rrc.sv:583  assign ahbarray.hresp = 2'h0;
--- and it becomes the access-control policy ---
rrc.sv:232  assign user_code_cfg_boot0 = brdatreg[20][111:104];
rrc.sv:616  assign data_cfg_rd_dis = {brdatreg[25][127:0], brdatreg[24][127:0]};
rrc.sv:619  assign key_cfg_wr_dis = {brdatreg[31][127:0], brdatreg[30][127:0]};
rrc.sv:781  assign info_access_error_pre = (((brdatreg[axi_yadr][255:248] == PM_WRITE_DIS) | cm7sel&(!pri_op) | vexsel&(!vex_mm_reg) | scesel) & ahb_write_flag |
```

**Preconditions.** Physical access and fault-injection capability (laser, EM, voltage/clock glitch) timed to the boot read, or a device with natural ReRAM retention degradation. Requires no software privilege. Exploitation requires the injected error to be uncorrectable-but-still-returned rather than silently corrected — I could not determine the macro's correction strength because the ECC decoder (encoder_new_h.v / decoder_invless.v) lives in asic_top/lib/, which is not in this repository; ecc_err_o being 3 bits wide strongly suggests it distinguishes corrected from uncorrectable, and the RTL ignores all three bits equally.

**Attack scenario.** Attacker has physical access and a laser/EM fault-injection setup (T2), or exploits natural ReRAM retention loss on an aged part.
1. During the power-on boot read (brfsm states 1-3, which fetch brdatreg[0..31] over a bounded and observable number of cycles at 0x603D_x), the attacker injects a fault targeting the sense/ECC path for word index 26 or 27 (`data_cfg_wr_dis`) or 30/31 (`key_cfg_wr_dis`), or word 20-23 (`user_code_cfg_*`).
2. The macro asserts `ecc_err_o` (and possibly `trc_err_o`) for that beat. Nothing in the RRC reacts: `trc_dout_ready_sdone` still fires, rrc.sv:156 still latches the corrupted 256 bits into `brdatreg`, and `brfsm` still advances. `brdone` is set normally, the CPU boots normally, and the only trace is a non-sticky bit in a status register that nothing polls.
3. Bits that were 1 ("disabled") in `key_cfg_wr_dis` / `data_cfg_wr_dis` are now 0, so `cfg_wr_dis` (rrc.sv:812-813) no longer blocks writes to those CFG slots; or bits cleared in `user_code_cfg_fw1` (rrc.sv:752-757) remove the boot0/boot1/fw0 code-region protections against fw1. The attacker's unprivileged code then writes the previously-protected CFG lines or the boot code region.
4. Because `brdatreg` is reset only by `sysresetn`, the corrupted policy survives every `coreresetn` (software reset, watchdog reset), so the attacker has the rest of the power cycle to work with, and only needs the fault to land once.
The same gap applies on the read path for ordinary array accesses: an ECC-uncorrectable key or code word is returned to the bus as valid data with hresp = OKAY, so a fault-injection attack that perturbs a signature or a key during a secure-boot verification is not distinguishable from a legitimate read by any software check.

**Mitigation.** RTL fix: (a) add `ecc_err`/`trc_err` to `rrcfr` so they contribute to `rrcint`, and make them sticky per-transaction rather than combinational status; (b) qualify `trc_dout_ready_done` and the `brdatreg`/`ahb_rd_buf` load enables with the absence of an uncorrectable ECC error, so a faulted word is never latched; (c) return `hresp = 2'b01` (ERROR) on the AHB for an uncorrectable read instead of the hardwired `2'h0` at rrc.sv:583; (d) hold `brdone` low and refuse to release the array if any beat of the boot read reports an uncorrectable error, so the device fails closed rather than booting with a corrupted policy; (e) add a CRC or hash over brdatreg[20..31] checked after the boot read completes, and consider storing the permissive-when-zero policy bitmaps in inverted or dual-rail form so a 1->0 fault is detectable.
Firmware workaround on fabricated silicon: boot0 should read RRC_SFR_RRCSR at 0x40000008 immediately after boot and again after any array read of security-relevant data, and should independently re-read and cross-check the 0x603D_C000 CFG region against a firmware-held hash before trusting any access-control decision. This is only partial — rrcsr is not sticky, so an error that occurred during the boot read may already have cleared by the time firmware runs.

**Verification.** Verified as written; exploitability not fully established. The code claims are all accurate and I reproduced them. rrc.sv:937/939 OR the two macro halves; rrc.sv:289 `assign rrcsr[9:0] = {ecc_err, trc_err, trc_info_lock_err, ip_user_cmd_i, trc_busy};` is the only consumer — I grepped `ecc_err` across the module and rrc.sv:258, 939, 289, 999, 1085 are the complete set, so it truly reaches nothing else. rrc.sv:290 shows rrcfr contains only the five access-error flags, so rrcint (291) and rrcnmi (292) cannot see an ECC error. rrc.sv:156 latches `brdatreg[bridx_org]` and rrc.sv:561 latches `ahb_rd_buf` on `trc_dout_ready_sdone`/`trc_dout_ready_done` with no error qualifier, rrc.sv:136-144 advance brfsm purely on `trc_dout_ready_sdone`, and rrc.sv:583 hardwires `hresp = 2'h0`. The consumption of brdatreg as live policy (rrc.sv:232-235, 616-619, 781-782) is correct, and the permissive-when-cleared property is real. What I cannot substantiate is the exploit: the ECC decoder (decoder_invless.v / encoder_new_h.v, referenced from reram_inc.sv:76-77 under asic_top/lib/) is not in this repository, so whether ecc_err_o[2:0] ever signals an uncorrectable-but-still-returned word — as opposed to a corrected one — is unknown. trbcx1r32_daric_wrapper.sv:309/609/934 shows the wrapper only passes ecc_err_o straight through. The hardening gap is genuine; the attack is not demonstrated.

**Corrections applied by the verifier.** Downgraded from medium. This is a missing-defence-in-depth observation (no sticky error, no interrupt, no ERROR response, no fail-closed on boot read), not a demonstrated defect — the finder's own preconditions concede the ECC correction strength is unknown. Report it as hardening, not as an exploitable flaw.

---

<a id="bao-109"></a>

### BAO-109 — ReRAM code-region protection is disabled at reset: code_access_error is still gated by rrccr[12] (reset value 0) after the #eco16 ECO removed the equivalent gate from the other four checks

**Severity: Low** | CWE-1221 Incorrect Register Defaults or Module Parameters (security control defaults to disabled) | Threat actor: T1 for the software-reset path; T2 (glitch during early boot) for the more serious variant. | Confidence: High

**Location:** `rtl/modules/rrc/rtl/rrc.sv:778`

**Description.** An ECO annotated `#eco16` deliberately removed the `rrccr[n]` enable gate from four of the five RRC access checks: rrc.sv:719 (`//    assign key_access_error = key_access_error_pre & rrccr[10];`), rrc.sv:728 (`rrccr[11]`), rrc.sv:784 (`rrccr[14]`) and rrc.sv:824 (`rrccr[13]`) are all commented out and replaced with unconditional assignments. The code check was left gated: rrc.sv:778 still reads `assign code_access_error = code_access_error_pre & rrccr[12];` with the unconditional version commented out immediately below on line 779 — the exact inverse of the pattern applied to the other four. `rrccr` comes from `ahb_cr_ECO #(.A('h00), .DW(32))` (rrc.sv:274) whose IV parameter defaults to `32'h0` (rrc.sv:1144) and which resets on `coreresetn`. So from every reset until software writes 0x4000_0000, `code_access_error` is identically 0 and the entire code-region protection is off: the boot0/boot1/fw0/fw1 mutual read/write isolation matrix (`rrsub_code_dis`, rrc.sv:731-768) and the trustkey-linked code lock (`rrsub_code_dis_trustkey`, rrc.sv:761-763) — the only mechanisms in the design protecting the secure-boot code in ReRAM from being read or rewritten by a later boot stage — are both inert. The one mitigating factor is that `ahb_sfr2_ECO` force-sets bit 12 on every write (rrc.sv:1258 `? reg_wdata|32'h0000_1000 :`), so software cannot clear it once set without a reset; but `coreresetn` is assertable from software via the unlocked `sfr_rcurst1` at 0x4004_0084 (sysctrl.sv:872), and the RRC SFR window has no privilege filter, so nothing prevents a later stage from returning the chip to the unprotected state.

**Evidence.**
```systemverilog
rrc.sv:777  //#eco16
rrc.sv:778      assign code_access_error = code_access_error_pre & rrccr[12];
rrc.sv:779  //    assign code_access_error = code_access_error_pre;
--- contrast: the same ECO removed the gate everywhere else ---
rrc.sv:718  //#eco16
rrc.sv:719  //    assign key_access_error = key_access_error_pre & rrccr[10];
rrc.sv:720      assign key_access_error = key_access_error_pre;
rrc.sv:727  //#eco16
rrc.sv:728  //    assign data_access_error = data_access_error_pre & rrccr[11];
rrc.sv:729      assign data_access_error = data_access_error_pre;
rrc.sv:783  //#eco16
rrc.sv:784  //    assign info_access_error = info_access_error_pre & rrccr[14];
rrc.sv:785      assign info_access_error = info_access_error_pre;
rrc.sv:823  //#eco16
rrc.sv:824  //    assign cfg_access_error = cfg_access_error_pre & rrccr[13];
rrc.sv:825      assign cfg_access_error = cfg_access_error_pre;// & rrccr[13];
--- the reset value ---
rrc.sv:274      ahb_cr_ECO #(.A('h00), .DW(32))                 sfr_rrccr       (.cr(rrccr), .hrdata32(), .resetn(coreresetn), .sfrlock(1'b0), .*);
rrc.sv:1144       parameter IV=32'h0,
--- what is disabled ---
rrc.sv:765  assign rrsub_code_dis = boot0_code_dis & userid_c[0] |
rrc.sv:768                              fw1_code_dis & userid_c[3] | rrsub_code_dis_trustkey;
rrc.sv:770  assign code_access_error_inst = rrsub_code_dis_trustkey & ahb_read_flag & (cm7sel|vexsel) & inst_op & codesel;
```

**Preconditions.** Any reset, plus a way to execute or influence execution before the first write to RRC_SFR_RRCCR. Also note the protection only ever applies to masters with `cm7sel|vexsel` (rrc.sv:772), so it is independently absent for the BDMA/MDMA/uDMA regardless of rrccr[12] — see the separate coreuser_mux finding.

**Attack scenario.** 1. On every reset (power-on, watchdog, or a software write of 0x55aa to sysctrl `sfr_rcurst1` at 0x4004_0084, which is unlocked and reachable from the same unfiltered peripheral bus), `rrccr` clears to 32'h0 and `rrccr[12]` = 0.
2. Until boot code performs its first write to 0x4000_0000, `code_access_error` cannot assert. Any read or write from the CM7 or Vex to the ReRAM code region (`codesel = ( haddr_reg[31:12] < PM_CODE_REGION_BORDER )`, i.e. all of 0x6000_0000-0x603D_9FFF) succeeds regardless of the boot0/boot1/fw0/fw1 policy in `user_code_cfg_*` and regardless of whether the required trustkey has been established.
3. This is a fail-open reset value on the root of the secure-boot chain: the window is bounded only by a software convention ("boot0 must write rrccr early") that the hardware does not enforce and that no lock bit backs. Any glitch, exception, or alternate entry point that reaches attacker-influenced code before that write — for example a fault-injected branch during the first instructions after reset, or any path where the reset vector `cm7cfg_iv` (soc_coresub.sv:263-266, an 8-bit ReRAM field) has been perturbed — executes with ReRAM code-region protection entirely absent and can rewrite the boot0 image.
4. The asymmetry with the four sibling checks is strong evidence this is an oversight in the ECO rather than an intended design choice: the ECO author clearly intended these enables to go away, and the code check was missed.

**Mitigation.** RTL fix (preferred): apply the same #eco16 treatment to line 778 as to lines 719/728/784/824 — `assign code_access_error = code_access_error_pre;` — removing the software-controlled enable entirely. If the enable must be retained, change the `sfr_rrccr` instantiation at rrc.sv:274 to pass a non-zero IV with bit 12 set (`ahb_cr_ECO #(.A('h00), .DW(32), .IV(32'h0000_1000))`) so the control comes up enabled, matching the force-set behaviour already present on the write path at rrc.sv:1258. Independently, remove the `(cm7sel|vexsel)` qualifier from `code_access_error_data` (rrc.sv:772) so the code region is protected against all masters.
Firmware workaround on fabricated silicon: boot0 must write RRC_SFR_RRCCR at 0x4000_0000 as one of its very first instructions, before any branch that could be influenced by external data, and must verify the read-back shows bit 12 set. Because the write path ORs in 0x0000_1000, any write suffices. Boot code should also verify bit 12 is still set after every stage transition, and should treat a cleared bit 12 as a tamper indication. This does not close the reset-to-first-write window, which cannot be closed from software.

**Verification.** Independently confirmed by a second reviewer. The RTL evidence is exact. rrc.sv:777-779 read `//#eco16` / `assign code_access_error = code_access_error_pre & rrccr[12];` / `//    assign code_access_error = code_access_error_pre;` — the inverse of the pattern at rrc.sv:718-720, 727-729, 783-785 and 823-825, which I read and confirmed are all commented-out-gate/uncommented-ungated. rrc.sv:274 passes no IV to `ahb_cr_ECO`, whose declaration at rrc.sv:1144 is `parameter IV=32'h0`, so rrccr[12]=0 out of coreresetn and code_access_error is identically 0 until firmware writes 0x4000_0000. The mitigation the finder correctly identified is real: ahb_sfr2_ECO at rrc.sv:1258 `? reg_wdata|32'h0000_1000 :` force-sets bit 12 on any write, so it cannot be cleared by software once set. However I checked the claimed software attack path and it does not work.

**Corrections applied by the verifier.** The attack scenario is wrong. The finder claims a later stage can write 0x55aa to sysctrl sfr_rcurst1 (sysctrl.sv:872) to return the chip to the unprotected state. That reset is not RRC-local: sysctrl.sv:798-804 feeds `~corereset_sw` into `coreresetgen`, whose output `coreresetn` (sysctrl.sv:811) also resets both CPUs — soc_coresub.sv:308 `coreresetn_cm7 = cmsatpg ? 1'b1 : coreresetn & cm7cfg_en` and soc_coresub.sv:311 `resetn_vex = cmsatpg ? 1'b1 : coreresetn & vexcfg_en`. So a software core reset restarts execution at boot0, which re-enables bit 12; the attacker cannot survive it. What remains, and is real, is a fail-open reset default on a security control: the code-region isolation matrix and the trustkey code lock are off from every reset until boot software happens to write the register, and nothing in hardware enforces that it ever does. Downgraded from medium to low: exploitation requires either fault injection inside the reset-to-first-write window or firmware that never writes RRC_SFR_RRCCR. Also note the finder's own aside is correct and independently important — rrc.sv:772 qualifies `code_access_error_data` with `(cm7sel|vexsel)`, so the code region is unprotected against unrecognised masters regardless of rrccr[12].

---

<a id="bao-110"></a>

### BAO-110 — The program-only (`wrmode_d`) attribute of a ReRAM data slot is evaluated from the previous transaction's ACRAM descriptor, letting an attacker turn a one-way slot into a full overwrite

**Severity: Low**

**Location:** `rtl/modules/rrc/rtl/rrc.sv:535`

*Surfaced by the independent verifier, not the original domain reviewer.*

**Description.** `prog_only_data_write` selects between the OR-only program path (`axi_din = ahb_rd_buf | ahb_wr_buf`, rrc.sv:869) and the ordinary full-overwrite buffer-load path (rrcfsm 0->2 at rrc.sv:848). It is evaluated combinationally during the AHB address phase, from `ahbarray.htrans`/`ahbarray.haddr` (rrc.sv:535, 537). But its `wrmode_d` input comes from the ACRAM output: rrc.sv:705 `assign wrmode_d = datacfg[24];` and rrc.sv:688 `assign datacfg = haddr_reg[5] ? acram_rdata[63:32] : acram_rdata[31:0];`. Both `acram_rdata` and `haddr_reg` still belong to the *previous* transfer at that moment — the ACRAM address for the current transfer is only presented in that same cycle (rrc.sv:394 `ahb_read_acram ? ahbarray.haddr[16:6]`) and its data is not available until the next cycle, and `haddr_reg` is only updated at the end of the address phase (rrc.sv:541). Every other access-control decision reads correctly because it is driven from the registered `haddr_reg`/`ahb_write_flag` one cycle later; `wrmode_d` is the sole check evaluated a cycle early against a stale descriptor. The result is that the program-only (bits can only be set) attribute of data slot N is decided by the descriptor of whatever slot was touched in transaction N-1, in both directions.

**Evidence.**
```systemverilog
rrc.sv:535     assign prog_only_data_write = ahb_array_trans & ahbarray.hwrite & ahbarray.hsel & (ahbarray.haddr[23:16] == 8'h3E) & wrmode_d & rrccr[1]; // 3E_xxxx Data Slots Region
rrc.sv:537     assign ahb_array_trans = clken & ahbarray.htrans[1] & brdone & ahbarray.hready;
rrc.sv:688     assign datacfg = haddr_reg[5] ? acram_rdata[63:32] : acram_rdata[31:0];
rrc.sv:705     assign wrmode_d = datacfg[24];
rrc.sv:394                             ahb_read_acram ? ahbarray.haddr[16:6] :
rrc.sv:541     `theregfull(clktop, coreresetn, haddr_reg, '0) <= ahb_array_trans & ahbarray.hsel ? ahbarray.haddr :
rrc.sv:869                         prog_only_data_write_reg ? (ahb_rd_buf | ahb_wr_buf) : ahb_wr_buf;
rrc.sv:848             ( rrcfsm == 0 ) & ahb_array_write  & !rrccr[1] ? 2 :                                                // rram wr_buf load
```

**Attack scenario.** Attacker has legitimate write permission to a data slot but the slot is marked program-only (`wrmode_d`=1) so that its bits are intended to be one-way — the natural use for a lifecycle/feature/attempt-counter field held in a data slot.
1. Issue any access to a data slot whose descriptor has bit 24 clear (or simply one whose descriptor half selected by the previous `haddr_reg[5]` has bit 24 clear). `acram_rdata` now holds that descriptor.
2. In the immediately following transfer, write to the program-only slot. At the address phase `wrmode_d` still reflects step 1's descriptor, so `prog_only_data_write` is 0, `ahb_array_write` (rrc.sv:539) is 1, and rrcfsm takes the ordinary 0->2 buffer-load path.
3. Set rrccr[1] and issue PM_RRAM_WRITE. `axi_din = ahb_wr_buf` (rrc.sv:869, the prog_only_data_write_reg term is 0), so the slot is fully overwritten rather than OR-merged, clearing bits that the program-only attribute was meant to make irreversible.
The converse also occurs: a normal write to a `wrmode_d`=0 slot preceded by a `wrmode_d`=1 descriptor is silently converted into an OR-merge, corrupting data. Fix: derive `prog_only_data_write` from the registered descriptor one cycle later, alongside the other checks, rather than from the address phase.

**Verification.** No independent verdict recorded for this entry.

---

<a id="bao-111"></a>

### BAO-111 — Debug UART is unconditionally enabled at reset, unlocked, and bonded to a dedicated pad with no lifecycle gate - an always-available off-chip exfiltration channel for any bus master

**Severity: Low** | CWE-1191 On-Chip Debug and Test Interface With Improper Access Control | Threat actor: T1 (any software or bus master that can reach 0x4004_2000) to transmit; T2/T3 (physical probe on the PAD_DUART pin) to receive | Confidence: High

**Location:** `rtl/modules/core/rtl/duart.sv:45`

**Description.** `duart` is a transmit-only serial port whose control register `sfr_cr` (the TX enable) has reset value `.IV('1)` - i.e. transmission is enabled out of reset with no software action - and whose SFR lock is hardwired to zero (`assign sfrlock = '0;`), so the enable can never be latched off. Its `txd` output goes straight to `dbgtxd` (soc_top.sv:527) and from there to a dedicated always-driven output pad, `padcell_o #(.H('0)) u_duart ( .pad( PAD_DUART ), ... .po( dbgtxd ), ...)`, with no `cmsuser` / `cmstest` / `devmode` qualification anywhere in the chain - unlike the Vex JTAG (gated by `vexcfg_dev`, vexsys.sv:347-349), the CM7 SWD (gated by `cm7cfg_dev`, cm7sys.sv:855, 865) and the IPT/rbist/ReRAM TAPs (gated by `cmstest`/`cmsatpg` in pad_frame_arm.sv:232-250). On a secure chip whose entire debug surface is otherwise lifecycle-gated, this is an unmanaged permanent egress path: any code or DMA-reachable write that lands a byte at 0x4004_2000 emits it off-chip at a rate the attacker also controls via the unlocked baud register `sfr_etuc` at 0x4004_200C.

**Evidence.**
```systemverilog
rtl/modules/core/rtl/duart.sv:29-30
    logic apbrd, apbwr, sfrlock;
    assign sfrlock = '0;

rtl/modules/core/rtl/duart.sv:44-47
    apb_cr #(.A('h00), .DW(8 ),    .IV('0))   sfr_txd      (.cr(sfrtxd),   .prdata32(),.*);
    apb_cr #(.A('h04), .DW(1),     .IV('1))   sfr_cr       (.cr(sfrcr),    .prdata32(),.*);
    apb_sr #(.A('h08), .DW(1)             )   sfr_sr       (.sr(sfrsr),    .prdata32(),.*);
    apb_cr #(.A('h0C), .DW(16),   .IV(INITETU))  sfr_etuc     (.cr(sfretu),   .prdata32(),.*);

rtl/modules/core/rtl/duart.sv:55, 106
    assign sfrcr_txen = sfrcr;
...
    assign txd = txstreamdata[0];

rtl/asic_top/rtl/soc_top.sv:521-528 (no enable/lifecycle input at all)
    duart duart(
            .clk    (pclk),
            .sclk   (clksys),
            .resetn (coreresetn),
            .apbs   (apbsys[2]),
            .apbx   (apbsys[2]),
            .txd    (dbgtxd)
        );

rtl/asic_top/rtl/pad_frame_arm.sv:221 (dedicated pad, unconditional)
    padcell_o  #(.H('0))  u_duart  ( .pad( PAD_DUART ), .thecfg(padcfg_dev), .po( dbgtxd ), .rtosns(rtosnstest), .cmsatpg(cmsatpg));
```

**Preconditions.** Attacker can write 0x4004_2000 (data) - the duart is `apbsys[2]` in the apb1-system block at 0x4004_0000-0x4004_FFFF, reachable from the CM7 AHB-P, the Vex AHB-P, the MDMA and the BDMA AHB master with no privilege check anywhere on that path. Receiving requires only a probe on the dedicated PAD_DUART pin.

**Attack scenario.** 1. Attacker obtains any write primitive that reaches 0x4004_2000 - unprivileged code on either CPU, an MDMA channel programmed per finding 2, or the BIO/BDMA AHB master (whose hauser is 0 and satisfies no check in the design).
2. He does not need to enable anything: `sfr_cr` resets to 1 and cannot be locked off, so the transmitter is live from `coreresetn` onward. He optionally writes `sfr_etuc` at 0x4004_200C to pick a convenient baud rate.
3. He streams any secret he has managed to read - ReRAM key-slot bytes obtained via finding 1, CM7 DTCM contents obtained via finding 2, SCE crypto-RAM contents - one byte per write to 0x4004_2000. `txstart_pclk` fires on every write to offset 0 while `~txbusy` (duart.sv:59), and the byte is shifted out of PAD_DUART.
4. He captures the bits with a probe or logic analyser on PAD_DUART. Unlike SWD, Vex JTAG and the IPT/rbist/ReRAM TAPs, this path is not conditioned on `cm7cfg_dev`, `vexcfg_dev`, `cmstest`, `cmsatpg` or `cmsuser`, so it works in a fully locked-down production part.
5. The channel is equally useful in reverse as a covert timing/liveness oracle: since `sfr_sr` reports `txbusy` and there is no lock, a low-privilege thread can use it to signal a co-operating physical attacker exactly when to apply a glitch.

**Mitigation.** RTL fix: qualify the pad output with the lifecycle state, e.g. `assign dbgtxd_gated = (cmstest | cmsatpg | cm7cfg_dev | vexcfg_dev) ? dbgtxd : 1'b0;` before `padcell_o`, matching how every other debug pin is handled in pad_frame_arm.sv:232-250; change `sfr_cr`'s reset value to 0 so transmission is opt-in; and drive `duart.sfrlock` from a set-only lock bit so boot code can permanently disable the port. Add a privilege/coreuser qualification on the apb1-system window so unprivileged code and DMA masters cannot reach it at all.
Silicon workaround: on already-fabricated parts the pad cannot be gated, so treat PAD_DUART as a permanently exposed output: (a) at the board level, do not route PAD_DUART to an accessible test point or connector on production hardware, and consider leaving it unbonded/covered; (b) boot code should ensure no trusted routine ever writes secret-derived bytes to 0x4004_2000, and should prefer to keep the sysctrl clock gate for the apb1-system duart clock off in production if the clock tree permits it; (c) restrict which masters can reach 0x4004_0000 (see the MDMA mitigation). None of these removes the channel for an attacker who already has code execution - the port is fundamentally unmanaged in this silicon.

**Verification.** Verified as written; exploitability not fully established. duart.sv:29-30, 44-47, 55 and 106 verified verbatim; soc_top.sv:521-528 verified — the duart instance takes clk/sclk/resetn/apbs/apbx/txd only, no enable or lifecycle input; pad_frame_arm.sv:221 verified verbatim. duart is apbsys[2]; apbsys is a 16-way apb_mux (soc_top.sv:671) off a PAW(16) bridge, so 0x4004_2000 is right. `txstart_pclk <= apbwr & sfrcr_txen & (apbs.paddr == '0) & ~txbusy` (duart.sv:59) confirms a single write to offset 0 shifts a byte out. I looked for a compensating control and found none in the pad chain — but I also confirmed there is no receive path, so this is purely an egress channel and cannot be used to inject.

**Corrections applied by the verifier.** All quoted RTL is verbatim correct and I confirmed the pad is unconditionally driven (padcell_arm.sv:227-228 inside padcell_o hardwires `assign pio.pu = '1; assign pio.oe = '1;`, and `thecfg`/padcfg_dev carries only schmsel/anamode/slewslow/drvsel — drive characteristics, not an enable). But the severity is overstated. The channel is transmit-only and requires code execution to use; an attacker who already has an arbitrary write primitive on this SoC also has GPIO, the SPI master, USB and the QFC pads as egress. The incremental risk over an already-compromised part is small, and 'covert timing/liveness oracle to cue a glitch' (step 5) is a stretch given the attacker already has code execution and a clock. What is genuinely reportable, and should be the entire finding, is the inconsistency: every other debug pin in pad_frame_arm.sv is lifecycle-qualified (u_swdio/u_swdck via cm7cfg_dev inside cm7sys.sv:854/865 `.SWDITMS(swdio_pi & cm7cfg_dev)` and `.DEVICEEN(cm7cfg_dev)` — I verified this gate is real; the JTAG/IPT/rbist TAPs via cmstest/cmsatpg at pad_frame_arm.sv:233-250), whereas PAD_DUART is not, and duart.sv:45 `sfr_cr` resets to '1 with duart.sv:30 `assign sfrlock = '0;` so it can be neither disabled at reset nor locked off. That is a defence-in-depth gap, not an attack.

---

<a id="bao-112"></a>

### BAO-112 — mcounteren and scounteren are not implemented, so User mode has unrestricted access to the cycle-accurate cycle and instret counters

**Severity: Low** | CWE-1300 Improper Protection of Physical Side Channels (missing control over a fine-grained timing source available to lower privilege) | Threat actor: T1 | Confidence: High

**Location:** `VexRiscv/VexRiscv_CramSoC.v:6266`

**Description.** The CsrPlugin implements the user-level read-only counters `cycle` (0xC00), `cycleh` (0xC80), `instret` (0xC02) and `instreth` (0xC82) and unconditionally clears `execute_CsrPlugin_illegalAccess` for them on any read (6266-6285). It does NOT implement `mcounteren` (0x306) or `scounteren` (0x106) — I enumerated every CSR decode in the design (VexRiscv_CramSoC.v:8945-9053, 37 entries) and neither address appears. The generic privilege gate at 7467 does not help: 0xC00[9:8] == 2'b00, so `CsrPlugin_privilege (2'b00) < 2'b00` is false and U-mode access is allowed. Per the RISC-V privileged spec, when mcounteren/scounteren are not implemented they read as zero and an attempt to read a hpm/cycle/instret counter from a lower privilege must raise an illegal-instruction exception. Here there is no mechanism at all — hardware or software — by which M-mode or S-mode can deny an unprivileged task a cycle-exact, free-running timer and a retired-instruction counter. On a chip whose stated assets include SCE keys and whose CPU shares a 16 KB 4-way instruction cache and a 16 KB 4-way data cache (GenCramSoC.scala:95-121) with the privileged code that touches those keys, this is the single primitive that makes microarchitectural and timing side-channel attacks practical rather than theoretical.

**Evidence.**
```systemverilog
VexRiscv/VexRiscv_CramSoC.v:6266-6285 (cycle/cycleh/instret/instreth allowed unconditionally on read)
      if(execute_CsrPlugin_csr_3072) begin
        if(execute_CSR_READ_OPCODE) begin
          execute_CsrPlugin_illegalAccess = 1'b0;
        end
      end
      if(execute_CsrPlugin_csr_3200) begin
        if(execute_CSR_READ_OPCODE) begin
          execute_CsrPlugin_illegalAccess = 1'b0;
        end
      end
      if(execute_CsrPlugin_csr_3074) begin
        if(execute_CSR_READ_OPCODE) begin
          execute_CsrPlugin_illegalAccess = 1'b0;
        end
      end
      if(execute_CsrPlugin_csr_3202) begin
        if(execute_CSR_READ_OPCODE) begin
          execute_CsrPlugin_illegalAccess = 1'b0;
        end
      end

VexRiscv/VexRiscv_CramSoC.v:9005-9014 (the CSR numbers, confirming they are the user-mode 0xC00 block)
        execute_CsrPlugin_csr_3072 <= (decode_INSTRUCTION[31 : 20] == 12'hc00);
        execute_CsrPlugin_csr_3200 <= (decode_INSTRUCTION[31 : 20] == 12'hc80);
        execute_CsrPlugin_csr_3074 <= (decode_INSTRUCTION[31 : 20] == 12'hc02);
        execute_CsrPlugin_csr_3202 <= (decode_INSTRUCTION[31 : 20] == 12'hc82);

VexRiscv/VexRiscv_CramSoC.v:7467 (the generic gate is a no-op for 0xC00: privilege 2'b00 < 2'b00 is false)
  assign when_CsrPlugin_l1625 = (CsrPlugin_privilege < execute_CsrPlugin_csrAddress[9 : 8]);

Absent from the complete CSR decode list at 8945-9053: 12'h306 (mcounteren) and 12'h106 (scounteren). Absent from the plugin config: any counter-enable option (GenCramSoC.scala:161-167).
```

**Preconditions.** Unprivileged code execution on the Vex. No physical access required for the pure-timing variants; a T2 attacker additionally gains a cycle-exact glitch trigger.

**Attack scenario.** 1. Attacker runs an ordinary unprivileged (U-mode) task on the Vex. 2. Attacker reads `cycle`/`cycleh` with `rdcycle`/`rdcycleh` — no trap, no mediation, single-cycle granularity. 3. Attacker uses it to (a) time an ecall into the S/M-mode crypto service and recover data-dependent branch or loop-count behaviour in the software AES/RSA glue; (b) mount a PRIME+PROBE against the shared 16 KB 4-way D-cache to recover the access pattern of privileged code, including S-box or table indices in any software crypto and the addresses of ReRAM key-slot fetches (ReRAM at 0x6000_0000 is NOT in the MmuPlugin ioRange (GenCramSoC.scala:172-181, which covers only 0x4/0x5/0xA-0xF), so ReRAM key-slot reads are cached and therefore observable through cache-timing); (c) time the SCE's HMAC compare that drives the ReRAM `truststate` unlock bits and detect early-exit behaviour; (d) build a precise trigger for a clock/voltage glitch by counting cycles from a known synchronisation point. 4. `instret` additionally gives the attacker a noise-free instruction count, which turns the timing channel from statistical into near-deterministic.

**Mitigation.** RTL (respin): add `mcounteren` (0x306) and `scounteren` (0x106) to the CsrPlugin CSR map and extend the illegalAccess logic so that a read of 0xC00/0xC02/0xC80/0xC82 from privilege < M is illegal unless the corresponding mcounteren bit is set (and from U unless scounteren is also set), which is what the privileged spec requires when those registers are absent. Software workaround on fabricated silicon: the counters cannot be disabled, so the mitigation must be structural — (a) never run untrusted code in the same address space or on the same core as key-handling code; (b) make all key-dependent code in the Vex's M/S-mode firmware constant-time and constant-cache-footprint (no key-indexed table lookups, no key-dependent branches); (c) prefer the SCE hardware engines over software crypto on the Vex for any operation on a live key; (d) flush both caches on every privilege transition out of key-handling code. Note that the AesZkn `aes32*` instructions are constant-time (dedicated ROM, `en` tied 1'b1, fixed one-cycle latency, VexRiscv_CramSoC.v:2839-2847) and so are a safe primitive against this timing channel, though not against power/EM.

**Verification.** Independently confirmed by a second reviewer. Verified directly. VexRiscv_CramSoC.v:6266-6285 contains the four blocks `if(execute_CsrPlugin_csr_3072/3200/3074/3202) if(execute_CSR_READ_OPCODE) execute_CsrPlugin_illegalAccess = 1'b0;` exactly as quoted, and 9005-9014 confirms those are 12'hc00/c80/c02/c82. My independent enumeration of every `12'h...` literal in the netlist contains neither 12'h306 (mcounteren) nor 12'h106 (scounteren), and `grep -c "12'h306\|12'h106"` returns 0. The gate at 7466 is a no-op for the 0xC00 block since `2'b00 < 2'b00` is false. I also confirmed the supporting claim about cacheability: VexRiscv_CramSoC.v:6801 shows `DBusCachedPlugin_mmuBus_rsp_isIoAccess` matches only physical addr[31:28] in {4,5,A,B,C,D,E,F}, so ReRAM at 0x6xxx_xxxx — including the key window 0x603F_xxxx — is cacheable in the 16 KB D-cache and therefore observable by cache timing. The AesZkn constant-time note also checks out (VexRiscv_CramSoC.v:2839-2847, ROM `en` tied 1'b1, fixed latency).

**Corrections applied by the verifier.** Severity is overstated. Absent counter-enable CSRs is common in embedded RISC-V cores and, per the spec, when mcounteren is not implemented the *machine-mode* view is simply that the counters are always enabled — this is a hardening gap, not a defect. More importantly it is largely subsumed: on this core untrusted code sharing the CPU with key-handling code already has unrestricted physical access with no PMP (finding #4), so `rdcycle` is not the marginal primitive that makes attacks practical. Downgrading medium -> low. The finding is still worth reporting as a hardening recommendation for a respin.

---

<a id="bao-113"></a>

### BAO-113 — healthtest_err is not qualified by healthtest_en, so at the reset configuration the flag and the SoC error counter fire continuously on perfectly healthy data, while setting the threshold without the enable makes the test permanently silent

**Severity: Info**

**Location:** `rtl/modules/crypto_trng/rtl/healthtest.v:38`

*Surfaced by the independent verifier, not the original domain reviewer.*

**Description.** healthtest.v:34 gates the repetition counter on healthtest_en, but lines 38-39, which produce the error output, do not reference healthtest_en at all. That creates two opposite failure modes, both of which destroy the only software-visible health signal the design offers. (1) With the test disabled -- the reset state, since cr_hlthtest_en and cr_healthtest_len both live in cr_postproc, an apb_cr at 0x08 with IV='0 (trng.sv:110, apb_sfr.sv:81/339) -- healthtest_cnt is pinned to 0 by line 34, and the error condition at line 38 evaluates (healthtest_cnt >= healthtest_length) as 0 >= 0, permanently true. healthtest_err therefore asserts on every pair of equal consecutive bits, i.e. about half the samples, on a perfectly healthy source. trng.sv:268-271 counts the rising edges into the 12-bit sr_hlthtest_errcnt and asserts hlthtest_errof (and hence fr[2], trng.sv:124, the only health-related flag the SoC exposes) once it saturates -- which on a healthy source happens within roughly sixteen thousand samples of every run left at the reset configuration. (2) Conversely, if firmware writes a non-zero cr_healthtest_len but forgets cr_hlthtest_en, healthtest_cnt stays pinned at 0, 0 >= healthtest_length is false, and healthtest_err can never assert -- the test is silently absent while the register read-back shows a plausible threshold. Combined with the separate finding that healthtest_err gates nothing in the datapath, this means the software-polling mitigation is a false alarm generator in one configuration and a no-op in the other.

**Evidence.**
```systemverilog
rtl/modules/crypto_trng/rtl/healthtest.v:34-39 (line 34 is gated by healthtest_en; lines 38-39 are not):
    assign healthtest_cnt_pre = (~healthtest_en) ? 6'h0 : 
	                    (digi_data_vld&(digi_data_out==digi_data_save)&(healthtest_cnt< healthtest_length))? healthtest_cnt+1'b1:
		    (digi_data_vld&(digi_data_out!=digi_data_save))? 6'h0 :healthtest_cnt;

    assign healthtest_err_pre = (digi_data_vld&(digi_data_out==digi_data_save)&(healthtest_cnt>=healthtest_length))? 1'b1:
	                    (digi_data_vld&(digi_data_out!=digi_data_save))? 1'b0 :healthtest_err;   

rtl/modules/crypto_top/rtl/trng.sv:110 (cr_postproc has no IV override, so cr_hlthtest_en=0 and cr_healthtest_len=0 at reset):
    apb_cr #(.A('h08), .DW(17) )      sfr_pp          (.cr(cr_postproc), .prdata32(),.*);

rtl/modules/amba/rtl/apb_sfr.sv:81,339 (the default and the reset that applies it):
      parameter IV=32'h0,
        `theregfull( pclk, resetn, sfrdatarr[i], IV ) <= ( sfrsel[i] & apbwr ) ? apbslave.pwdata : sfrdatarr[i];

rtl/modules/crypto_top/rtl/trng.sv:124,268-271 (the spurious errors are what drives the SoC's only health flag):
    assign fr[2] = hlthtest_errof;
    `theregrn( sr_hlthtest_errreg ) <= sr_hlthtest_err;
    assign sr_hlthtest_errrise = ( sr_hlthtest_err && ~sr_hlthtest_errreg );
    `theregrn( sr_hlthtest_errcnt ) <= ar_start ? '0 : sr_hlthtest_errcnt + sr_hlthtest_errrise;
    `theregrn( hlthtest_errof ) <= ( sr_hlthtest_errcnt == '1);
```

**Attack scenario.** This is primarily a correctness defect that neutralizes the mitigation, and an attacker benefits from it passively. Firmware written against the register map enables the oscillators via cr_src and issues ar_start without writing cr_hlthtest_en (the reset default). sr_hlthtest_errcnt immediately begins climbing on healthy entropy and fr[2] asserts, so the driver author concludes the health signal is unusable and stops checking it -- or masks fr[2] permanently. Later, when a T2 attacker actually stalls the noise source (EM/clock/thermal injection on the RNG_CELL rings), the one indicator that would have distinguished a live source from a dead one has already been classified as noise and is ignored, and since healthtest_err gates nothing in the datapath (rng_top.v:52, trng.sv:357) the chip keys from a dead source with no alarm at any level. The mirror-image case is worse for a careful integrator: firmware that writes cr_healthtest_len=32 but leaves cr_hlthtest_en clear reads back a register that looks correctly configured while healthtest_err is provably unreachable.

**Verification.** No independent verdict recorded for this entry.

---

<a id="bao-114"></a>

### BAO-114 — BIST read-data port is driven with live functional RAM read data at all times, not only when BIST is enabled

**Severity: Info** | CWE-1272 Sensitive Information Uncleared Before Debug/Power State Transition | Threat actor: T2 (physical/fault injection), amplifying Finding 1 and Finding 2 | Confidence: High

**Location:** `rtl/modules/bio_bdma/rtl/ram_1rw_s.sv:140`

**Description.** In `rbspmux`, every control input to the RAM macro is multiplexed on `cmsbist` (lines 128-132: `undft_cen = cmsbist ? rbs.ramcen : cen`, etc.), but the read-data *output* back to the BIST interface is not. Line 140 unconditionally exports whatever the macro just read to `rbs.ramrdata`, with the only mux being the ATPG placeholder. This means that during entirely normal USER-mode operation — SCE key scheduling, HMAC key-store fetches, AES round-key reads, ACRAM descriptor lookups — every word read from every RAM macro in the SoC is continuously presented on the `rbif` bus that fans out to `rbist_wrp` (soc_top.sv:990-1008) and from there into the JTAG-attached `rbist` core. The correct structure, matching lines 128-132, would be `assign rbs.ramrdata = cmsbist ? rb_q : '0;`. As written, the secret is already inside the BIST/repair logic before any mode check is made, so the security of the crypto RAM contents depends entirely on the closed-source BIST core never capturing or shifting out data it was not asked for, and on every one of the eight AND-gates in pad_frame_arm.sv:243-246 holding — there is no defence in depth.

**Evidence.**
```systemverilog
rtl/modules/bio_bdma/rtl/ram_1rw_s.sv:128-132  (control IS gated on cmsbist)
    assign rb_cen  = cmsatpg ? '1 : undft_cen  ; assign undft_cen  = cmsbist ? rbs.ramcen   : cen  ;
    assign rb_gwen = cmsatpg ? '1 : undft_gwen ; assign undft_gwen = cmsbist ? rbs.ramgwen  : gwen ;
    assign rb_wen  = cmsatpg ? '1 : undft_wen  ; assign undft_wen  = cmsbist ? rbs.ramwen   : wen  ;
    assign rb_a    = cmsatpg ? '1 : undft_a    ; assign undft_a    = cmsbist ? rbs.ramaddr  : a    ;
    assign rb_d    = cmsatpg ? '1 : undft_d    ; assign undft_d    = cmsbist ? rbs.ramwdata : d    ;

rtl/modules/bio_bdma/rtl/ram_1rw_s.sv:139-140  (read data is NOT gated)
    assign q            = cmsatpg ? undft_q : rb_q;
    assign rbs.ramrdata = cmsatpg ? undft_q : rb_q;

rtl/modules/crypto_top/rtl/cryptoram.sv:146-149  (this mux sits in front of the SCE key RAM)
    rbspmux #(.AW(AW),.DW(DW0))rbmux(
         .cmsatpg,
         .cmsbist,
         .rbs         (rbs),
```

**Preconditions.** Requires a fault or partial enable on the cmstest/cmsbist path, or a BIST core that samples ramrdata outside its enabled window. On its own this is an information-flow defect rather than a directly exploitable path; it removes the second layer of defence that lines 128-132 provide on the control side.

**Attack scenario.** An attacker who obtains any partial or transient enable of the BIST TAP — a laser or EM fault on the single `cmstest & jtagtrst` AND-gate at pad_frame_arm.sv:244, a glitch on the `cmstestreg` flop in cms.sv:157, or a scan-shift of the BIST core's own capture registers during ATPG — observes crypto-RAM read data that the design intended to be visible only in BIST mode, because line 140 has been feeding it into the BIST core continuously. Concretely: firmware performs an HMAC over a ReRAM key slot; the SCE reads AKEY/SKEY words out of sce_sceram_10k; each of those words appears on rbif_sce_sceram_10k.ramrdata in the same cycle. A single successful glitch on the TAP-release gate at the right moment captures a live key word, where a properly gated design would have required the attacker to also win control of address and enable.

**Mitigation.** RTL one-liner: `assign rbs.ramrdata = cmsatpg ? undft_q : (cmsbist ? rb_q : '0);` — mirror the cmsbist gating already applied to cen/gwen/wen/a/d. Apply the same to `rbs.ramrdatab` in the dual-port variant `rbdpmux`. Silicon workaround: none — this is a pure combinational path inside every RAM wrapper with no software-visible control.

**Verification.** Verified as written; exploitability not fully established. The quoted lines are verbatim correct: ram_1rw_s.sv:128-132 gate cen/gwen/wen/a/d on cmsbist, while :139-140 (`assign q = cmsatpg ? undft_q : rb_q; assign rbs.ramrdata = cmsatpg ? undft_q : rb_q;`) do not gate the read-data return. cryptoram.sv:146-149 does put this mux in front of the SCE RAMs. The asymmetry is real and the one-line fix is correct. One point in the finder's favour that they did not make: clkbist[0:5] is not gated by cmsbist either (sysctrl.sv:373-378), so the BIST core is clocked while functional read data is on its inputs. Countervailing: in ATPG the RAMs are properly isolated (rb_cen forced '1, rb_clk forced 0 at ram_1rw_s.sv:126-128, and rbs.ramrdata is replaced by the undft_q placeholder), so the scan-shift variant of the attack does not work. There is no demonstrated leak — the rbif bus terminates inside the same die at a controller that is idle. This is a legitimate 'defence in depth is missing' observation, not a vulnerability.

**Corrections applied by the verifier.** Severity lowered from medium to low. The finder's own preconditions concede this is not directly exploitable, and the proposed amplifier requires a successful single-bit fault on a specific gate. The suggested fix for the dual-port case names `rbdpmux`, which is not defined anywhere in this repo (only instantiated: vexram.sv:134, qfc.sv:536, udc.sv:509) — it is in a redacted file, so the same defect cannot be confirmed there.

---

<a id="bao-115"></a>

### BAO-115 — RAM-trim write pulse crosses clock domains through a synchroniser declared on the wrong launch clock

**Severity: Info** | CWE-1298 Hardware Logic Contains Race Conditions | Threat actor: T2 (JTAG access) — primarily a reliability/integrity defect rather than a direct attack path | Confidence: Medium

**Location:** `rtl/modules/rbist/rtl/rbist_wrp.sv:186`

**Description.** `rbist_wrp` receives `iptregset` from the IPT JTAG TAP: soc_top.sv:966 connects `.iptregset(iptregset[2])`, and `iptregset[2]` is produced inside `jtagtap` as `assign regset[i] = tap_updatedr & regsel[i];` (jtagtap.sv:78), where every flop in that TAP is clocked by `jtags.tck` = `jtagipt.tck` = `jtagclk` (pad_frame_arm.sv:248). The synchroniser that carries this pulse into the clksys domain, however, declares its launch clock as `jtagrb.tck` — a different net, assigned `jtagclk_occ = cmsatpg ? clkocc : jtagclk` (pad_frame_arm.sv:229,243). In CMS_TEST/VRGN the two happen to alias to the same physical net (jtagclk), which is why this has not been caught; in CMS_ATPG they are genuinely different clocks (clkocc, the on-chip-clock-controller output, versus the JTAG pin), so the `iptregset` pulse is sampled asynchronously by a synchroniser that was never told about it. The compiler cannot flag it because both are named `.tck` on `jtagif` instances. The result is that a JTAG-issued RAM-trim write can be silently dropped, doubled, or latch a metastable `ipttrmsel`/`ipttrmdat` value into the trim flops at rbist_wrp.sv:194-198 — i.e. a RAM group other than the intended one can receive an out-of-window margin setting.

**Evidence.**
```systemverilog
rtl/modules/rbist/rtl/rbist_wrp.sv:186-188
    sync_pulse su0 ( .clka(jtagrb.tck), .resetn(sysresetn), .clkb(clksys), .pulsea (iptregset), .pulseb( ipttrmset ) );
    sync_pulse su1 ( .clka(pclk),        .resetn(sysresetn), .clkb(clksys), .pulsea (trmar    ), .pulseb( sfrtrmset ) );
//    sync_pulse su1 ( .clka(jtagipt.tck), .resetn(sysresetn), .clkb(clksys), .pulsea (ipt), .pulseb( nvrtrmset ) );

rtl/asic_top/rtl/soc_top.sv:964-966  (iptregset comes from the IPT TAP, not the rbist TAP)
    .iptregset(iptregset[2]),
    .iptregout(iptregout[2]),
    .iptregin(iptregin[2]),

rtl/modules/dft/rtl/jtagtap.sv:66,78  (iptregset[2] is a jtagipt.tck-domain pulse)
        .clk_i           (jtags.tck ),
	assign regset[i] = tap_updatedr & regsel[i];

rtl/asic_top/rtl/pad_frame_arm.sv:229,243,248  (the two .tck nets are different in ATPG mode)
    assign jtagclk_occ = cmsatpg ? clkocc : jtagclk;
    assign jtagrb.tck  = jtagclk_occ;
    assign jtagipt.tck     = jtagclk;

rtl/asic_top/rtl/soc_top.sv:947,951  (the correct pattern, used elsewhere for the same pulse family)
    sync_pulse su0 ( .clka(jtagipt.tck), .resetn(sysresetn), .clkb(clksysao), .pulsea (iptregset[1]), .pulseb( aojtagipt_set ) );
    sync_pulse su3 ( .clka(jtagipt.tck), .resetn(sysresetn_undft), .clkb(clksys_undft), .pulsea (iptregset[0]), .pulseb( ipt_socset ) );
```

**Preconditions.** Chip in CMS_ATPG (or any future mode where jtagrb.tck and jtagipt.tck are not the same net). In CMS_TEST/VRGN the aliasing masks the bug. Requires JTAG access, i.e. Finding 1 or a legitimate tester.

**Attack scenario.** During ATPG/characterisation the clkocc and jtagclk domains are independent. An attacker (or, more likely, a mis-set production tester) issuing a JTAG trim write to a benign RAM group can have the `ipttrmsel` field sampled metastably by the su0 synchroniser, so that `ipttrmset & ( ipttrmsel == 128+i )` at rbist_wrp.sv:196 matches a different `i` than intended — landing an out-of-window margin word on, for example, group 9 (sce_sceram_10k) or group 26 (acram2kx64). The affected RAM then exhibits marginal read/write behaviour in the field with no error indication, since the trim registers persist until sysresetn (rbist_wrp.sv:194). This is the same corruption as Finding 4 but arrived at accidentally, and it can also cause a deliberately-issued trim write to be silently dropped, so a part shipped from test with the wrong margins believes it was programmed.

**Mitigation.** RTL: change the launch clock to the domain in which the pulse is actually generated — `sync_pulse su0 ( .clka(jtagipt.tck), ... )` — matching the pattern already used correctly at soc_top.sv:947 and :951 for the sibling pulses iptregset[1] and iptregset[0]. Better still, pass the IPT TAP's clock into rbist_wrp explicitly rather than deriving it from an unrelated jtagif instance, so the connection is checkable. Silicon workaround: production test flow must read back the trim word through SFRSR_TRM (0x40045004) after every JTAG trim write and retry on mismatch; end-user firmware should read back and verify the trim values for the security-critical groups (9, 26, 27) at boot.

**Verification.** Independently confirmed by a second reviewer. Every link in the chain checks out. rbist_wrp.sv:186 is verbatim `sync_pulse su0 ( .clka(jtagrb.tck), .resetn(sysresetn), .clkb(clksys), .pulsea (iptregset), .pulseb( ipttrmset ) );`. soc_top.sv:964-966 connects `.iptregset(iptregset[2])` from the IPT TAP. jtagtap.sv:66 clocks jtagreg on `jtags.tck` and :78 is `assign regset[i] = tap_updatedr & regsel[i];`, so iptregset[2] is a jtagipt.tck-domain pulse. pad_frame_arm.sv:229/243 give `jtagclk_occ = cmsatpg ? clkocc : jtagclk;` and `jtagrb.tck = jtagclk_occ;` while :248 gives `jtagipt.tck = jtagclk;` — identical nets when cmsatpg=0, genuinely different clocks when cmsatpg=1. The IPT TAP is live in ATPG (jtagipt.trst/tdi = (cmstest|cmsatpg)&..., pad_frame_arm.sv:249-250; iptap_en includes cmsatpg, soc_top.sv:907) whereas the rbist TAP is not (jtagrb.trst = cmstest & jtagtrst, :244), which is precisely the case where the two clocks diverge. sync_pulse (gnrl_sync.sv:32) toggles `toga` on clka, so an iptregset pulse launched on jtagclk can be missed or double-counted by a clkocc-clocked toggle flop. The contrast with the correctly-written siblings at soc_top.sv:947 and :951 (both `.clka(jtagipt.tck)`) confirms the intended pattern.

**Corrections applied by the verifier.** No factual correction; the analysis is right. I would only note explicitly that this has no offensive value: the mismatch is only real in CMS_ATPG, and an attacker who is in CMS_ATPG already has full scan control of the die, so this is a test-integrity/reliability defect rather than an attack path. Also worth telling the vendor that jtagipt is not even a port of rbist_wrp, so the only .tck available inside the module is the wrong one — the fix requires a port change, not a one-word edit.

---

<a id="bao-116"></a>

### BAO-116 — TAP TDO multiplexer indexes scan_out_i out of range for unmapped instruction codes

**Severity: Info**

**Location:** `rtl/modules/dft/rtl/tap_top.sv:542`

*Surfaced by the independent verifier, not the original domain reviewer.*

**Description.** The TDO output multiplexer's `default` arm indexes the per-register scan-out bus with `latched_jtag_ir_neg - `REG1`. `latched_jtag_ir_neg` is a 5-bit register (`reg [`IR_LENGTH-1:0] latched_jtag_ir, latched_jtag_ir_neg;`, tap_top.sv:392) holding any of 32 instruction codes, `REG1` is 5'b00100, and `scan_out_i` is only `[SETCNT-1:0]` = 5 bits wide. The case above it only names IDCODE (5'b00010) and BYPASS (5'b11111) — every other opcode outside 4..8 falls to the default. For IR values 0, 1 and 3 the subtraction wraps in 5-bit unsigned arithmetic to 28, 29 and 31; for IR values 9..30 the index is 5..26. In all of those cases the index is outside `scan_out_i`'s range, so TDO is driven with X in simulation and with an unspecified value in silicon. The IR is fully attacker/tester controlled (any 5-bit value can be shifted in at tap_top.sv:398-401), and the instruction decoder at tap_top.sv:497-508 correctly funnels all unmapped opcodes to BYPASS — the TDO mux simply fails to mirror that decision, so the two disagree about what an unmapped instruction means.

**Evidence.**
```systemverilog
rtl/modules/dft/rtl/tap_top.sv:527-544
always @ (*)
begin
  if(shift_ir_neg)
    tdo_comb = instruction_tdo;
  else
    begin
      case(latched_jtag_ir_neg)    // synthesis parallel_case
        `IDCODE:            tdo_comb = idcode_tdo;        // Reading ID code
        `BYPASS:            tdo_comb = bypassed_tdo;     // BYPASS
        default:            tdo_comb = scan_out_i[latched_jtag_ir_neg-`REG1];      // BYPASS instruction
      endcase
    end
end

rtl/modules/dft/rtl/tap_top.sv:36-46 (only 4..8 are valid register selects)
`define IR_LENGTH	5
`define IDCODE          5'b00010
`define REG1            5'b00100

rtl/modules/dft/rtl/tap_top.sv:513-517 (the select decode, which does bound the range)
  for ( i = 0; i < SETCNT; i++) begin: gg
    assign scan_sel_o[i] = (latched_jtag_ir == `REG1 + i);
  end
```

**Attack scenario.** A tester or an attacker with the DFT interface enabled shifts an unmapped instruction (for example IR = 5'b00000 or 5'b01010) into the IPT TAP and enters Shift-DR. The instruction decoder selects BYPASS and asserts no scan_sel_o bit, but the TDO mux takes its default arm and reads scan_out_i at an out-of-range index (28 and 6 respectively), so TDO is undefined rather than the JTAG-mandated bypass bit. The chain length seen by the tester is then not what the standard requires, and any RTL-level simulation of that sequence produces X on TDO, masking whatever the surrounding verification was trying to prove.

**Verification.** No independent verdict recorded for this entry.

---

<a id="bao-117"></a>

### BAO-117 — ahb_gate drops hauser/hwuser/hruser - the AHB identity tag is discarded at the SCE's security boundary

**Severity: Info** | CWE-1220 Insufficient Granularity of Access Control (identity signal not propagated across a bridge) | Threat actor: T1 (would-be), contingent on a downstream consumer existing | Confidence: High

**Location:** `rtl/modules/amba/rtl/amba_components.sv:1028`

**Description.** Every other AHB plumbing component in this library forwards the user sideband: `ahb_thru` (amba_components.sv:1022-1024), `ahb_demux_map` (ahb_demux.sv:114-115 and :129), `ahb_mux3` (amba_components.sv:275-276), `ahb_sync` (amba_components.sv:868-870), `ahbasync` (ahb_async.sv:54-55, :95-96), and even `ahbm_null` (amba_components.sv:512-513). `ahb_gate` is the sole exception: it is a byte-for-byte copy of `ahb_thru` with the three hauser/hwuser/hruser assignments deleted.

`ahb_gate` is instantiated in exactly one place in the design, and it is the SCE's AHB security gate (sce_sec.sv:76). Its master-side output is `ahbs0` (sce.sv:286), which is the slave port of the SCE's internal `ahb_demux_map` (sce.sv:159-168) and from there feeds the SCE's APB bridge, the SCE crypto-RAM DMA channel and the PKE RAM window. Because the gate never assigns `ahbmaster.hauser`/`hwuser`, those are undriven wires (the interface declares them `wire`, amba_interface_def.sv:268-269) throughout the SCE's internal fabric. Symmetrically, `ahbslave.hruser` is never driven back, so the SCE's external AHB slave port returns an undriven `hruser` (via ahb_sync, amba_components.sv:870), which is then OR-mixed into the coresub demux's `hruser` output at ahb_demux.sv:129 whenever the SCE is in a data phase.

I verified by grep that today nothing inside crypto_top consumes `hauser` downstream of the gate - the only readers are sce_sec.sv:61-62 and :73, all on the PRE-gate `ahbs`. So the present-day exploitable impact is nil; this is a latent defect and an X-propagation hazard, reported because the whole isolation model rests on this tag never being dropped and this is the one component in the fabric library that drops it.

**Evidence.**
```systemverilog
rtl/modules/amba/rtl/amba_components.sv:1028-1052 (note the absence of any hauser/hwuser/hruser assignment)
```
    module ahb_gate #(
      parameter AW=32,
      parameter DW=32
     )(
        input logic ahben,
        ahbif.slave             ahbslave,
        ahbif.master            ahbmaster
    );

        assign ahbmaster.hsel        = ahben & ahbslave.hsel        ;
        assign ahbmaster.haddr       = ahbslave.haddr       ;
        assign ahbmaster.htrans      = ahben ? ahbslave.htrans : '0      ;
        assign ahbmaster.hwrite      = ahbslave.hwrite      ;
        assign ahbmaster.hsize       = ahbslave.hsize       ;
        assign ahbmaster.hburst      = ahbslave.hburst      ;
        assign ahbmaster.hprot       = ahbslave.hprot       ;
        assign ahbmaster.hmaster     = ahbslave.hmaster     ;
        assign ahbmaster.hwdata      = ahbslave.hwdata      ;
        assign ahbmaster.hmasterlock = ahbslave.hmasterlock ;
        assign ahbmaster.hreadym    = ahbslave.hreadym    ;
        assign ahbslave.hrdata       = ahbmaster.hrdata     ;
        assign ahbslave.hready       = ahbmaster.hready     ;
        assign ahbslave.hresp        = ahbmaster.hresp      ;

    endmodule
```

Contrast with the identical module that does it right, amba_components.sv:1022-1024
```
        assign ahbmaster.hauser = ahbslave.hauser;
        assign ahbmaster.hwuser = ahbslave.hwuser;
        assign ahbslave.hruser = ahbmaster.hruser;
```

Sole instantiation, at the SCE's security boundary - rtl/modules/crypto_top/rtl/sce_sec.sv:76
```
    ahb_gate #(.AW(32),.DW(32)) ahbsgate(.ahben,.ahbslave(ahbs),.ahbmaster(ahbm));
```
wired into the SCE's internal demux - rtl/modules/crypto_top/rtl/sce.sv:285-286 and :167
```
        .ahbs        (ahbs0_sync),
        .ahbm        (ahbs0),
...
        .ahbslave (ahbs0),
```

**Preconditions.** None to exist. To become exploitable, requires either a future consumer of hauser inside crypto_top, or a synthesis/ECO tie-off of the dangling net to a value that matches one of the two IDs compared in sce_sec.sv.

**Attack scenario.** This is a latent defect rather than a directly exercisable attack today. The realistic failure mode is a maintenance one: any future SCE-internal slave (or any netlist/ECO change) that qualifies an access on `hauser` - exactly what `sce_sec.sv:61-62` and `:73` do on the pre-gate side - would read an undriven wire. In simulation that is X; in the synthesized netlist the tool ties the dangling net to a constant, and if it resolves to a value matching `AMBAID4_CM7P (4'h8)` or `AMBAID4_VEXD (4'h4)` the check passes unconditionally for every master, collapsing the SCE's owner gate. The immediate observable effect in the current design is that `hruser` returned from the SCE is undriven and is OR-mixed into the coresub demux's `hruser` output (ahb_demux.sv:124-131) during every SCE data phase, driving X onto that field for the whole core AHB segment.

**Mitigation.** RTL: add the three missing assignments to `ahb_gate`, mirroring `ahb_thru`, and gate them with `ahben` in the same style as `htrans` so that a blocked transfer also presents a null tag:\n    assign ahbmaster.hauser = ahben ? ahbslave.hauser : '0;\n    assign ahbmaster.hwuser = ahben ? ahbslave.hwuser : '0;\n    assign ahbslave.hruser  = ahbmaster.hruser;\nBetter still, delete `ahb_gate` entirely and add an `ahben` input to `ahb_thru`, so there is exactly one AHB pass-through implementation that cannot drift. Add a lint rule that fails on any undriven signal in an ahbif/axiif instance.\nNo firmware workaround is needed or possible on fabricated silicon, since there is no consumer today; the action item is to confirm in the delivered netlist what the dangling hauser/hwuser/hruser nets were tied to, and to record that tie-off value as a constraint on any future ECO.

**Verification.** Independently confirmed by a second reviewer. Read amba_components.sv:1028-1052 in full. The module body is byte-for-byte ahb_thru minus the three user assignments - confirmed, there is no hauser/hwuser/hruser assignment anywhere in ahb_gate. Contrast at amba_components.sv:1022-1024 in ahb_thru is quoted correctly.
Confirmed the instantiation: sce_sec.sv:76 `ahb_gate #(.AW(32),.DW(32)) ahbsgate(.ahben,.ahbslave(ahbs),.ahbmaster(ahbm));` and sce.sv:285-286 wiring ahbs0_sync -> ahbs0 into the SCE's internal ahb_demux_map at sce.sv:159-168. I grepped every hauser reference under rtl/modules/crypto_top/: the only three are sce_sec.sv:61, :62 and :73, all on the pre-gate `ahbs` - so the finder's claim that nothing downstream of the gate consumes hauser today is correct, and the ahben gate itself (sce_sec.sv:72-74) is computed from the pre-gate hauser and still works.
I checked the only other ahb_gate instance, amba_components.sv:1351 `ahb_gate u7(1'b1,ahb3,ahb4);`, and it is inside `module dummytb_ahbapb_thru()` - a simulation stub, not part of the design.
The hruser return-path claim also checks out: ahb_sync (amba_components.sv:870) drives ahbslave.hruser from ahbmaster.hruser, so the SCE's external hruser traces back to the undriven ahbs0_sync.hruser, and ahb_demux.sv:126-130 OR-mixes it into the parent's hruser during the SCE data phase. However I grepped every hruser consumer in the design and found none that makes a security decision (only rrc.sv:584 drives one), so the X does not reach any control logic. Zero present-day security impact.

**Corrections applied by the verifier.** The defect is exactly as described and the finder is right that present-day impact is nil - which is why this should be filed as informational/hygiene rather than low-severity security. Two small refinements: hauser/hwuser are declared `wire` (amba_interface_def.sv:268-269) so in simulation they resolve to Z, not X, while hruser is declared `logic` (amba_interface_def.sv:274) and does resolve to X. Also `ahb_mux3` (amba_components.sv:275-276) has the same omission on the return path - it forwards hauser/hwuser forward but never drives hruser back to its three slave ports - so ahb_gate is not quite 'the sole exception'.

---

## 4. Considered and dismissed

Candidate findings investigated by an independent reviewer and withdrawn. Recorded with full
reasoning so they need not be re-investigated, and so the basis for withdrawal is auditable.

### ~~DFT/BIST JTAG access is authorised solely by two external pads — all four ReRAM chip-mode patterns are the same constant 128'h0~~

Reassessed as **INFO**.

The quoted text is verbatim correct: cms.sv:34-39 does declare all four CMSDAT_* enum members as '0, and the decode at cms.sv:119-137 does then collapse. cms.sv:153 (`cmstestreg <= cmscodereg == CMS_TEST | cmscodereg == CMS_VRGN`), soc_top.sv:397 (`assign cmsbist = cmstest;`), soc_top.sv:907 (`assign iptap_en = cmstest | cmsbist | cmsatpg;`) and pad_frame_arm.sv:232-250/262-269 all read exactly as quoted. However, I cannot substantiate that this is the taped-out behaviour. Decisive counter-evidence: the top-level testbench drives the SAME pad pattern with THREE DIFFERENT data words and labels them three different lifecycle states — daric_rv32_tb.sv:1019-1021 `thenvrcms.cmsdata0 = CMSDAT_VRGNMODE; cmspad = {1'b1,1'b1,1'b0};` ("virgin mode"), :1045-1046 `... = CMSDAT_TESTMODE; cmspad = {1'b1,1'b1,1'b0};` ("test mode 1"), :1070-1071 `... = CMSDAT_USERMODE; cmspad = {1'b1,1'b1,1'b0};` ("user mode 1"), and :1093 `thenvrcms.cmsdata0 = {$urandom()...}; //not USER Pattern`. That test sequence is only meaningful if the four constants are distinct and USERMODE is a specific non-zero value. docs/src/ch00-00-rtl-overview.md:5 states "the RTL description of the Baochip-1x redacts some closed-source components", and the trailing-whitespace alignment on cms.sv:35 is the signature of a literal being replaced by '0. The constants are therefore almost certainly redaction placeholders, not the silicon values. Additionally the aocmsuser argument is beside the point: aocmsuser is 0 out of any cold power-up anyway (ao_top.sv:144 resets it to '0), so no reset trick is needed — which means the finder's whole XRSTn narrative adds nothing even in the hypothetical. Reporting 'all your lifecycle patterns are zero' to the vendor on the basis of a redacted constant is exactly the kind of false positive that destroys report credibility. It should be raised as a question ('please confirm the four CMSDAT_* patterns in silicon are distinct and that the provisioned USER pattern is non-zero'), not as a critical finding.

**Factual corrections.** Three factual errors. (1) The reset that clears `aocmsuser` is PAD_AOXRSTn, not PAD_XRSTn: ao_top's `padresetn` port is driven by `ao_padresetn` (daric_top.sv:963), which comes from `padcell_i ... u_aoxrstn ( .pad( PAD_AOXRSTn ), .pi( ao_padresetn ) ...)` (pad_frame_arm.sv:411). PAD_XRSTn drives a different net (`padresetn`, pad_frame_arm.sv:217). (2) The finder missed that cms.sv:92 (`theregrn( cmspadregs[1] ) <= { cmspadregs[0][0:1], 1'b0 };`) forces cmspadout[0] to 0 permanently, so PAD_WMS2 is ignored and the casex arm `3'bxx1` at cms.sv:121 is unreachable — mode select is a 2-pad, not 3-pad, function. (3) There is a compensating control the finder missed: any change on the WMS pads after the 128-cycle lock sets `cmspaderror` (cms.sv:97), and `cmserror` is wired into the SoC reset (`.socresetn (socresetn & ~cmserror )`, soc_top.sv:342), so glitching the pads after lock resets the chip.

### ~~The DFT TAP enable is a single non-redundant AND gate used only as an asynchronous reset, while the TAP clock runs free from an ungated pad~~

Reassessed as **LOW**.

jtagtap.sv:31-33 and :38-42 are quoted verbatim correctly, tap_top.sv:153-156 is correct (async assert and async release with no reset-removal synchroniser), and pad_frame_arm.sv:248-250 and soc_top.sv:906-907/927-930 are quoted correctly. So the individual quotes are accurate — but the conclusion drawn from pad_frame_arm.sv:248 is not, because the finder stopped at `assign jtagipt.tck = jtagclk;` and never traced `jtagclk` back to its driver. Tracing it: pad_frame_arm.sv:283 `padcell_io ... u_PA0 ( .pad( PA0 ), ..., .cmsatpg(cmstest|cmsatpg), ..., .testpi(jtagclk));` and padcell_arm.sv:44 `assign testpi = cmsatpg & pio_pi;`. That is the compensating control. What survives is a much weaker observation: at the moment cmstest asserts, the pad gate and the reset gate open from the same net with different delays, so the TAP reset is released against a clock that starts at nominally the same time and there is no reset-removal synchroniser; and the enable is not redundantly encoded. That is a hardening suggestion at low severity, not the described EM-FI break.

**Factual corrections.** The central premise is wrong. `jtagclk` and `jtagipt.tms` are NOT ungated pad signals. Both come from the pad cells' `testpi` output, and padcell_arm.sv:44 is `assign testpi = cmsatpg & pio_pi;` — while u_PA0 and u_PA3 are instantiated with `.cmsatpg(cmstest|cmsatpg)` (pad_frame_arm.sv:283 and :286). Therefore in USER mode jtagclk == 0 and jtagipt.tms == 0. TCK, TMS, TRST and TDI are all gated by the same (cmstest|cmsatpg) term; the finder's claim that 'only the trst and tdi AND-gates hold the flops in reset' while 'the TAP's clock and TMS are already live' is false, and the attack narrative (steps 1-3, replaying a JTAG sequence on a live TCK/TMS while faulting the enable) does not work as written.

### ~~BLAKE2 finalization flag is hardwired off - the last-block domain separation that makes BLAKE2 length-extension resistant is never applied~~

Reassessed as **LOW**.

Every quoted line is verbatim correct — combohasha.sv:550 `.cfg_finalhash('0),` is the only hashcore instance, and grep confirms cfg_finalhash has exactly four references in rtl/ (hashcore.sv:33, 80, 286 and combohasha.sv:550), so the port is indeed tied off and `finalrnd` is dead. But the security conclusion does not follow, because there is a second, software-reachable path to exactly the same effect that the finder missed.

At hashcore.sv:283 the BLAKE input stage is `assign vregpre_mfsmin = blk_mfsmin_segstpl2 ? { VREGCNT{ ramrdatreg }} : { VREGCNT{ ramrdatreg }} ^ { 512'h0, vreg_mfsmin_blk[8:15] };`. For HT_BLK2s/HT_BLK2b thecfg.inmode=1 and incnt=24 (hash_pkg.sv:64-65), so hashcore.sv:219-225 loads mfsm_incnt 0..15 from RAMSEG_ST into vreg[0..15] and mfsm_incnt 16..23 from ramseg_h (the IV table) into vreg[8..15] XORed with their current contents. That means v[14] = IV[6] ^ ST[14] — the standard BLAKE2 `v[14] = IV[6] ^ f0` construction. cfg_finalhash at hashcore.sv:286 is only a convenience that inverts ST[14] on the way in.

ST[14] is fully software-controlled: combohasha.sv:589-597 MFSM_LD_ST copies SEG_HOUT words 0..STSIZE-1 into HASHSEG_ST, and STSIZE=16 for HT_BLK2s / 32 for HT_BLK2b (combohasha.sv:530-531), so words 12/13/14/15 (t0/t1/f0/f1) are all loaded from SEG_HOUT. hashcore_hout mode 1 only writes back vreg[0:7] (hashcore.sv:753-754 `vregwr_m1[8:15] <= '0`; mfsm_wbcnt runs to wbcnt=8), so ST[8..15] persist. Firmware that writes SEG_HOUT word 14 = all-ones before the final block gets v[14] = IV[6] ^ 0xFFFF_FFFF = ~IV[6], which is exactly RFC 7693 f0. The engine therefore CAN produce spec-compliant BLAKE2 and CAN be made length-extension resistant, so both Case A ("digests never match") and Case B ("tag is always extendable") are wrong as stated.

What remains is real but much smaller: the dedicated cfg_finalhash port and the finalrnd register are dead logic, and the correct use of the engine depends on an undocumented software convention (setting ST[14]) with no hardware default enforcing it. The t0/t1 observation is factually correct (hashcore.sv:736-746 only ever writes ST word 12, and cfg_blkt0 is an 8-bit CR at combohasha.sv:220 with IV 0x40 — note 0x40 is the BLAKE2s block size, so BLAKE2b users must reprogram it to 0x80), but t1 is likewise software-loadable via SEG_HOUT word 13, so it is a counter-increment limitation, not an inability to set the counter.

**Factual corrections.** Refuted as a security finding. The compensating control is hashcore.sv:283-287 combined with combohasha.sv:589-597: v[14] = IV[6] ^ ST[14], and ST[14] is loaded from SEG_HOUT word 14 by MFSM_LD_ST, so firmware can set the BLAKE2 f0 finalization flag directly without cfg_finalhash. The same applies to t0/t1 via ST[12]/ST[13]. Downgraded critical-path claim to a low-severity dead-logic / undocumented-firmware-contract issue. Do not send Case B (length extension against keyed BLAKE2) to the vendor as written — it asserts an impossibility that the RTL contradicts.

### ~~Filter policy registers cross from pclk into the hclk/dmaclk filter with no synchronizer and no atomic commit, and in-flight transfers are never re-checked — narrowing a whitelist window can transiently open a wider one~~

Reassessed as **INFO**.

The quoted lines are all real (bio_bdma.sv:2528-2534 comment and ports, :620-621 the pclk apb_cr registers, :1298 `.clk(hclk)`, :1434 `.clk(dmaclk)`, :2550-2551 the combinational comparison), but the CDC premise is wrong and it is the premise the whole attack rests on. pclk, hclk, aclk and fclk are not independent domains: cgucore.sv:189 `ICG fdicg ( .CK (clktop), .EN (oclken[0]), .SE(cmsatpg), .CKG (clkout_unmux[0]));` and the identical generate loop for clkout 1..OCNT produce all of them as ICG-gated versions of the single `clktop`, with the enables generated by cgufdsync instances all clocked on clktop; sysctrl.sv:429 maps that bus to `{fclk,aclk,hclk,iclk,pclk,aoclkpre}`. soc_ifsub.sv:340-342 then ICG-gates hclk/pclk/fclk again with the same `clkbiogate`. Every domain edge is therefore a clktop edge. A 20-bit apb_cr in the pclk domain updates all twenty bits on one shared clktop edge, so the comparator at :2550 cannot observe a torn base/bounds pair, and there is no metastability path to a synchronizer's absence. The described transitional 0x00000 window does not exist. What remains is the ordinary same-domain race the RTL comment at :2529-2530 already calls out ("If they are updated during an access, unpredictable things will happen"), which is a static-timing/functional concern closed by STA, not an attacker-controllable window. The AXI address-stability concern likewise disappears once the policy is stable: for a held s_axi_awaddr, allow_write is a stable function of stable inputs.

**Factual corrections.** The mechanism is misidentified. This is not a clock-domain crossing at all — all BIO clocks are synchronous ICG-derived divisions of clktop (cgucore.sv:189 and the clkout generate loop; sysctrl.sv:429). Multi-bit tearing and metastability are both impossible, so the exploit as written cannot occur. The residual issue is a documented functional caveat, not a security defect; if the vendor is told this instead, it costs nothing and the rest of the report keeps its credibility. Severity lowered from medium to info.

### ~~CM7 coreuser bits are generated in reversed index order: rrc.sv reads the memory-region bits where it expects the boot0/boot1/fw0/fw1 identity, collapsing the ReRAM privilege ladder~~

Reassessed as **INFO**.

Verified verbatim: cm7sys.sv:753-757 and 761 match the quote; soc_coresub.sv:247-253 and daric_cfg_pkg.sv:62-67 match; rrc.sv:815-816 and 731-736 match; vexsys.sv:221 comment matches. The finder's error is that they never opened cm7sys.sv:159, the port declaration, which is `input axi_pkg::xbar_rule_32_t [0:PM_COREUSERCNT-1] coreusermap` — ascending. axi_pkg.sv:425-429 confirms xbar_rule_32_t is a `typedef struct packed`, so both sides are plain bit vectors and the [7:0]-to-[0:7] connection is a positional (bit-stream) mapping that reverses element order. Working the composition through: the finder's derived vector (coreuser[6]=DTCM, [5]=ReRAM, [4]=SRAM) is what you get only if the port were also [7:0]. With the actual ascending port, the double reversal yields the documented {fw1,fw0,boot1,boot0} in [7:4]. This is also self-consistent with the commented-out pre-ECO code at cm7sys.sv:743-745, which used the identical `PM_COREUSERCNT-gvi-1` indexing and whose companion line 759 comment ('all program out of reram will be identified as fw1') only makes sense under the correct interpretation. I also confirmed at cm7sys.sv:776 that coreuser resets to 0, and 8'h00 denies everything in rrc (key/data checks require a nonzero owner match, cfg_prev_dis requires coreuser[5]|coreuser[4]) — so the reset state is fail-closed.

**Factual corrections.** The reversal the finder identified is real in isolation but is cancelled by a deliberate (if obscure) packed-array port-direction mismatch that the finder did not check. cm7sys.sv:159 declares the port with an ASCENDING range — `input axi_pkg::xbar_rule_32_t [0:PM_COREUSERCNT-1] coreusermap` — while soc_coresub.sv:239 declares the actual signal with a DESCENDING range — `rule32_t [PM_COREUSERCNT-1:0] coreusermap_cm7`. Packed-array port connection is by bit position, so coreusermap[0] inside cm7sys is coreusermap_cm7[7] (fw1), coreusermap[1]=fw0, [2]=boot1, [3]=boot0, [4]=sram, [5]=reram, [6]=dtcm, [7]=itcm. Applying cm7sys.sv:755 (`coreuserreg0pre[PM_COREUSERCNT-gvi-1]`) to that gives coreuser[6]=fw0, [5]=boot1, [4]=boot0, [3]=sram, [2]=reram, [1]=dtcm, [0]=itcm, and coreuser[7]=~|coreuser[6:4]. That is EXACTLY rrc.sv:642's legend `coreuser [7]:fw1, [6]:fw0, [5]:boot1, [4]:boot0`, and rrc.sv:815 `!(coreuser_in[5]|coreuser_in[4])` really does mean 'not boot1 and not boot0'. Every downstream consequence the finder derives (CFG region open to fw1, key-slot owner nibble matching on memory region, XIP code presenting an unforgeable identity) therefore does not follow. The only residual observation is that coreuser[7] ('fw1') is a catch-all asserted for any PC outside fw0/boot1/boot0 — including SRAM, ITCM and the XIP window — but fw1 is the LEAST privileged identity in the ladder, so this is fail-safe, not fail-open: an XIP-resident attacker gets coreuser[7] only, which fails `!(coreuser[5]|coreuser[4])` and is therefore DENIED the CFG region.

### ~~Chip-Mode-Select lifecycle gate is decided entirely by two external pads: all four non-volatile CMS mode patterns are the identical constant 128'h0~~

Reassessed as **INFO**.

cms.sv:34-39, 91-92, 126-135 and nvrcfgs.sv:102-105 are quoted accurately. But the constants are redacted, not real: (1) README.md and docs/src/ch00-00-rtl-overview.md:5 state 'the RTL description of the Baochip-1x redacts some closed-source components'; (2) cms.sv:35 carries 33 trailing spaces between `'0` and the comma — the signature of a long hex literal replaced in place while preserving column alignment (lines 36-37 have one stray space each; line 38 has none); (3) duplicate enumeration values are illegal in SystemVerilog (IEEE 1800 §6.19), so this file as published would not elaborate in the VCS flow the vendor describes using — it cannot be the taped-out source; (4) decisively, the tape-out testbench treats the three patterns as distinct and tests unrecognised patterns separately: daric_rv32_tb.sv:1019 `thenvrcms.cmsdata0 = cms_pkg::CMSDAT_VRGNMODE;`, :1045 `= CMSDAT_TESTMODE;`, :1070 `= CMSDAT_USERMODE;`, and :1094 `= {$urandom(),...}; //not USER Pattern`. If all four constants were '0, these labelled test cases would produce results contradicting their own titles (the 'user mode 1' case would decode to CMS_VRGN). I could not substantiate that fabricated silicon has identical patterns, so per the rule I default to refuted. I did independently confirm the downstream unlock chain the finder describes is real (soc_top.sv:397 `assign cmsbist = cmstest;`, rrc.sv:884 `assign bist_enable = ((cmscode == CMS_VRGN) | (cmscode == CMS_TEST)) & (brfsm == 3'h5);`, soc_top.sv:907 `assign iptap_en = cmstest | cmsbist | cmsatpg;`) — but that chain is gated by a pattern match whose real constants are not in this repo. Note also that the WMS2 removal the finder flags as a bug is the deliberate A1 hardening ECO16b, documented in commit 86d5293: 'we need this ECO to remove the WMS2 pad to avoid potential backdoors.'

**Factual corrections.** The quoted lines exist verbatim, but they are a publication redaction artifact, not the silicon. Also factually wrong in three places: (a) it is cmspadout[0] (the WMS2 bit), not cmspadout[2], that line 92 forces to 0 (cmspadregs is declared [1:0][0:2], so cmspadregs[1][2] maps to cmspadout[0]); (b) `aocmsuser` is reset by porresetn_undft derived from ao_sysctrl.sv:422 `por = ~pmu_POR & padresetn`, and ao_top's `padresetn` port is wired to `ao_padresetn` from PAD_AOXRSTn (daric_top.sv:963), not PAD_XRSTn; (c) even taking the code literally, a non-zero CMS word falls through to CMS_SCDE, so 'no value of the non-volatile word can prevent entry into VRGN' is false. Compensating controls the finder missed: cmserror feeds soc_top.sv:342 `.socresetn (socresetn & ~cmserror)`, so any strap change after the 128-cycle lock holds the SoC in reset; and sysctrl.sv:790 `assign cmsresetn = ( cmscode == cms_pkg::CMS_USER ) & brdone;` feeds coreresetgen, so both CPUs are held in reset in VRGN/TEST/SCDE.

### ~~AO power-domain isolation is incomplete and is enabled by an unlocked software register: only cen/gwen are clamped, while clock, address and write data from the powered-off SoC domain reach the AO SRAM unisolated~~

Reassessed as **LOW**.

All quoted lines are verbatim correct (ao_top.sv:248-255, ao_sysctrl.sv:379, :586, :509, :362, docs/src/pmu.md:291). I read aoram.sv:141-166 to determine the polarity of bcen/bgwen and it is active-low, which is the compensating control the finder missed. I also confirmed the isolation OR gates and the `BUFFD8BWP40P140HVT u_iso_en_buf` (ao_sysctrl.sv:516) are inside the AO domain, so the clamp itself stays powered. The pdflow sequencing is coherent: pdflowfsm asserts pdisoreg at state 1 (before aopdreg at state 2) and clears it at state 5, holding at state 4 while `pdflowfsmstop = ~socresetn` (line 583-586), so on the default path isolation is asserted before and released after the SoC domain is down.

**Factual corrections.** The headline defect does not hold. `aoram_bcen`/`aoram_bwen` are ACTIVE-LOW enables - aoram.sv:144-145 `assign #0.5 bcen[i] = ~( rams_ramcs & (bsel==i) );` and `assign #0.5 bgwen[i] = ~( |rams_ramwr & rams_ramcs & (bsel==i) );` - so `|ao_iso_enable` clamps them to the DISABLED state. An SRAM macro with cen deasserted performs no operation and ignores its clock, address and data pins entirely; clamping only the enables is the standard and sufficient isolation for a memory macro at a power-domain boundary. Presenting 'clk/a/d are unisolated, therefore a spurious write can occur' to the vendor would be a technical error and would cost the report credibility. What survives is only the second half: `ao_iso_enable` is gated by `pdisoen`, an unlocked config bit (AO_CR[1], reset value 1 per IV 3'h6), so software can disable the clamp before power-down. That is a genuine but low-severity issue: the outcome is uncontrolled corruption of a general-purpose scratch SRAM, requires the attacker to also drive the power-down flow, and the actual electrical behaviour of unpowered drivers is not determinable from RTL. Recommend rewriting as 'power-domain isolation clamp is software-defeatable via an unlocked bit' and dropping the incomplete-isolation claim.

### ~~Async AHB bridge captures read data, response and user tag on an unsynchronized cross-domain enable while completing the transfer via a synchronized one~~

Reassessed as **LOW**.

Verified the evidence verbatim: bus_async.sv:51-61 matches the quote exactly (line 54 `dpreadys ... ~dpreadys & dpsdone ? '1`, line 56 `sync_pulse dpsync`, line 58 `assign dpmdone = dpm & dpreadym;`, line 60 `theregfull( clks, resetn, dpdatamreg, '0 ) <= dpmdone ? dpdatam : dpdatamreg;`). ahb_async.sv:57-62 and :100-104 match. soc_top.sv:830 and :841 match. gnrl_sync.sv:18-36 confirms sync_pulse is a proper toggle + 2-flop synchronizer, so dpsdone IS synchronized and dpmdone is NOT - the asymmetry is real.

The compensating control the finder missed is in the clock generator. (1) All core clocks are ICG gates off one root: cgucore.sv:236 `ICG fdicg ( .CK (clktop), .EN (oclken[gvi]), ... .CKG (clkout_unmux[gvi]))` for clkout = {fclk,aclk,hclk,iclk,pclk,aoclkpre}. (2) The AO clocks are toggle flops off fclk, which is itself an ICG of clktop: sysctrl.sv:483 `always@(posedge fclk ) aoclkreg <= aoclken ? ~aoclkreg : aoclkreg;` and sysctrl.sv:500 `always@(posedge fclk ) clkaoramreg <= clkaoramen ? ~clkaoramreg : clkaoramreg;`. So hclk, iclk, clkao and clkaoram are all frequency- and phase-related derivatives of clktop; there is no asynchronous sampling event and therefore no metastability.
(3) The divider hierarchy enforces the frequency ordering. cgufdsync.sv:77 `assign clk2en = clk2en_atclk1 & clk1en & clk0en;` makes every child enable a strict subset of its parent enable (the module header comment even states 'when clk2fd is faster than clk1fd, the actual clk2en equal clk1en'). cgucore.sv:235 `assign iclken[gvi] = (gvi==OCNT-1) ? oclken[2] : oclken[gvi-1];` gives aoclken (gvi=5) the parent oclken[2] = hclken. sysctrl.sv:491 `.clk1en (iclken)` gives clkaoramen the parent iclken. Combined with the extra divide-by-2 from the output toggle flop, this yields clkao <= hclk/2 and clkaoram <= iclk/2 for every possible programming of CGUFD_AOCLK/CGUFD_AORAM/CGUFD_HCLK/CGUFD_ICLK.
For uahbaolf (clks=hclk, clkm=clkao) and uahbaoramlf (clks=iclk, clkm=clkaoram) this means clkm period >= 2 x clks period always, so the one-clkm-cycle dpmdone pulse always contains at least one clean clks sampling edge, and dpdatamreg is always loaded before dpsdone (which needs >=2 further clks edges through the toggle synchronizer) releases dpreadys. The 'stale previous requester's word' outcome cannot occur.
I also confirmed the finder's supporting claim that soc_top.sv:217 `logic sfrlock;` is undriven and used at soc_top.sv:361 `.sfrlock (sfrlock|'0)` - that is true, but it does not help this attack because the divider hierarchy, not the lock bit, is what bounds the AO clock.

**Factual corrections.** The quoted RTL is accurate and the structural observation (bus_async.sv:60 uses the raw clkm strobe `dpmdone` as the clks capture enable while bus_async.sv:54 uses the synchronized `dpsdone` to release the transfer) is real. But BOTH claimed failure modes are refuted by the clock generator: (a) the metastability variant is refuted because clks and clkm here are not asynchronous - they are all edge-related derivatives of the single `clktop` root; (b) the deterministic stale-read variant is refuted because clkm <= clks/2 is structurally guaranteed for both instances regardless of software divider programming, so the one-clkm-cycle `dpmdone` pulse always spans at least two clks edges and is always captured. The attack step 'slowing iclk relative to clkaoram' is impossible because clkaoramen is *derived from* iclken. Residual issue is a CDC-methodology/implementation-flow risk (if this path is false-pathed as async in STA, or if the AO clock topology is ever changed), not an exploitable defect - hence low, not high.

## 5. Coverage gaps and follow-up

Two independent critics reviewed the audit itself: one for coverage (what was never looked at)
and one for gaps between documented guarantees and the RTL. Their output follows essentially
unedited, because what an audit *missed* is as material to a reader as what it found.

---

#### COMPLETENESS CRITIQUE — Baochip 1x RTL audit

##### Method
I reconstructed the authoritative synthesis file set by expanding every `` `include`` in `rtl/asic_top/include/*.sv` (the build is include-list driven; `rtl/asic_top/include/daric_inc.sv` is the root). 1304 include directives resolve to **298 files that exist in this repo and are pulled into the ASIC build**. Cross-referencing against the eleven coverage statements: **145 were read, 153 were never opened.** Below is what that costs you.

---

#### 1. IN THE TAPED-OUT NETLIST, IN THIS REPO, READ BY NOBODY

##### 1a. The main SoC SRAM controller — the single biggest hole
`rtl/modules/common/rtl/axisramc.sv` (187 L) is instantiated twice at `soc_coresub.sv:667,674` as `axisramc64 #(.WCW(1)) sramc0` / `#(.WCW(0)) sramc1` — this is the shared main SRAM every master reaches. It is in the build via `daric_inc.sv:26`. **Nobody read it.** It is not clean:

```
axisramc.sv:138    assign ahbmaster_hauser = axibdg.HAUSER;
axisramc.sv:139    assign ahbmaster_hwuser = axibdg.HWUSER;
```
Those two nets are **assigned and then never consumed**. The downstream `ahb_sram_bridge_64` instance (`axisramc.sv:146-172`) has no `HAUSER`/`HWUSER`/`HPROT`-based gate at all, and is hardwired open:
```
axisramc.sv:167    .HSEL      (1'b1),
axisramc.sv:168    .HREADY    (1'b1),
```
So the main SoC SRAM performs **zero identity, coreuser, or privilege filtering** — the coreuser tag arrives at the RAM and is discarded. Every "isolation between the two CPUs / between privilege levels" claim in the threat model is untested against the memory that both CPUs actually share. `mbox-fabric` audited tag propagation through `rtl/modules/amba/rtl/*` and stopped at the fabric edge; the tag's *terminus* was never checked. Companion files `rtl/modules/common/rtl/ahbsramc.sv` (93 L, in build via `soc_ifsub_inc.sv:18`), `sram.sv` (164 L) and `gnrl_sramc_pkg.sv` are likewise unread.

##### 1b. The Vex's own AXI interconnect — 12 files, ~5200 lines, all in the build
`rtl/modules/vexriscv/lib/`: `axi_crossbar.v` (406), `axi_crossbar_rd.v` (600), `axi_crossbar_wr.v` (698), `axi_crossbar_addr.v` (438), `axi_axil_adapter{,_rd,_wr}.v` (1375), `axi_register_{rd,wr}.v` (1365), `arbiter.v`, `priority_encoder.v`. The `cpu-vex` reviewer read the *address map constants* inside `cram_axi.sv:22940-23090` but not the crossbar RTL. Concretely, `cram_axi.sv:22951-22976` instantiates it with:
```
.ARUSER_ENABLE(1'd0), .AWUSER_ENABLE(1'd0), .WUSER_ENABLE(1'd0),
.BUSER_ENABLE(1'd0),  .RUSER_ENABLE(1'd0),
```
and `axi_crossbar.v:67-85` defaults `*USER_WIDTH = 1`. Nobody established whether `coreuser_vex`/`vex_mm` ride the AxUSER channel through this crossbar or bypass it as sideband. That determination decides whether the `cpu-vex` and `rrc-nvm` identity findings are exploitable or moot. It is *readable open RTL* and it was skipped.

##### 1c. `nic1_intf.sv` — declared a black box by two reviewers; it is 476 lines of readable RTL
Both `mbox-fabric` and `bio-bdma` wrote "nic400_1 / nic1_intf are black boxes not present in this repo" and downgraded/caveated findings on that basis. `rtl/modules/bmxcore/rtl/nic1_intf.sv` **is** in the repo and in the build. Only the inner `nic400_1` instance is encrypted. The wrapper is where the ID and USER mapping happens:
```
nic1_intf.sv:65   assign m0.awid = nic1_AWID_m0|'0;
nic1_intf.sv:154  .AWUSER_m0 (m0.awuser),
nic1_intf.sv:157  .ARUSER_m0 (m0.aruser),
```
Reading this would have raised (or settled) `bio-bdma` finding 3 and `mbox-fabric` finding 2 from "asserted by integration" to proven. It also shows all four master ports' ID widths are 10 bits driven from the NIC, i.e. **the master ID presented to ReRAM is generated inside the closed NIC, not by the master** — which nobody checked and which directly bears on the AMBAID/hauser trust model.

##### 1d. Interrupt / event delivery — the entire path, unaudited
`rtl/ips/pulp_soc/rtl/pulp_soc/soc_event_queue.sv` and `soc_event_arbiter.sv` are in the build (`daric_inc.sv:48-49`) and instantiated inside the audited `evc.sv`:
```
evc.sv:108   soc_event_queue u_soc_event_queue (... .event_i(evin[j] & ifeven[j]), .err_o(ifev_errs[j]) ...)
evc.sv:119   soc_event_arbiter #(.EVNT_NUM(EVCNT)) u_arbiter (.req_i(s_req), .grant_o(s_grant), ...)
```
The `sysctrl-clk-reset` reviewer read `evc.sv` but not the two leaf modules. Nobody asked: is the arbiter fixed-priority? Can a software-spammable low-index event starve the tamper/security events that `tamper-sec` traced into `soc_top.sv:473 ev[239:224]`? Does a full queue silently drop a tamper event (`err_o` is wired to `ifev_errs`, a status bit)? **The audit filed a `[medium]` on tamper events terminating in a maskable interrupt but never checked whether that interrupt can even be delivered under load.**

##### 1e. Timers and the advanced PWM timer — 12 files, ~3000 lines
- `rtl/ips/pulp_soc/rtl/components/apb_timer_unit.sv` + `rtl/ips/timer_unit/rtl/timer_unit_counter.sv` — in build (`daric_inc.sv:52-53`), instantiated at `aoperi.sv:89`. The `ao-domain` reviewer wrote "apb_timer_unit … third-party IP not in this repository" — **it is in this repository**, and ao_peri was left "effectively uncovered beyond its wiring" on a false premise.
- `rtl/ips/apb/apb_adv_timer/rtl/*` (10 files, 2792 lines) — in build via `soc_ifsub_inc.sv:121-130`, instantiated at `rtl/modules/ifsub/rtl/pwm_intf.sv:30`. `pwm_intf.sv` itself (69 L) is also unread. This block contains `input_stage.sv` and `lut_4x4.sv` — a programmable input-event/trigger selector feeding counters that drive **external pads**. That is a textbook software-controlled covert-exfiltration and timing-observation primitive on a secure chip, and nobody looked at it.

##### 1f. AXI infrastructure in `rtl/ips/` — 13 files
`axi_xbar.sv`, `axi_mux.sv`, `axi_demux_nointf.sv`, `axi_err_slv.sv`, **`axi_id_prepend.sv`**, `axi_intf.sv`, `axi_pkg.sv`, plus the 6-file `axi_slice_dc` async CDC. `bmxcore.sv` routes BDMA/MDMA/SCE through `axi_mux`/`axi_xbar` and `axi_id_prepend` is precisely the module that rewrites master IDs — the thing every ReRAM access-control finding depends on. `mbox-fabric` explicitly noted "rtl/ips/axi were only spot-checked … pulp axi_xbar/axi_mux internals were not read line-by-line."

##### 1g. `rtl/ips/common_cells/` — 16 files including the security-relevant ones
`addr_decode.sv` (the AXI crossbar's address decoder — a live access-control decision), `rr_arb_tree.sv` (arbiter fairness/starvation), `fifo_v3.sv`, `spill_register*.sv`, `edge_propagator*.sv`, `pulp_sync.sv` / `pulp_sync_wedge.sv` (the CDC synchronizers). Zero coverage.

##### 1h. Physical/pad/clock cells in the build
- `rtl/modules/model/rtl/padcell_arm.sv` (336 L) — included unconditionally at `daric_inc.sv:66`. `pad_frame_arm.sv` was read but the cell it instantiates was not. Pull-up/down defaults, input-enable behaviour under reset, and retention behaviour of the JTAG/SWD/WMS pads all live here.
- `rtl/asic_top/rtl/powerpad.sv` (288 L, `daric_inc.sv:68`) — its only functional inputs are `pvsense_reton`/`pvsense_retoff` (`powerpad.sv:37-38, 221-222`), traced from `daric_top.sv:436-437` ← `soc_top.sv:112-113`. Nobody traced who drives pad retention or what it does during a power-domain transition.
- `rtl/modules/common/rtl/pulp_icg.sv`, `rtl/ips/tech_cells_generic/src/deprecated/pulp_clk_cells.sv`, `pulp_clock_gating_async.sv`, `rtl/modules/model/rtl/icg.v` — every clock gate in the design. `sysctrl-clk-reset` explicitly said "I cannot verify whether the ICG cells are glitch-free." Three of the four candidate cells are in this repo.
- `rtl/modules/common/rtl/scresetgen.sv` (44 L) — the reset generator used by `qfc.sv:226` (the XIP flash controller). Unread.
- `rtl/asic_top/rtl/sparecell.v` — 200 instances in the SoC domain (`soc_top.sv:1011`) + 8 in AO (`ao_top.sv:272`), each containing 3 `SDFCSNQD2BWP40P140HVT` **scan flip-flops** with `.SI(1'b0), .SE(1'b0), .CP(1'b0)`. That is ~624 spare scan flops whose scan pins are tied off in RTL but which are re-stitched at scan insertion. Nobody asked whether they end up on a chain.

##### 1i. uDMA leaf peripherals — 59 files, ~15000 lines
`udma_rx_channels.sv` (731 L) and `udma_tx_channels.sv` (549 L) generate the L2 addresses; `udma_qspi/*` (2390 L), `udma_i2c/*`, `udma_sdio/*`, `udma_uart/*`, `udma_i2s/*`, `udma_camera/*`, `udma_filter/*` (2267 L, an in-line data-transform engine with its own DMA), `udma_external_per/*` (740 L, a *traffic generator* wired into the fabric), `udma_arbiter.sv`, `udma_clkgen.sv`. `peripherals-external` justified skipping these with the 18-bit address truncation argument, which is sound for *memory safety* — but not for: DoS via `PREADY` stalls (they already found one such bug), clock-generator lockup, event/IRQ flooding into the unaudited event arbiter, or the `udma_external_per` traffic generator being reachable at all.

Also unread in `rtl/modules/ifsub/rtl/`: `udma_scif_reg.sv`, `udma_scif_rx.sv`, `udma_scif_tx.sv` (829 L — the smart-card interface's actual register file and datapath, where the externally-clocked domain from finding `udma_scif.sv:217` terminates), `udma_adc_ts_reg_if.sv`.

##### 1j. BIO/BDMA interconnect leaves — 10 files
`axil_crossbar.v`, `axil_crossbar_rd/wr.v`, `axil_register_rd/wr.v`, `axil_reg_if{,_rd,_wr}.v`, `cdc_blinded.v`, `regfifo.v`. The `bio-bdma` reviewer read the filter and the CDC wrappers but not the crossbar body — and the "gutter re-addressing" finding depends on how the crossbar handles the rewritten address.

---

#### 2. WHOLE VULNERABILITY CLASSES NEVER PROBED

**(a) Power-domain isolation.** There is exactly **one** isolation enable in the design and it gates exactly two SRAM pins:
```
ao_top.sv:251   .cen  (aoram_bcen[i]|ao_iso_enable),
ao_top.sv:252   .gwen (aoram_bwen[i]|ao_iso_enable),
ao_sysctrl.sv:509  assign ao_iso_enable_temp = cmsatpg? 1'b0 : pdisoreg;
```
`grep -rn ao_iso_enable rtl/ --include=*.sv` returns no other consumer. Every other signal crossing the SoC↔AO boundary while the SoC domain is powered down — the APB bus, `wkupvld`, `ipflow_set`, `aocmsuser`, the AO SRAM address/data buses — has **no isolation clamp in RTL**. And `cmsatpg` (ATPG test mode) forces isolation *off*. Nobody analysed what the AO domain samples from a floating SoC domain during `PMU_PDAR` power-down — which is the reachable state `ao-domain` finding #4 already establishes an attacker can enter.

**(b) Analog test-mode / probe hooks.** `pmu_top.sv` (341 L, in build via `ipbox_inc.sv`, instantiated `daric_top.sv:992`) exposes `D2A_VDDAO_PMU_TEST_EN`, `D2A_VDDAO_PMU_TEST_SEL`, `PMU_ANA_TEST`. Their driver is **software**, not DFT:
```
ao_sysctrl.sv:311  assign pmu_PMU_TEST_SEL[2:0] = cmstest | cmsatpg ? soc_PMU_TEST_SEL : pmudft_testsel[2:0];
ao_sysctrl.sv:312  assign pmu_PMU_TEST_EN [2:0] = cmstest | cmsatpg ? soc_PMU_TEST_EN  : pmudft_testen [2:0];
ao_sysctrl.sv:339-340  { ..., pmudft_testsel, pmudft_testen } = sfrpmudftcr;
ao_sysctrl.sv:387  apb_cr #(.A('h1c), .DW(PMUDFTW), .IV(IV_PMUDFT)) sfr_pmudft (.cr(sfrpmudft), ...)
```
Note the polarity: in **functional** mode (`cmstest=0, cmsatpg=0`) the *software* register wins. `ao-domain` reported the trim and regulator-enable registers but not this analog test-mux enable, which is a candidate on-die analog probe path to the bandgap/regulator nodes.

**(c) CM7 debug authentication.** `jtag-dft-bist` declared this unassessable. It is partly assessable and the asymmetry with the Vex is stark:
```
cm7sys.sv:589   .DBGEN     (cm7cfg_dev),
cm7sys.sv:590   .NIDEN     (cm7cfg_dev),
cm7sys.sv:845   .SWCLKTCK  (swclk),              // NOT gated
cm7sys.sv:855   .SWDITMS   (swdio_pi & cm7cfg_dev),
cm7sys.sv:865   .DEVICEEN  (cm7cfg_dev),
```
versus `vexsys.sv:136 assign jtagtck0 = jtags.tck & vexcfg_dev;` — the Vex **gates the debug clock**, the CM7 does not. And `cm7cfg_dev` is one AND gate off one flop: `soc_coresub.sv:268 assign cm7cfg_dev = corecfg_devreg & cm7cfg_en;`, with `corecfg_devreg` being the single non-redundant ReRAM magic-compare flop that `sysctrl-clk-reset` explicitly declined to file. Nobody filed the CM7 debug-authentication single-point-of-failure, and nobody checked whether a free-running SWCLK into the DAP with `DEVICEEN=0` is safe.

**(d) CoreSight trace / debug buffers.** `cm7sys_inc.sv` pulls in the complete `cm7tpiu`, `cm7itm`, `cm7dwt`, `cm7fpb`, `cm7cti`, `cm7stb` and `cm7dap` hierarchies. `cm7sys.sv:227 TPIUBASE = 32'hE0040000`, `:915 .ENTRY1BASEADDR(TPIUBASE)`, `:939 .psel1(psel_tpiu)`. Nobody asked: is the trace port bonded to a pad? Is ITM/DWT enablement gated by `NIDEN` only (it is — `cm7sys.sv:590`, same single bit)? DWT comparators are a hardware watchpoint engine that can be used to observe secret-dependent addresses. **Debug/trace buffers were listed as a target class and got zero coverage.**

**(e) Systematic SFR reset-value and lock sweep.** There are **297** `apb_cr`/`apb_sfr2`/`apb_ar`/`ahb_cr`/`ahb_ar` register instances in `rtl/modules/`. The audit reported lock/default problems for perhaps fifteen of them, found ad hoc. There is no evidence anyone enumerated all 297 against `(IV parameter, sfrlock binding, read-back present)`. The binding census is:
```
22×  .sfrlock (sfrlock)          ← in sysctrl this net is undriven (soc_top.sv:217)
14×  .sfrlock (1'b0)             ← 11 of them inside rrc.sv, 3 in amba_components.sv
 3×  .sfrlock (sfrlock|'0)
 1×  .sfrlock (~devmode & (|cr_scemode))
 1×  .sfrlock (ioxlock)          ← tied '0 at soc_top.sv:772
```
i.e. **essentially every control register in the chip is permanently writable**, and the audit reported that fact ~10 separate times as ~10 separate medium findings rather than once as the systemic defect it is. A single generated table would be far more actionable to the vendor than the current scatter.

**(f) X-propagation and undriven nets.** The audit found `sfrlock` undriven at `soc_top.sv:217` and `owr` undriven at `sysctrl.sv:977` **by accident, while looking for something else**. Nobody ran a systematic undriven/multiply-driven/X-source sweep. Two independent findings of this exact class strongly implies more exist. Related: `rrc-nvm` noted `trc_info_lock_err` is "likely reading an undriven net" (`rrc.sv:289`) and could not confirm — an elaboration run would settle it in seconds.

**(g) Metastability in security-signal synchronizers.** `cpu-vex` explicitly deferred it ("The CDC of `coreuser_vex`/`vex_mm` from Vex `aclk` into RRC `clktop` has no synchronizer — soc_coresub.sv:839-841 into rrc.sv:664/670 … that belongs to the fabric/RRC domain, not mine"), and `mbox-fabric` did not pick it up. **This dropped between two reviewers and is currently in nobody's report.** It is a coreuser tag crossing a clock domain unsynchronised into the ReRAM access-control comparator. Add to that: the synchronizer primitives themselves (`pulp_sync.sv`, `pulp_sync_wedge.sv`, `dc_synchronizer.v`, `gnrl_sync.sv`'s siblings) were not audited for depth or for reset-domain correctness.

**(h) Boot / first-instruction path.** Nobody traced where either CPU fetches its first instruction from. It is an 8-bit ReRAM field with no integrity check:
```
soc_coresub.sv:263  assign cm7cfg_iv_8b = nvrcfgdata.cfgrrsub.m7_init;
soc_coresub.sv:264  assign vexcfg_iv_8b = nvrcfgdata.cfgrrsub.rv_init;
soc_coresub.sv:265  assign cm7cfg_iv    = `ambarrb(cm7cfg_iv_8b);
cm7sys.sv:421       .INITVTOR (cm7cfg_iv[31:7]),
vexsys.sv:235       .trimming_reset (vexcfg_iv),
```
`sysctrl-clk-reset` confirmed the boot-read path has "NO ECC, parity, CRC or redundant copy" and correctly argued the *devmode* and *coresel* compares fail closed — but `m7_init`/`rv_init` are **not** magic-compared; any value is accepted and becomes the reset vector. That is the root of secure boot and it is unexamined.

**(i) Claimed-but-unimplemented redundancy.** `cm7sys.sv:369 .LOCKSTEP(LOCKSTEP)` — nobody resolved the parameter value or checked whether lockstep is actually enabled. For a chip whose findings include "single non-redundant equality compare" three separate times (`AesCtrl.v:846`, `scedma_ac.sv:40`, `sce.sv:376`), whether the CM7 is in lockstep is material.

**(j) The A1 metal-mask ECO itself.** Commit `86d5293` is the vendor's own written statement of six known security defects and their fixes (ECO16a.1/a.2, 16b, 16c, 16d, 16e), touching only `cm7sys.sv`, `rrc.sv`, `cms.sv`. **Nobody read it.** It contains the vendor's authoritative definition of the coreuser bit map, the intended `rrccr[12]` one-way semantics, and the intended `ahb_read_acram` fix — i.e. exactly the "documented guarantee vs. RTL" oracle that eight reviewers independently reported as "not possible, no docs exist." Three findings (`core-mem-dma` #1 coreuser index inversion, `rrc-nvm` `rrccr[12]` reset value, `rrc-nvm` ACRAM rewrite) sit directly on top of ECO'd code and were analysed without reading the ECO rationale. **The `rrc-nvm` critical finding at `rrc.sv:360` is in the region ECO16e rewrote — it must be re-verified against the commit's stated intent before it goes to the vendor.**

---

#### 3. FACTUAL ERRORS IN THE COVERAGE CLAIMS THAT WEAKEN SHIPPED FINDINGS

1. `nic1_intf.sv` is **in this repo** (476 L). Two reviewers said it isn't and caveated findings accordingly.
2. `apb_timer_unit` is **in this repo** at `rtl/ips/pulp_soc/rtl/components/apb_timer_unit.sv`. `ao-domain` said it isn't and left ao_peri uncovered.
3. `mac_ref.sv` appears in the synthesis include list (`sce_inc.sv:70`) and is instantiated at `mimm.sv:505,515,524`. The `pke-alu` reviewer excluded it as non-synthesised — that call is **correct** (those instances sit inside `` `ifdef SIM_MIMM``, `mimm.sv:394`–`761`), but it was reached by assumption, not verification, and it is one `+define` away from being real.

---

#### 4. PRIORITIZED NEXT STEPS

1. **Read `axisramc.sv` end to end and decide whether the main SoC SRAM has any access control.** If the answer is "none" (which lines 138-139 and 167-168 suggest), that is a critical-severity CPU-isolation finding that outranks most of what is currently in the report, and it is a 187-line file.
2. **Read commit `86d5293` in full and re-verify every finding that touches `rrc.sv`, `cm7sys.sv`, or `cms.sv` against it.** This is the only vendor specification that exists. Do this before shipping — a finding that duplicates or contradicts a documented ECO destroys credibility.
3. **Elaborate the design.** Run `verilator --lint-only -Wall` or equivalent over `daric_inc.sv`. That resolves in minutes: undriven-net sweep (two were already found by hand), the `daric_cfg_pkg.sv:116-128` comment-block problem that blocked three reviewers from resolving `CM7CFG.MPU`, the `trc_info_lock_err` question, and multiply-driven security nets. Several reviewers said "I did not build or simulate anything" — that is the single highest-leverage remaining action.
4. **`rtl/modules/vexriscv/lib/axi_crossbar*.v` + `rtl/ips/axi-master/src/axi_id_prepend.sv` + `nic1_intf.sv`.** Settle, once, whether `coreuser`/AxUSER/master-ID survive every interconnect hop. Four `[high]` findings (`bio-bdma` #3, `rrc-nvm` #2, `cpu-vex` #1/#2) are stated at reduced confidence purely because this was not done, and 2 of the 3 blocking files are open RTL.
5. **`soc_event_queue.sv` + `soc_event_arbiter.sv`.** ~200 lines. Determine whether a security/tamper event can be starved, dropped, or priority-inverted by software-generated event traffic. This is the delivery mechanism for every escalation path the audit already found.
6. **Generate a machine-checked table of all 297 SFR instances** — `(file:line, address, IV, sfrlock expression, read-back present)` — and replace the ~10 scattered "register X is unlocked" findings with one systemic finding plus the table. This is what the vendor can actually act on for the next stepping.
7. **CM7 debug authentication and CoreSight trace.** Trace `swclk`/`SWCLKTCK` gating, `DBGEN`/`NIDEN` redundancy, and whether TPIU/ITM/DWT reach a pad. The Vex was cleared on exactly these grounds; the CM7 was never checked and its gating is demonstrably weaker.
8. **Power-domain isolation.** Enumerate every net crossing the SoC↔AO boundary and check it against the single `ao_iso_enable` (`ao_top.sv:251-252`), including the `cmsatpg` force-off at `ao_sysctrl.sv:509`.
9. **`pwm_intf.sv` + `apb_adv_timer/*`** (2861 L). A programmable event-triggered counter block driving external pads, currently completely unexamined, on a chip whose whole point is not leaking.
10. **`rtl/ips/common_cells/{addr_decode,rr_arb_tree,pulp_sync,pulp_sync_wedge}.sv`** — the address decoder that makes routing decisions and the synchronizers that carry security signals across domains. Small files, high leverage.

Deprioritize: the 59 uDMA leaf files. The 18-bit address truncation at `udc.sv:109-110` and `ifsub1_intf.sv:170-171` is a genuine structural bound and that reviewer's positive result is the strongest piece of work in the packet. Sample two files (`udma_rx_channels.sv`, `udma_external_per_top.sv`) to confirm no bus-master escape, then leave the rest.

---

#### SPEC-vs-RTL FINDINGS — Baochip-1x

Doc paths are `docs/src/`, RTL paths `rtl/`.

---

##### F1 (HIGH) — BIO/BDMA peripheral whitelist filter is wired to the wrong control bit; `DISABLE_FILTER_PERI` is dead silicon and `DISABLE_FILTER_MEM` silently opens all of peripheral space

**Doc promise** — `docs/src/ch02-00-bio-overview.md:804-805`:
```
| [6] | DISABLE_FILTER_PERI | When `1`, disables the host peripheral range whitelist filter. Setting this is strongly discouraged in secure applications. |
| [7] | DISABLE_FILTER_MEM  | When `1`, disables the host memory range whitelist filter. Setting this is strongly discouraged in secure applications. |
```
and `ch02-00-bio-overview.md:70`: *"access to main memory is blocked by a whitelist, which by default is empty… This also helps prevent abuse of the BDMA as a method for bypassing host CPU security features."*

**RTL** — `rtl/modules/bio_bdma/rtl/bio_bdma.sv`. Both bits are decoded correctly into the SFR (lines 324-325, 504-508), but **both** filter instances receive `disable_filter_mem`:

```
1339:        .base           (filter_base),
1340:        .length         (filter_bounds),
1341:        .gutter         (mem_gutter),
1342:        .disable_filter (disable_filter_mem)      // mem_filter — correct
```
```
1475:        .base           (filter_base),
1476:        .length         (filter_bounds),
1477:        .gutter         (peri_gutter),
1478:        .disable_filter (disable_filter_mem)      // peri_filter — WRONG, should be disable_filter_peri
```

`disable_filter_peri` is declared (`:325`) and packed into `SFR_CONFIG` (`:506`) and is **read nowhere else in the design** (exhaustive grep over `rtl/` and `deps/`: only lines 325, 506).

**Consequences**
1. `SFR_CONFIG[6]` is a no-op. Software that follows the doc and clears bit 6 while setting bit 7 believes it has left the peripheral filter armed; it has not.
2. Setting `SFR_CONFIG[7]` — documented as affecting only the memory range — **also disables the peripheral filter** at `bio_bdma.sv:2556-2557` (`allow_write = |match_write | disable_filter`). The peri window is `0x4000_0000-0x5FFF_FFFF` (crossbar decode at `:1397-1399`), which contains the SCE crypto block, `sysctrl`/CGU, the SEC tamper subsystem, the ReRAM controller, and the BIO's own filter/gutter registers at `0x5012_4000`. A single documented-as-memory-only concession therefore hands four PicoRV32 cores unfiltered write access to every security peripheral on the chip.
3. There is no lock: `bio_bdma.sv:459` `assign sfrlock = '0;` — `SFR_CONFIG`, `SFR_FILTER_*` and `SFR_*_GUTTER` can never be write-protected once configured.

---

##### F2 (HIGH) — The documented "security warning reset" is disabled by its own reset default, and the per-detector reset mask is not per-detector

**Doc promise** — `docs/src/system-control.md:473,479` lists, among the system reset sources reported in `RCUSRCFR`:
```
System reset sources:
| \[6\] | secresetn | Security warning reset |
```

**RTL** — `rtl/modules/sec/rtl/sensorc.sv`:
```
68:     apb_cr #(.A('h04), .DW(VDC), .IV({VDC{1'b1}}) )  		sfr_vdmask1   (.cr(cr_vdmask1), .prdata32(),.*); // reset mask
...
93:     `theregfull(clksys, resetn, vdresetnreg, '1 ) <= & ( cr_vdmask1 ? '1 : ~vdflag );
94:     always@(posedge clksys) vdresetn <= vdresetnreg;
```

`cr_vdmask1` is a `VDC`-wide vector (`VDC = SENSORVDC = 6`, `rtl/asic_top/rtl/daric_cfg_pkg.sv:205`). Used as a conditional predicate it reduces to `|cr_vdmask1`, so line 93 is **not** a per-bit mask — it evaluates to `&('1) == 1'b1` whenever *any* mask bit is set, and only degenerates to `&(~vdflag)` when `VDMASK1 == 0`.

The reset value is `{VDC{1'b1}} = 6'b111111`. Therefore out of reset `vdresetn` is permanently deasserted: **the voltage-detector security reset never fires**, and it stays dead unless software writes exactly `0x00`. Conversely, masking one noisy detector (the obvious intent of a "reset mask") disables the tamper reset for *all* detectors.

Delivery path is confirmed end to end: `rtl/asic_top/rtl/soc_top.sv:712` `.vdresetn ( secresetn )` → `rtl/modules/sysctrl/rtl/sysctrl.sv:794` `.resetnin( { socresetn, vdresetn, secresetn, ~sysreset_sw } )`.

The commented-out predecessor at `sensorc.sv:92` shows the same defect, so this is not a transcription slip in one line. The correct idiom would be `&( cr_vdmask1 | ~vdflag )`.

---

##### F3 (MEDIUM-HIGH) — Clock-cipher "level" is inverted relative to the documentation: requesting maximum side-channel hardening yields zero clock scrambling

**Doc promise** — `docs/src/clock-generation.md:110,112,115`:
```
| \[3:0\]  | clkcipher level (clktop) | Clock cipher speed for clktop. `0xF` = full speed, `0x0` = slowest (does not stop) |
| \[11:8\] | clkcipher level (clkpke) | Clock cipher speed for clkpke. `0xF` = full speed, `0x0` = slowest (does not stop) |
The clock cipher scrambles the system clock by skipping pulses according to the state of an LFSR configured by `CGU_SEED`. This feature can harden the system against side channel analysis...
```

**RTL** — `rtl/modules/sysctrl/rtl/sysctrl.sv`:
```
673:    `theregfull( clktop, coreresetn, clktopenin_sec, '1 ) <= clkcipheren ? ( clkcipherdat >= clkcipherlevel * 16 ) : '1;
676:    assign clkcipherlevel = cgusec[3:0];
677:    assign clkcipheren = cgusec[4];
```
and identically for the PKE clock at `:555` / `:558-559`.

`clkcipherdat` is the 8-bit LFSR tap output. The threshold is `level*16`:
- `level = 0x0` → threshold `0` → `dat >= 0` is always true → clock enable is constantly asserted → **no pulses skipped at all, full speed, countermeasure completely inert** while `CGUSEC[4]` reads back as enabled.
- `level = 0xF` → threshold `240` → only ~6% of pulses pass → slowest.

The mapping is exactly the inverse of the documentation. An integrator who reads `clock-generation.md` and programs `CGUSEC = 0x0010` (enable, level 0) believing they have selected the strongest jitter setting gets a perfectly clean, unmodulated `clktop`. The failure is silent — no status bit distinguishes "cipher active" from "cipher active but transparent".

---

##### F4 (MEDIUM) — `CGU_SEED` is documented as a 32-bit cipher seed but only bit 31 reaches the LFSR, and the LFSR is frozen while the cipher is off, so the pulse-skip sequence is a fixed, precomputable constant

**Doc promise** — `docs/src/clock-generation.md:133,137,147`:
```
- **Reset value:** `0x0000_0000`
| \[31:0\] | cipher seed | Value of the clock cipher seed |
| \[31:0\] | — | Write `0x5A` to commit the seed value from `CGU_SEED` |
```

**RTL** — `rtl/modules/common/rtl/insauth.v:38`:
```
    `theregfull( clk, resetn, sdata, LFSR_IV ) <= sen ? ( swr ? ( sdin[LFSR_IW-1] ^ sdata ) : sdatapre ) : sdata ;
```

Two problems in one line:

1. **Only `sdin[31]` is used.** The seed commit XORs a single bit into a 59-bit state; because the 1-bit operand is zero-extended, it only ever inverts `sdata[0]`. Writing all 32 bits of `CGU_SEED` and committing via `CGU_SEEDAR` yields at most **two** distinct LFSR trajectories, not 2^32.
2. **The state register is gated by `sen`**, which is `clkcipheren = cgusec[4]` (`sysctrl.sv:668`, `:550`). While the cipher is disabled the LFSR does not advance, so it always restarts from the hard-coded initial value each time the cipher is enabled:
   - `sysctrl.sv:667` — `LFSR_IV('h55aa_aa55_5a5a_a5a5)` for `clktop`
   - `sysctrl.sv:549` — `LFSR_IV('hfedcba9876543210)` for `clkpke`

Net effect: the clock-skip pattern used to defeat power/EM correlation is a fixed, publicly derivable sequence with a known phase origin (cipher-enable). An attacker can align traces to it and average it out, which is precisely the property the doc claims the seed provides against.

---

##### F5 (MEDIUM) — Every register write-lock in the chip is hard-tied inactive, including the pinmux and the entire tamper subsystem

The APB/AHB register primitives implement a real `sfrlock` (`rtl/modules/amba/rtl/apb_sfr.sv:333`, `:378` — `assign apbwr = ~sfrlock & …`). Nothing in the fabricated design ever asserts it.

The pinmux lock is routed all the way to the top and then tied off:
```
rtl/modules/ifsub/rtl/soc_ifsub.sv:580:        .sfrlock    (ioxlock),
rtl/asic_top/rtl/soc_top.sv:772:                                        .ioxlock   ( '0    ),
rtl/asic_top/rtl/soc_top_no_cm7_rv.sv:788:                                        .ioxlock   ( '0    ),
```
So `AFSEL*`, `BIOSEL`, `GPIOOE*`, `INTCR*` (`docs/src/ch03-00-io-configuration.md:47-112`) can be re-muxed at any time by any code reaching `0x5012_F000` — including remapping a BIO pin onto a pad that a secure peripheral is using.

The same tie-off pattern removes write protection from the anti-tamper blocks and the ReRAM controller:
```
rtl/modules/sec/rtl/sensorc.sv:57:    `theregrn( sfrlock ) <= '0;
rtl/modules/sec/rtl/mesh.sv:46:    `theregrn( sfrlock ) <= '0;
rtl/modules/sec/rtl/gluechain.sv:42:    `theregrn( sfrlock ) <= '0;
rtl/modules/bio_bdma/rtl/bio_bdma.sv:459:    assign sfrlock = '0;
rtl/modules/rrc/rtl/rrc.sv:286:    ahb_ar #(.A('hF0), .AR(PM_RRAM_SUICIDE))    sfr_rrcar       (.ar(rrcar_suicide), .resetn(coreresetn), .sfrlock(1'b0), .*);
```

Concretely, unprivileged software that reaches these APB pages can permanently silence tamper detection with plain register writes, and none of it can be latched down by secure boot:
- `mesh.sv:68` — `assign apterr[i][j] = cr_mlie[i] & ( aptreg[i][j] != cr_mldrv[i] );` — clearing `MLIE` (`sfr_mlie`, offset `0x10`, reset value 0) zeroes every mesh error term and hence `irq`. The mesh is also **inert out of reset** (`cr_mlie` and `cr_mldrv` both reset to 0) and only ever raises an IRQ — it drives no reset and no zeroization.
- `sensorc.sv:67` — setting `VDMASK0` (already all-ones at reset) suppresses the sensor IRQ; per F2, `VDMASK1` suppresses the reset.
- `gluechain.sv:58` — `assign glueresetn[i] = cmsatpg ? '0 : gluerst[i] & resetn;` with `sfr_gcrst` reset value 0, so the glue-chain FIB detector is held in reset until software enables it, and can be returned to reset at will.
- `rrc.sv:256,286` — a single unauthenticated 16-bit magic write (`0x2468` to RRC offset `0xF0`) starts the irreversible ReRAM erase sweep (`rrc.sv:307-326`), with no lock, no redundancy and no second factor.

---

##### F6 (MEDIUM) — The `coreuser` privilege-tag debounce filter fails open: it holds the stale tag, and can be held stale indefinitely

`rtl/modules/core/rtl/cm7sys.sv:769-776`:
```
769:    `theregrn( coreuserreg1 ) <= coreuserreg0;
770:    assign coreuser_change = ~(coreuserreg1==coreuserreg0);
772:    `theregrn( coreuser_keepcnt ) <= coreuser_change ? '0 : ~coreuser_keep ? coreuser_keepcnt + 1 : coreuser_keepcnt;
773:    `theregrn( coreuser_keep ) <= coreuser_change ? '0 : coreuser_keepcnthit ? '1 : coreuser_keep;
774:    assign coreuser_keepcnthit = (coreuser_keepcnt == coreuser_filtercyc);
776:    `theregrn(coreuser) <= coreuser_keepcnthit ? coreuserreg0 : coreuser;
```
`coreuser_filtercyc` defaults to `8'h7` (`rtl/modules/sysctrl/rtl/nvrcfgs.sv:92`).

Two issues, both in the permissive direction:

1. **Lag.** After the PC leaves a privileged region, `coreuser` retains the *old, privileged* vector for `filtercyc+1` cycles. During that window the CM7's bus transactions still carry the privileged tag.
2. **Indefinite freeze.** `coreuser_keepcnt` is reset by *any* change of `coreuserreg0`. Code whose PC-region vector changes at least once every `filtercyc` cycles never satisfies `coreuser_keepcnthit`, so line 776 never commits and `coreuser` stays pinned at whatever it held when the oscillation began. A privileged→unprivileged handoff followed by a loop that straddles two region boundaries leaves the bus tag stuck at the privileged value for as long as the attacker wants.

This matters because `coreuser` is the sole gate on the SCE slave port — `rtl/modules/crypto_top/rtl/sce_sec.sv:72-76`:
```
72:    assign ahben =  mode_non ? 1'b1 :
73:                            ((sceusersel == 0 ) ? ( ahbs.hauser == daric_cfg::AMBAID4_CM7P ) : ( ahbs.hauser == daric_cfg::AMBAID4_VEXD )) &
74:                            ((sceusersel == 0 ) ? ( coreuser_cm7 == sceuser ) : ( coreuser_vex == sceuser ));
76:    ahb_gate #(.AW(32),.DW(32)) ahbsgate(.ahben,.ahbslave(ahbs),.ahbmaster(ahbm));
```
A stale-privileged `coreuser_cm7` that still equals the latched `sceuser` grants full access to the SCE register file and crypto RAM. A fail-closed filter (drop to the "no region" encoding on `coreuser_change`, restore only after the dwell) would remove both windows.

---

##### Minor doc/RTL default mismatches (no direct exploit, but they misinform integrators)

- `docs/src/ch02-00-bio-overview.md:806` states `CLOCKING_MODE` *"Defaults to `0b11` (isochronous operation)"*. `bio_bdma.sv:504` instantiates `SFR_CONFIG` as `apb_cr #(.A('h08), .DW(10))` with no `IV`, i.e. `IV = 32'h0`, so the reset value is `0b00` (2-stage synchronizer). The RTL is the safer of the two, but the documented default is wrong.
- `docs/src/clock-generation.md:106` states `CGUSEC` reset value `0x0000_8000`. `sysctrl.sv:831` is `apb_cr #(.A('h00), .DW(16)) sfr_cgusec` with no `IV`, so the actual reset value is `0x0000_0000`. Both leave the cipher disabled, so this is cosmetic.
- `docs/src/clock-generation.md:99,407-412` document `CGUOWR` as a one-way (set-only) register. It is implemented (`sysctrl.sv:887`, `apb_owr` at `sysctrl.sv:963-996`) but its `owr` output is not connected to anything anywhere in the design — grep for `owr` in `rtl/` returns only the declaration (`sysctrl.sv:816`), the instantiation (`:887`) and the module port (`:977`). It is a dead scratch register, not a lock. Also note the `apb_ar #(.AR(i))` construction means writing decimal value *i* sets bit *i*, not "write 1 to set a bit" as documented at `clock-generation.md:412`.

---

##### Deliberately not reported

`rtl/modules/sysctrl/rtl/cms.sv:34-39` declares all four 128-bit chip-mode unlock patterns (`CMSDAT_VRGNMODE`, `CMSDAT_TESTMODE`, `CMSDAT_ATPGMODE`, `CMSDAT_USERMODE`) as `'0`. Four identical values in one enum is not legal SystemVerilog, so these are redaction placeholders per `docs/src/ch00-00-rtl-overview.md:5`, not the silicon values. I flag it only so the vendor can confirm the real constants are non-trivial and that the `3'bxx1` arm at `cms.sv:121-122` — which falls through to `CMS_TEST` on a *non-matching* pattern rather than to `CMS_NONE` — is unreachable in silicon as intended by the `#eco16b` forcing of `cmspadout[0]` to zero (`cms.sv:92`).

---

## 6. Build and supply-chain surface

Reviewed manually; outside the RTL scope but part of the repository.

| Location | Issue |
|---|---|
| `.github/workflows/main.yml:65-69` | Downloads `linkcheck.sh` from the **`master` branch** of `rust-lang/rust` and executes it — unpinned remote code execution in a job holding `secrets.GITHUB_TOKEN`. |
| `.github/workflows/main.yml:20,44` | `curl \| tar -xz` of the mdbook release tarball, with no checksum or signature verification. |
| `.github/workflows/main.yml:9,33` | `actions/checkout@master` — a mutable ref rather than a pinned SHA. `peaceiris/actions-gh-pages@v3` is likewise a mutable tag. |
| `.github/workflows/main.yml` | No `permissions:` block; the job runs with default `GITHUB_TOKEN` scope and deploys to `gh-pages`. |

**Mitigating factors.** The trigger is `on: [push]` only, not `pull_request`, so untrusted forks
cannot reach it; the blast radius is limited to compromise of one of the four upstream fetch
points. All five git submodules are pinned by commit SHA, which is correct.

**Not a finding.** The `eval(` occurrences under `rtl/scripts/headergen/` are a class method on
an expression AST, not the Python builtin.

## 7. Method, limitations and handling

### 7.1 Method

16 parallel domain reviewers over the RTL, each followed by an **independent verifier**
instructed to re-derive every finding from source and to default to *refuted* where it could
not substantiate the claim itself. Every critical and high finding then faced a **two-lens
adversarial panel** — one lens testing code truth, one testing exploitability — whose explicit
instruction was to refute. A finding survived only where not every lens refuted it. Two critics
then assessed coverage and documented-guarantee-versus-RTL (§5).

The filtering was not cosmetic: **the critical count fell from 9 to 1** under adversarial
review. Verifier verdicts across all 90 primary findings were 63 confirmed, 19 plausible, 8
refuted; verifiers additionally surfaced 40 findings the domain reviewers had missed. Of 40
adversarial votes cast, 34 upheld the finding and 6 refuted it, with 24 rating exploitability
`practical` — reachable by an ordinary attacker rather than requiring exotic equipment.

### 7.2 Limitations

- **Static source review only.** No simulation, formal verification, synthesis, netlist review
  or silicon testing was performed. **No finding here has been demonstrated on hardware.**
- **Redacted constants.** `docs/src/ch00-00-rtl-overview.md:5` states the RTL "redacts some
  closed-source components." Constants reading `'0` may be placeholders rather than silicon
  values — one candidate critical was withdrawn on exactly this basis (§4). Any finding resting
  on a suspicious zero constant is a **question for the vendor**, not an assertion.
- **Black boxes**, absent from the repository and unreviewable: ARM NIC-400 (`nic400_1`),
  `ahb_bmx33_intf`, `ahb_bmxif_intf`, the `CM7AAB` AXI→AHB bridge, `cm7top`,
  `sdvt_spi_master_core`, `trbcx1r32_daric_wrapper` internals. **`hauser`/`AxUSER` propagation
  through the two AHB matrices and CM7AAB cannot be proven from open RTL**, and several
  findings depend on it.
- Third-party IP under `rtl/ips/` and the generated VexRiscv netlist received targeted review only.
- Testbench code was read for understanding but excluded from the attack surface.
- Severity ratings have not been through a formal calibration pass.

### 7.3 Handling

Results are published openly. Because the
part is fabricated and cannot be respun, findings that admit a firmware mitigation are the
actionable ones; each finding states separately what an RTL fix would be and what firmware can
do on existing silicon, and says so explicitly where the answer is that nothing can.

---

## Appendix A — Manual deep-dive: is there a hardware "no-read" on the SCE key segments?

Verified by the orchestrating model rather than by a domain agent (and not by any human),
because it determines whether BAO findings
against `combohasha.sv` / `sce_dmachnl.sv` / `scedma_amba.sv` are real. **Conclusion: there is no
hardware read-block on the SCE key segments reachable by the crypto engines.** Three independent
reasons, each verified against source:

### A.1 `ST_KI` is inert metadata

`scedma_pkg.sv:54` defines `ST_KI` ("secure key buf") and the `SEGCFGS` table tags SKEY, SCRT, PKB
and AKEY with it. **No logic anywhere in the SCE ever tests `segtype`.** Grepping all consumers of
`segtype` across `rtl/modules/crypto_top/` returns only the typedef, the struct field declaration,
and struct-literal assignments — no comparison, no gating. The segment type is documentation.

### A.2 `ACRULEs` does not privilege the key segments

`scedma_pkg.sv:290-307` — the real per-(segment, channel) permission table:

```systemverilog
'{ segid:SEGID_SKEY , accessrule: 8'b01_01_01_01 },   // secret key
'{ segid:SEGID_SCRT , accessrule: 8'b01_01_01_01 },   // secret / HMAC compare
'{ segid:SEGID_MSG  , accessrule: 8'b01_01_01_01 },   // plaintext message buffer
'{ segid:SEGID_AKEY , accessrule: 8'b01_01_01_01 },   // AES key
'{ segid:SEGID_HOUT , accessrule: 8'b01_00_00_10 },   // output buffers ARE restricted
'{ segid:SEGID_SOB  , accessrule: 8'b10_00_10_00 },
'{ segid:SEGID_POB  , accessrule: 8'b00_00_00_10 },
```

The key segments carry permissions byte-identical to the plaintext message buffer. The segments the
table actually restricts are the *output* buffers. This table governs data-flow direction, not key
confidentiality.

**Latent defect (informational):** the array is positional (`[0:SEGCNT-1]`) and position 8 is PKB,
but that entry's `segid` field reads `SEGID_KEY`. Because lookup is `chnlacrules[segid][chnl]` by
array index, behaviour is unaffected — but the table has evidently not been audited against its own
labels, and any future refactor that keys off the `segid` field will silently mis-permission PKB.

### A.3 The crypto engines' RAM channels bypass access control entirely

`sce.sv:65` declares `CHNLCNT = 17`; `scedma_pkg.sv:278` declares `CHNLACCNT = 8`. The access-control
block is instantiated across only the first eight channels (`sce.sv:377-380`):

```systemverilog
.chnlinreq  ( chnlreq[0:CHNLACCNT-1] ),   // channels 0-7 only
.chnloutreq ( ramreq[0:CHNLACCNT-1]  ),
```

Channels 8–16 are wired **directly to `ramreq[]`**, with no `scedma_ac` in the path:

| Channel | Engine | Through `scedma_ac`? |
|---|---|---|
| 0–1 | AHB slave (bus) read/write | yes |
| 2–7 | scedma xch / sch / ich | yes |
| **8–9** | **`combohash`** (hash/HMAC) | **no** |
| **10–11** | **`pke`** | **no** |
| **12–13** | **`aes`** | **no** |
| **14** | **`trng`** | **no** |
| **15–16** | **`alu`** | **no** |

### A.4 And the block is disabled outside secure mode

`sce.sv:370`: `assign acenable = mode_sec;` combined with `scedma_ac.sv:47`:
`assign chnlac[i] = acenable ? chnlacrule : '1;` — outside secure mode every channel is all-allow.
`scemode` is a software-writable register whose `sfrlock` is never driven (see the SCE global
register findings).

### A.5 Consequence

The engines' spatial confinement to their assigned segment rests **entirely** on
`rpptr <= segsize` in `sce_dmachnl.sv:120-125`. That clamp tests the already-registered pointer and
is bypassed on the `chnlstart` load path, and `rpptr_start` is a full-width software-writable APB
register (`combohasha.sv:223`, `apb_cr #(.A('h20), .DW(scedma_pkg::AW), ...)`). The clamp is
therefore load-bearing for key confidentiality and is not sound.

**Anticipated vendor response, and the reviewer's answer.** The vendor may reasonably argue that
crypto engines sit *inside* the trust boundary by design, so gating only the bus and DMA paths is
intentional. That is a defensible architecture — but it makes the pointer clamp the sole barrier
between an unprivileged software-programmed hash operation and the SKEY/SCRT/PKB/AKEY contents.
The architecture is not the defect; the unbounded pointer load is.

### A.6 Correction to earlier analysis

An earlier draft of this analysis stated that `ST_KI` marked the key segments write-only and that
this was what kept them away from the bus channel. That was wrong: `ST_KI` has no enforcement logic
behind it, and `ACRULEs` does not distinguish key segments from ordinary data buffers. The
protection described in that draft does not exist.
