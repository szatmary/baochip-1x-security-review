# Baochip 1x — RTL Security Review

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
| BAO-001 | Critical | ACRAM access-control table rewritten despite denial | `rrc.sv:360` |
| BAO-002 | High | Unbounded hash segment pointer reads any SCERAM word | `combohasha.sv:629` |
| BAO-003 | High | BDMA tagged AMBAID4_MDMA; matches no RRC master decode branch | `bio_bdma.sv:122` |
| BAO-004 | High | SCE RAM wipe skips the TRNG output pool | `sce.sv:417` |
| BAO-005 | High | SCE DMA pointer bounds-checked one cycle too late | `sce_memc.sv:212` |
| BAO-006 | High | SCERAM AHB slave: ACL segid from next address phase | `scedma_amba.sv:99` |
| BAO-007 | High | Segment start pointer clamp applied to stale value | `sce_dmachnl.sv:123` |
| BAO-008 | High | AES DPA mask is a fixed-IV LFSR; TRNG port tied to zero | `aes.sv:283` |
| BAO-009 | High | AES first-order masking cancelled before the round register | `AesDataPath.v:171` |
| BAO-010 | High | AES engine SCERAM read pointer escapes its segment | `aes.sv:341` |
| BAO-011 | High | Montgomery final reduction is data-dependent in time | `mimm.sv:338` |
| BAO-012 | High | SCE trust state (ReRAM key unlock) is forgeable | `combohasha.sv:490` |
| BAO-013 | High | HMAC trust check completes on a shared DMA done pulse | `combohasha.sv:484` |
| BAO-014 | High | Default TRNG post-processing publishes raw LFSR state | `lfsr129.v:100` |
| BAO-015 | High | LFSR zero-state guard reloads a compile-time constant | `lfsr129.v:88` |
| BAO-016 | High | Raw entropy and live DRBG seed readable over APB | `trng.sv:278` |
| BAO-017 | High | Every TRNG control register permanently unlocked | `trng.sv:52` |
| BAO-018 | High | TRNG excluded from the SCE reset; seed survives mode change | `sce.sv:534` |
| BAO-019 | High | Voltage-tamper reset mask used as a scalar; resets to disabled | `sensorc.sv:93` |
| BAO-020 | High | Mesh arming lost on warm reset; mesh clock software-gateable | `soc_top.sv:702` |
| BAO-021 | High | Sticky USER-mode latch cleared by the external reset pad | `ao_top.sv:144` |
| BAO-022 | High | AO SRAM never zeroized, contradicting documented behaviour | `ao_top.sv:248` |
| BAO-023 | High | PMU regulator enables and trims unlocked; brown-out reset masked | `ao_sysctrl.sv:433` |
| BAO-024 | High | DISABLE_FILTER_PERI is a dead net; MEM bit disables both filters | `bio_bdma.sv:1478` |
| BAO-025 | High | RRC master decode has no deny-by-default arm | `rrc.sv:670` |
| BAO-026 | High | ReRAM mass erase triggered by one unprivileged store | `rrc.sv:286` |
| BAO-027 | High | All RRC access checks qualified by `data_op`; ifetch bypasses | `rrc.sv:679` |
| BAO-028 | High | Vex fabric identity selected by software-written satp.ASID | `cram_axi.sv:5816` |
| BAO-029 | High | `vex_mm` privilege signal is invertible and non-CPU-derived | `cram_axi.sv:20923` |
| BAO-030 | High | Coreuser configuration bank unqualified on the CPU data bus | `cram_axi.sv:13121` |
| BAO-031 | High | Vex instruction fetch bypasses all RRC checks (AxPROT[2]=1) | `VexRiscv_CramSoC.v:7484` |
| BAO-032 | Medium | Modular inverse is an unblinded binary EEA | `PkeCtrl.sv:1933` |
| BAO-033 | Medium | Unbounded hash output pointer defeats the ifsob/ifskey guard | `combohasha.sv:740` |
| BAO-034 | Medium | Two ReRAM config bits disable the SCE mode lock and wipe | `sce.sv:131` |
| BAO-035 | Medium | SCE trust state on system reset, not SCE reset; MSB hardwired | `sce.sv:298` |
| BAO-036 | Medium | One ReRAM byte replaces the entire SCE DMA access-rule table | `sce.sv:376` |
| BAO-037 | Medium | `acerr` violation reporting is structurally tied to zero | `scedma_ac.sv:61` |
| BAO-038 | Medium | ReRAM key credentials are plain unlocked SCE DMA registers | `scedma.sv:106` |
| BAO-039 | Medium | Unbounded array index in ich segment and AC rule lookup | `scedma.sv:277` |
| BAO-040 | Medium | `transsize == 0` decodes as 2^30 transfers with no abort | `sce_dmachnl.sv:110` |
| BAO-041 | Medium | AES has no fault detection; round count is one comparison | `AesCtrl.v:846` |
| BAO-042 | Medium | CTR_DRBG never reseeds when `reseed_interval == 0` | `ctr_aes.v:187` |
| BAO-043 | Medium | PKE countermeasure off by default, fixed IV, 1-bit reseed | `pke.sv:788` |
| BAO-044 | Medium | ALU divider leaks the quotient's Hamming weight in cycles | `aludiv.sv:100` |
| BAO-045 | Medium | Detected PKE RAM parity errors do not abort the operation | `pke.sv:1552` |
| BAO-046 | Medium | mimm round count truncates; top words silently dropped | `mimm.sv:121` |
| BAO-047 | Medium | Divide-by-zero guard tests the wrong index; ALU deadlocks | `aludiv.sv:120` |
| BAO-048 | Medium | Parity-filter mode forces `digi_data_vld` high regardless of enables | `digitalization.v:83` |
| BAO-049 | Medium | `apb_buf` decode aliases the seed buffer over adjacent registers | `trng.sv:432` |
| BAO-050 | Medium | BIST port gives full RAM read/write; no zeroization on entry | `ram_1rw_s.sv:128` |
| BAO-051 | Medium | RAM margin-trim registers unlocked and unprivileged | `rbist_wrp.sv:161` |
| BAO-052 | Medium | CMS data register powers up holding the VIRGIN pattern | `cms.sv:107` |
| BAO-053 | Medium | Mesh integrity check is a static, readable DC level | `mesh.sv:68` |
| BAO-054 | Medium | Glue chain held in reset out of reset; state clearable by software | `gluechain.sv:58` |
| BAO-055 | Medium | Every tamper event terminates in a maskable interrupt, disabled at reset | `soc_top.sv:480` |
| BAO-056 | Medium | `sfr_vdip_ena` disables the voltage detectors at the source | `sensorc.sv:78` |
| BAO-057 | Medium | Mesh tamper indications are never latched | `mesh.sv:55` |
| BAO-058 | Medium | Keypad (PIN entry) pads mirrored into main-domain GPIO | `ao_sysctrl.sv:562` |
| BAO-059 | Medium | AO timebase source is a software mux with no lock | `ao_sysctrl.sv:379` |
| BAO-060 | Medium | Software can power down the SoC domain with no wake path | `ao_sysctrl.sv:588` |
| BAO-061 | Medium | No AO configuration register is cleared by any warm reset | `ao_sysctrl.sv:434` |
| BAO-062 | Medium | sysctrl `sfrlock` is an undriven net at the top level | `soc_top.sv:217` |
| BAO-063 | Medium | Mesh clock is behind an unlocked software clock gate | `sysctrl.sv:867` |
| BAO-064 | Medium | PLL, OSC trim and all dividers unbounded and unlocked (CLKSCREW) | `sysctrl.sv:881` |
| BAO-065 | Medium | Clock cipher: fixed IV, 1-bit seed, inverted level semantics | `sysctrl.sv:667` |
| BAO-066 | Medium | WDT_LOCKCR bypassable via the unlocked PCLK divider | `sysctrl.sv:839` |
| BAO-067 | Medium | BDMA whitelist has no lock bit and no privilege check | `bio_bdma.sv:459` |
| BAO-068 | Medium | Filter misses are re-addressed to a filter-exempt gutter | `bio_bdma.sv:2562` |
| BAO-069 | Medium | Whitelist and gutter registers are write-only; policy unauditable | `bio_bdma.sv:461` |
| BAO-070 | Medium | Inter-CPU mailbox endpoint has no access control | `mbox.sv:104` |
| BAO-071 | Medium | `ahb_ar` ignores its `sfrlock` input | `ahb_sfr.sv:340` |
| BAO-072 | Medium | ReRAM one-way counters incrementable with no access check | `rrc.sv:576` |
| BAO-073 | Medium | Event-driven counter burn converts an access into an unchecked RMW | `rrc.sv:541` |
| BAO-074 | Medium | MDMA is an unauthenticated bus master reaching the CM7 TCMs | `mdma.sv:100` |
| BAO-075 | Medium | One unlocked bit permanently disables ITCM/DTCM parity | `cm7sys_tcm.sv:105` |
| BAO-076 | Medium | Coreuser debounce holds the previous, higher-privilege identity | `cm7sys.sv:776` |
| BAO-077 | Medium | No PMP; S-mode has unrestricted physical access | `GenCramSoC.scala:96` |
| BAO-078 | Medium | `sstatus` exposes and permits writing `mstatus.MPRV` | `VexRiscv_CramSoC.v:8271` |
| BAO-079 | Medium | ReRAM is cacheable; RRC checks only on fill | `VexRiscv_CramSoC.v:6801` |
| BAO-080 | Medium | Coreuser encoder has no "no identity" value; default is boot0 | `cram_axi.sv:5851` |
| BAO-081 | Medium | uDMA APB decoder deadlocks the bridge on unmapped slots | `udma_apb4k_if.sv:68` |
| BAO-082 | Medium | Pinmux write-protect routed to the top and tied to zero | `soc_top.sv:772` |
| BAO-083 | Medium | SCIF external clock ORed with internal clock, not muxed | `udma_scif.sv:217` |
| BAO-084 | Medium | External SPI chip-select used as an unsynchronized FIFO reset | `udma_spis.sv:220` |
| BAO-085 | Medium | SCIF SCC clock can latch stuck-at-1, freezing the interface | `udma_scif.sv:236` |
| BAO-086 | Low | SCE ownership can never be granted to the VexRiscv | `sce_sec.sv:62` |
| BAO-087 | Low | QFC XIP AES key and enable are unlocked control registers | `qfc.sv:202` |
| BAO-088 | Low | Hash constants loaded from bus-writable RAM, excluded from wipe | `combohasha.sv:580` |
| BAO-089 | Low | SCE ownership latched from the last transfer, not the mode writer | `sce_sec.sv:64` |
| BAO-090 | Low | `sfrlock` declared but never driven in the SCE global SFR block | `sce_glbsfra.sv:65` |
| BAO-091 | Low | Single ReRAM byte compare replaces the crypto DMA ACL | `scedma_ac.sv:40` |
| BAO-092 | Low | AES CTR increments one 32-bit word with no carry or wrap flag | `aes.sv:463` |
| BAO-093 | Low | Undefined `cr_func` permanently latches the AES SFR lock | `aes.sv:135` |
| BAO-094 | Low | PKE exposes an exact per-operation cycle counter | `pke.sv:313` |
| BAO-095 | Low | Montgomery intermediate RAM has no clear path | `PkeCore.sv:403` |
| BAO-096 | Low | Undefined `cr_func` permanently latches the hash SFR lock | `combohasha.sv:203` |
| BAO-097 | Low | `vdresetn` output flop has no reset; response is clock-dependent | `sensorc.sv:94` |
| BAO-098 | Low | Light-detector debounce of 0xF disables all light detection | `sensorc.sv:110` |
| BAO-099 | Low | AO backup registers have no lock, no owner tag, no tamper erase | `aobureg.sv:30` |
| BAO-100 | Low | Security-error NMI escalation disabled at reset and re-maskable | `evc.sv:158` |
| BAO-101 | Low | `cgucore` POR and warm reset tied together; CLKSYS select lost | `sysctrl.sv:415` |
| BAO-102 | Low | CGUOWR, the only write-once primitive, is inert | `sysctrl.sv:977` |
| BAO-103 | Low | Host reads of a running BIO's imem return its private RAM data | `bio_bdma.sv:1735` |
| BAO-104 | Low | Mailbox `rx_err` / `tx_err` reported swapped | `mbox.sv:96` |
| BAO-105 | Low | Mailbox TX word is a live tap; a second write is swallowed | `mbox_client.v:265` |
| BAO-106 | Low | APB/AHB SFR banks ignore write byte strobes | `apb_sfr.sv:339` |
| BAO-107 | Low | Mailbox PREADY is constant; gating its clock discards messages | `mbox.sv:105` |
| BAO-108 | Low | ReRAM ECC and controller errors reach only a status register | `rrc.sv:289` |
| BAO-109 | Low | ReRAM code-region protection disabled at reset (`rrccr[12]`) | `rrc.sv:778` |
| BAO-110 | Low | Program-only slot attribute evaluated from the previous descriptor | `rrc.sv:535` |
| BAO-111 | Low | Debug UART enabled at reset, unlocked, on a dedicated pad | `duart.sv:45` |
| BAO-112 | Low | `mcounteren`/`scounteren` not implemented | `VexRiscv_CramSoC.v:6266` |
| BAO-113 | Info | `healthtest_err` not qualified by `healthtest_en` | `healthtest.v:38` |
| BAO-114 | Info | BIST read-data port driven with live functional RAM data | `ram_1rw_s.sv:140` |
| BAO-115 | Info | RAM-trim write pulse synchronised on the wrong launch clock | `rbist_wrp.sv:186` |
| BAO-116 | Info | JTAG TAP does not fall back to BYPASS for undefined instructions | `tap_top.sv:542` |
| BAO-117 | Info | `ahb_gate` drops the AHB user tag at the SCE security boundary | `amba_components.sv:1028` |

---

## 3. Findings

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
