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
